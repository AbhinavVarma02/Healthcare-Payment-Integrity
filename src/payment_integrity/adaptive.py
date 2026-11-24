"""Retrospective adaptive allocation experiment over audited CERT cohorts."""

import argparse
import time
from functools import lru_cache
from math import sqrt
from pathlib import Path

import numpy as np
from filelock import FileLock

from .cohorts import feature_snapshot
from .metrics import capacity, mean_with_mcse
from .planning import review_minutes
from .protocol import load_freeze
from .replay import prepare
from .sampling import estimate, hypergeometric_bounds, targeted_sample
from .storage import read_json, sha256, write_json
from .workflow import digest

BUDGETS = (2, 5, 10, 20)
POLICIES = ("uniform", "greedy", "fixed-5", "fixed-10", "fixed-20", "adaptive", "matched")
SEEDS = 200


def adaptive_share(dme_share, prior_share):
    return 20 if prior_share is not None and abs(dme_share - prior_share) >= 0.05 else 10


@lru_cache(maxsize=16_384)
def interval(population, draws, findings):
    return hypergeometric_bounds(population, draws, findings, 0.025)


def ballot(order, budget, policy, rng, adaptive, matched):
    shares = {"uniform": 100, "greedy": 0, "fixed-5": 5, "fixed-10": 10,
              "fixed-20": 20, "adaptive": adaptive, "matched": matched}
    share = shares[policy]
    reserve = max(1, capacity(budget, share)) if budget and share else 0
    return targeted_sample(order, budget, reserve, rng), reserve


def evaluate(hidden, sample, minutes, reserve):
    outcomes, _, _ = hidden.reveal(sample, "unweighted")
    truth = float(hidden.positives.sum() / len(minutes))
    result = estimate(outcomes, sample.strata)
    ht = result["ht"]
    covered, width = None, None
    if ht is not None:
        tail_size, tail_draws = sample.strata[-1]
        certain_findings = int(outcomes[:-tail_draws].sum())
        low, high = interval(tail_size, tail_draws, int(outcomes[-tail_draws:].sum()))
        covered = int((certain_findings + low) / len(minutes) <= truth <= (certain_findings + high) / len(minutes))
        width = (high - low) / len(minutes)
    return {
        "truth": truth, "findings": int(outcomes.sum()), "reviews": len(outcomes),
        "yield": result["naive"], "selected_only_error": result["naive"] - truth,
        "ht_error": ht - truth if ht is not None else None,
        "coverage": covered, "interval_width": width, "ess": result["ess"],
        "exploration": reserve, "minutes": int(minutes[sample.indices].sum()),
        "nonfindings": int(len(outcomes) - outcomes.sum()),
        "strata": sample.strata, "selection_sha256": digest(sample.indices.tolist()),
    }


def summarize(rows):
    grouped = {}
    for row in rows:
        grouped.setdefault((row["year"], row["capacity_percent"], row["policy"]), []).append(row)
    summaries = []
    fields = ("findings", "yield", "ht_error", "selected_only_error", "coverage", "interval_width",
              "ess", "exploration", "minutes", "nonfindings")
    for (year, budget, policy), group in grouped.items():
        summary = {"year": year, "capacity_percent": budget, "policy": policy,
                   "oracle_rate": group[0]["truth"], "reviews": group[0]["reviews"]}
        for key in fields:
            summary[key] = mean_with_mcse([row[key] for row in group])
        for name, field in (("rmse_ht", "ht_error"), ("rmse_selected_only", "selected_only_error")):
            errors = [row[field] for row in group if row[field] is not None]
            stat = mean_with_mcse(np.square(errors))
            rmse = sqrt(stat["mean"]) if errors else None
            summary[name] = {"value": rmse, "mcse": stat["mcse"] / (2 * rmse) if rmse and stat["mcse"] else None}
        summaries.append(summary)
    primary = {row["policy"]: row for row in summaries if row["year"] == 2025 and row["capacity_percent"] == 5}
    adaptive, matched, greedy = (primary[policy] for policy in ("adaptive", "matched", "greedy"))
    a = grouped[(2025, 5, "adaptive")]
    m = grouped[(2025, 5, "matched")]
    paired = {key: mean_with_mcse([x[key] - y[key] for x, y in zip(a, m, strict=True)])
              for key in ("yield", "minutes", "coverage", "exploration")}
    paired["squared_error"] = mean_with_mcse([x["ht_error"] ** 2 - y["ht_error"] ** 2
                                             for x, y in zip(a, m, strict=True)])
    paired["rmse_delta"] = adaptive["rmse_ht"]["value"] - matched["rmse_ht"]["value"]
    left, right = adaptive["rmse_ht"]["value"], matched["rmse_ht"]["value"]
    paired["rmse_mcse"] = mean_with_mcse([
        x["ht_error"] ** 2 / (2 * left) - y["ht_error"] ** 2 / (2 * right)
        for x, y in zip(a, m, strict=True)
    ])["mcse"] if left and right else None
    p = {key: (-row["yield"]["mean"], row["rmse_ht"]["value"], row["minutes"]["mean"])
         for key, row in primary.items() if row["rmse_ht"]["value"] is not None}
    frontier = [key for key, triple in p.items() if not any(
        all(a <= b for a, b in zip(other, triple, strict=True)) and other != triple for other in p.values()
    )]
    retention = adaptive["yield"]["mean"] / greedy["yield"]["mean"]
    return summaries, {"retained_greedy_yield": retention, "paired_adaptive_minus_matched": paired,
                       "pareto_with_identifiable_rates": frontier,
                       "status": "supported" if retention >= 0.95 and paired["rmse_delta"] < 0 else "unsupported"}


def run(workspace, freeze, output, count):
    started = time.perf_counter()
    learner, loaded, provenance = prepare(workspace, freeze, purpose="H4")
    if [wave.year for wave, _ in loaded] != [2022, 2023, 2024, 2025]:
        raise ValueError("The declared H4 grid requires all four eligible complete cohorts.")
    waves = []
    previous = None
    visible_categories: set = set()
    for wave, hidden in loaded:
        frame, _ = feature_snapshot(workspace / "data" / "curated", wave.year)
        if frame["claim_key"].tolist() != list(wave.keys):
            raise ValueError("Review burden rows do not match the attested feature frame.")
        dme_share = float((frame["part"] == "DME").mean())
        adaptive = adaptive_share(dme_share, previous)
        categories = list(zip(frame["part"], frame["provider_type"], strict=True))
        novelty = sum(category not in visible_categories for category in categories) / len(categories)
        visible_categories.update(categories)
        scores = learner.score_cells(wave.cells, (), wave.decision_date)[wave.groups]
        order = wave.hash_order[np.argsort(-scores[wave.hash_order], kind="stable")]
        waves.append((wave.year, hidden, order, review_minutes(frame["visible_lines"]), adaptive, dme_share, novelty))
        previous = dme_share
    matched = (waves[0][4] + waves[1][4] + 1) // 2
    config = {"hypothesis": "H4", "scope": "historical retrospective exploratory",
              "freeze": freeze.commit, "freeze_sha256": freeze.sha256, "cohorts": provenance,
              "policies": POLICIES, "budgets": BUDGETS, "planned_seeds": SEEDS,
              "base_seed": freeze.config["seed"], "matched_exploration_percent": matched,
              "protocol_sha256": sha256(workspace / "docs" / "RESEARCH_PROTOCOL_EXTENSIONS.md"),
              "code": {name: sha256(Path(__file__).with_name(name)) for name in
                       ("adaptive.py", "replay.py", "sampling.py", "protocol.py")},
              "shift": [{"year": year, "exploration": share, "dme_share": dme, "novelty": novelty}
                        for year, _, _, _, share, dme, novelty in waves]}
    signature = digest(config)
    output.mkdir(parents=True, exist_ok=True)
    with FileLock(output / ".lock", timeout=0):
        rows = []
        for seed in range(config["base_seed"], config["base_seed"] + count):
            path = output / "seeds" / f"{seed}.json"
            if path.exists():
                saved = read_json(path)
                if saved["config_sha256"] != signature or saved["rows_sha256"] != digest(saved["rows"]):
                    raise ValueError("H4 checkpoint failed integrity or config verification.")
                batch = saved["rows"]
            else:
                batch = []
                for year, hidden, order, minutes, adaptive, _, _ in waves:
                    for percent in BUDGETS:
                        budget = capacity(len(order), percent)
                        for policy in POLICIES:
                            rng = np.random.default_rng(np.random.SeedSequence([seed, year, percent]))
                            sample, reserve = ballot(order, budget, policy, rng, adaptive, matched)
                            batch.append({"seed": seed, "year": year, "capacity_percent": percent, "policy": policy,
                                          **evaluate(hidden, sample, minutes, reserve)})
                write_json(path, {"config_sha256": signature, "rows_sha256": digest(batch), "rows": batch})
            rows.extend(batch)
        summary, primary = summarize(rows)
        result = {"config": config, "config_sha256": signature, "seed_count": count,
                  "seed_artifacts": {str(seed): sha256(output / "seeds" / f"{seed}.json")
                                     for seed in range(config["base_seed"], config["base_seed"] + count)},
                  "rows": len(rows), "primary": primary, "summary": summary,
                  "elapsed_seconds": time.perf_counter() - started,
                  "status": "complete" if count == SEEDS else "preview"}
        if count != SEEDS:
            primary["status"] = "incomplete_grid"
        write_json(output / ("h4.json" if count == SEEDS else f"preview-{count}.json"), result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", required=True)
    parser.add_argument("--output", type=Path, default=Path("artifacts/adaptive"))
    parser.add_argument("--seeds", type=int, choices=range(1, SEEDS + 1), default=SEEDS, metavar="1..200")
    args = parser.parse_args()
    workspace = Path.cwd()
    result = run(workspace, load_freeze(workspace, args.freeze), args.output, args.seeds)
    print(f"H4 {result['status']}: {result['seed_count']} seeds, {result['rows']} rows")


if __name__ == "__main__":
    main()
