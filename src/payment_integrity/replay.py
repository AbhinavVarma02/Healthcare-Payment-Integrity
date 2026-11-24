"""Delayed selective-label research replay over finite CERT cohorts."""

import argparse
import io
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
from filelock import FileLock

from .cohorts import feature_snapshot
from .metrics import capacity, mean_with_mcse
from .models import MIN_GROUP, fit_lookup, line_band
from .protocol import Evaluator, Freeze, load_freeze, verify_vintage
from .sampling import STRATEGIES, Sample, effective_size, estimate, select
from .storage import atomic_bytes, read_json, sha256, write_json
from .study import development_data

WEIGHTS = ("unweighted", "ipw", "clipped")
RUN_SCHEMA = 1


@dataclass(frozen=True)
class VisibleWave:
    year: int
    decision_date: date
    keys: np.ndarray
    hash_order: np.ndarray
    cells: tuple
    groups: np.ndarray

    @classmethod
    def from_frame(cls, year, decision_date, rows):
        keys = rows["claim_key"].to_numpy(dtype=str)
        cell_keys = list(zip(rows["part"], rows["provider_type"], line_band(rows["visible_lines"]),
                             strict=True))
        cells = tuple(sorted(set(cell_keys)))
        names = {key: index for index, key in enumerate(cells)}
        groups = np.fromiter((names[key] for key in cell_keys), dtype=np.int32, count=len(keys))
        order = np.argsort(keys)
        for array in (keys, order, groups):
            array.flags.writeable = False
        return cls(year, decision_date, keys, order, cells, groups)


@dataclass(frozen=True)
class RevealedBatch:
    available: date
    entries: tuple


class Learner:
    def __init__(self, warm_entries, strength):
        self.stats = defaultdict(lambda: (0.0, 0.0))
        self.strength = strength
        self.add(warm_entries)

    def add(self, entries):
        for cell, (count, errors) in entries:
            n, bad = self.stats[cell]
            self.stats[cell] = (n + count, bad + errors)

    def score_cells(self, cells, history, cutoff):
        stats = self.stats.copy()
        for batch in history:
            if batch.available <= cutoff:
                for cell, (count, errors) in batch.entries:
                    n, bad = stats[cell]
                    stats[cell] = (n + count, bad + errors)
        part_totals = defaultdict(lambda: np.zeros(2))
        provider_totals = defaultdict(lambda: np.zeros(2))
        total_count, total_errors = 0.0, 0.0
        for key, (count, errors) in stats.items():
            total_count += count
            total_errors += errors
            part_totals[key[0]] += (count, errors)
            provider_totals[key[:2]] += (count, errors)
        prevalence = (total_errors + 1) / (total_count + 2)
        k = self.strength
        parts = {key: (errors + k * prevalence) / (count + k)
                 for key, (count, errors) in part_totals.items()}
        providers = {key: (errors + k * parts[key[0]]) / (count + k)
                     for key, (count, errors) in provider_totals.items() if count >= MIN_GROUP}
        risks = []
        for key in cells:
            parent = providers.get(key[:2], parts.get(key[0], prevalence))
            count, errors = stats[key]
            risks.append((errors + k * parent) / (count + k) if count >= MIN_GROUP else parent)
        return np.asarray(risks)


def aggregate(cells, group_ids, y, weights):
    size = len(cells)
    count = np.bincount(group_ids, weights=weights, minlength=size)
    total = np.bincount(group_ids, weights=weights * y, minlength=size)
    return tuple((cells[i], (float(count[i]), float(total[i]))) for i in np.flatnonzero(count))


class HiddenWave:
    """Evaluator-side labels. Only an explicitly chosen sample can yield training entries."""

    def __init__(self, wave, labels, available):
        self._labels = np.asarray(labels, dtype=float).copy()
        if self._labels.shape != wave.groups.shape:
            raise ValueError("Replay outcomes do not match the feature frame.")
        self._labels.flags.writeable = False
        self.wave = wave
        self.available = available
        self.complete = bool(len(labels) and np.isin(labels, (0, 1)).all())
        self.counts = np.bincount(wave.groups, minlength=len(wave.cells))
        self.positives = np.bincount(wave.groups, weights=self._labels, minlength=len(wave.cells))

    def reveal(self, sample: Sample, rule: str):
        if not self.complete:
            raise ValueError("A replay cohort has unknown outcomes.")
        outcomes = self._labels[sample.indices]
        if rule == "unweighted":
            weights = np.ones(len(outcomes))
        else:
            if not sample.positive:
                raise ValueError("Learning with IPW requires positivity in the full frame.")
            weights = 1 / sample.probabilities
            if rule == "clipped":
                weights = np.minimum(weights, 20)
        entries = aggregate(self.wave.cells, self.wave.groups[sample.indices], outcomes, weights)
        return outcomes, RevealedBatch(self.available, entries), effective_size(weights)

    def oracle(self):
        return RevealedBatch(
            self.available, aggregate(self.wave.cells, self.wave.groups, self._labels,
                                      np.ones(len(self._labels))))

    def metrics(self, cell_scores):
        if not self.complete:
            raise ValueError("Metrics require complete outcomes for the replay cohort.")
        p = cell_scores
        total = len(self._labels)
        truth = float(self.positives.sum() / total)
        brier = (np.dot(self.counts, p*p) + np.dot(self.positives, 1 - 2*p)) / total
        unique, inverse = np.unique(p, return_inverse=True)
        n = np.bincount(inverse, weights=self.counts, minlength=len(unique))[::-1]
        bad = np.bincount(inverse, weights=self.positives, minlength=len(unique))[::-1]
        precision = np.cumsum(bad) / np.cumsum(n)
        ap = float(np.dot(precision, bad) / bad.sum()) if bad.sum() else None
        bins = np.minimum(9, (10 * p).astype(int))
        residuals = np.bincount(bins, weights=self.positives - self.counts * p, minlength=10)
        return {"truth": truth, "ap": ap, "brier": float(brier),
                "ece": float(np.abs(residuals).sum() / total)}


def ballot(wave, learner, history, budget, strategy, rng):
    available = tuple(batch for batch in history if batch.available <= wave.decision_date)
    cell_risk = learner.score_cells(wave.cells, available, wave.decision_date)
    scores = cell_risk[wave.groups]
    order = wave.hash_order[np.argsort(-scores[wave.hash_order], kind="stable")]
    return cell_risk, select(scores, wave.keys, budget, strategy, rng, order=order)


def prepare(workspace, freeze):
    curated = workspace / "data" / "curated"
    config = freeze.config
    evaluator = Evaluator(workspace, freeze.commit)
    warm_years = config["replay_warm_start"]
    warm_x, warm_y, warm_keys = development_data(curated, warm_years, freeze)
    initial = VisibleWave.from_frame(0, date.min, warm_x.assign(claim_key=warm_keys))
    warm = aggregate(initial.cells, initial.groups, warm_y, np.ones(len(warm_y)))
    prior = fit_lookup(warm_x, warm_y).strength
    learner = Learner(warm, prior)
    waves = []
    provenance = []
    sources = freeze.sources
    cutoff = date.fromisoformat(sources[str(config["replay_years"][0])]["submission_end"])
    if any(date.fromisoformat(sources[str(year)]["version"]) > cutoff for year in warm_years):
        raise ValueError("Replay warm-start vintage is unavailable on the first decision date.")
    for year in config["replay_years"]:
        frame, manifest = feature_snapshot(curated, year)
        verify_vintage(year, manifest, freeze)
        source = manifest["source"]
        wave = VisibleWave.from_frame(year, date.fromisoformat(source["submission_end"]), frame)
        available = date.fromisoformat(source["version"])
        if available <= wave.decision_date:
            raise ValueError("Replay label vintage must follow the simulated review decision.")
        labels = evaluator.outcomes(year, list(wave.keys), "H3")
        hidden = HiddenWave(wave, labels, available)
        provenance.append({"year": year, "decision": wave.decision_date.isoformat(),
                           "label_available": available.isoformat(), "claims": len(labels),
                           "unknown_outcomes": int(np.isnan(labels).sum()),
                           "features_sha256": manifest["tables"]["features"],
                           "run": hidden.complete})
        if hidden.complete:
            waves.append((wave, hidden))
    return learner, waves, provenance


def one_seed(learner, waves, config, seed, cancel):
    rows, selected = [], {}
    for percent in config["budget_percent"]:
        for design_index, strategy in enumerate(STRATEGIES):
            for rule in ("unweighted",) if strategy == "greedy" else WEIGHTS:
                history, cumulative = [], 0
                for wave, hidden in waves:
                    if cancel():
                        raise InterruptedError("Replay stopped at a completed seed boundary.")
                    n = capacity(len(wave.keys), percent)
                    rng = np.random.default_rng(np.random.SeedSequence([seed, wave.year, design_index,
                                                                         percent]))
                    scores, sample = ballot(wave, learner, history, n, strategy, rng)
                    outcomes, released, train_ess = hidden.reveal(sample, rule)
                    reliability = hidden.metrics(scores)
                    estimate_result = estimate(outcomes, sample.strata)
                    interval = estimate_result["interval"]
                    findings = int(outcomes.sum())
                    cumulative += findings
                    label = f"{wave.year}-{percent}-{strategy}-{rule}"
                    selected[label] = sample.indices.astype(np.int32)
                    rows.append({
                        "year": wave.year, "budget_percent": percent, "strategy": strategy, "weight": rule,
                        **reliability, **estimate_result, "training_ess": train_ess,
                        "reviews": n, "findings": findings, "cumulative_findings": cumulative,
                        "burden": (n - findings) / findings if findings else None,
                        "yield_rate": findings / n if n else None,
                        "coverage": int(interval[0] <= reliability["truth"] <= interval[1])
                                    if interval else None,
                        "strata": sample.strata,
                        "learning_waves": sum(item.available <= wave.decision_date for item in history),
                    })
                    history.append(released)
    return rows, selected


def summarize(complete_seed_rows, seed_count, primary_year):
    cells = defaultdict(list)
    for rows in complete_seed_rows:
        for row in rows:
            key = (row["year"], row["budget_percent"], row["strategy"], row["weight"])
            cells[key].append(row)
    result = []
    for (year, budget, design, rule), group in sorted(cells.items()):
        metrics = {}
        for key in ("yield_rate", "findings", "cumulative_findings", "burden", "truth", "ess",
                    "training_ess", "coverage", "brier", "ap", "ece"):
            metrics[key] = mean_with_mcse([row[key] for row in group])
        for estimator in ("naive", "ht"):
            errors = [row[estimator] - row["truth"] for row in group if row[estimator] is not None]
            metrics[f"{estimator}_bias"] = mean_with_mcse(errors)
            metrics[f"{estimator}_rmse"] = float(np.sqrt(np.mean(np.square(errors)))) if errors else None
        result.append({"year": year, "budget_percent": budget, "strategy": design, "weight": rule,
                       "review_count": group[0]["reviews"], "seeds": len(group),
                       "learning_waves": group[0]["learning_waves"], "metrics": metrics})
    subset = {(row["strategy"], row["weight"]): row["metrics"] for row in result
              if row["year"] == primary_year and row["budget_percent"] == 5}
    conclusions = {}
    if subset:
        greedy = subset["greedy", "unweighted"]
        hybrid = subset["hybrid-10", "unweighted"]
        uniform = subset["uniform", "unweighted"]
        stratified = subset["stratified", "unweighted"]
        rmse_gain = greedy["naive_rmse"] - hybrid["ht_rmse"]
        greedy_yield = greedy["yield_rate"]["mean"]
        yield_ratio = hybrid["yield_rate"]["mean"] / greedy_yield if greedy_yield else None
        conclusions["hybrid_vs_greedy"] = {
            "rmse_improvement": rmse_gain, "yield_ratio": yield_ratio,
            "supported": bool(rmse_gain >= 0.01 and yield_ratio is not None and yield_ratio >= 0.9),
        }
        strat_gain = uniform["ht_rmse"] - stratified["ht_rmse"]
        coverage = stratified["coverage"]["mean"]
        conclusions["stratified_vs_uniform"] = {
            "rmse_improvement": strat_gain, "coverage": coverage,
            "supported": bool(coverage is not None and strat_gain >= 0.005 and 0.9 <= coverage <= 0.98),
        }
        left = cells[primary_year, 5, "hybrid-10", "unweighted"]
        right = cells[primary_year, 5, "hybrid-10", "ipw"]
        paired = mean_with_mcse([a["brier"] - b["brier"] for a, b in zip(left, right, strict=True)])
        mean, error = paired["mean"], paired["mcse"]
        interval = [mean - 1.96 * error, mean + 1.96 * error] if error is not None else None
        conclusions["ipw_vs_unweighted"] = {
            "brier_improvement": paired, "mc_interval": interval,
            "supported": bool(mean >= 0.005 and interval is not None and interval[0] > 0),
        }
    statuses = [row["supported"] for row in conclusions.values()]
    status = "supported" if statuses and all(statuses) else "mixed" if any(statuses) else "not supported"
    return result, {"status": status if statuses and seed_count > 1 else "inconclusive",
                    "components": conclusions}


def run(workspace: Path, freeze: Freeze, output: Path, seed_count: int,
        progress: Callable[[int, int], None] = lambda _n, _max: None,
        cancel: Callable[[], bool] = lambda: False):
    output.mkdir(parents=True, exist_ok=True)
    with FileLock(output / ".run-lock", timeout=0):
        return run_locked(workspace, freeze, output, seed_count, progress, cancel)


def run_locked(workspace, freeze, output, seed_count, progress, cancel):
    config = freeze.config
    if not 1 <= seed_count <= config["replay_seeds"]:
        raise ValueError("Requested seed count is outside the protocol bound.")
    start = time.perf_counter()
    manifest = output / "job.json"
    if manifest.exists():
        previous = read_json(manifest)
        if previous["freeze"] != freeze.sha256:
            raise ValueError("Replay output belongs to another frozen study.")
        if seed_count < previous["requested_seeds"]:
            raise ValueError("Use a separate output directory for fewer replay seeds.")
    learner, waves, timeline = prepare(workspace, freeze)
    completed, oracle, all_rows = [], [], []
    history: list[RevealedBatch] = []
    for wave, hidden in waves:
        scores = learner.score_cells(wave.cells, history, wave.decision_date)
        oracle.append({"year": wave.year, **hidden.metrics(scores)})
        history.append(hidden.oracle())
    for seed in range(config["seed"], config["seed"] + seed_count):
        if cancel():
            raise InterruptedError("Replay cancelled.")
        evidence = output / "seeds" / f"{seed}.json"
        selections = output / "seeds" / f"{seed}.npz"
        if evidence.exists():
            cached = read_json(evidence)
            if (cached["schema"] != RUN_SCHEMA or cached["freeze"] != freeze.sha256 or cached["seed"] != seed
                    or sha256(selections) != cached["selections_sha256"]):
                raise ValueError("Replay seed checkpoint failed integrity verification.")
            rows = cached["rows"]
        else:
            rows, selected = one_seed(learner, waves, config, seed, cancel)
            buffer = io.BytesIO()
            np.savez_compressed(buffer, **selected)
            atomic_bytes(selections, buffer.getvalue())
            write_json(evidence, {"schema": RUN_SCHEMA, "seed": seed, "freeze": freeze.sha256,
                                  "rows": rows, "selections_sha256": sha256(selections)})
        all_rows.append(rows)
        completed.append(seed)
        write_json(manifest, {"freeze": freeze.sha256, "completed_seeds": completed,
                              "requested_seeds": seed_count, "state": "running"})
        progress(len(completed), seed_count)
    summary, conclusions = summarize(all_rows, seed_count, config["primary_year"])
    complete = seed_count == config["replay_seeds"] and len(waves) == len(config["replay_years"])
    if not complete:
        conclusions["status"] = "inconclusive"
    result = {"schema": RUN_SCHEMA, "study_id": "H3-sequential", "freeze_sha256": freeze.sha256,
              "freeze_commit": freeze.commit, "timeline": timeline, "seeds": seed_count,
              "complete": complete, "runtime_seconds": time.perf_counter() - start,
              "oracle_full_labels": oracle, "policy_results": summary, "conclusions": conclusions}
    write_json(output / "h3.json", result)
    write_json(manifest, {"freeze": freeze.sha256, "completed_seeds": completed,
                          "requested_seeds": seed_count, "state": "completed"})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", required=True)
    parser.add_argument("--seeds", type=int)
    parser.add_argument("--output", type=Path, default=Path("artifacts/replay"))
    args = parser.parse_args()
    workspace = Path.cwd()
    freeze = load_freeze(workspace, args.freeze)

    def progress(n, count):
        if n == 1 or n % 10 == 0 or n == count:
            print(f"Completed {n}/{count} seeds.", flush=True)

    seeds = freeze.config["replay_seeds"] if args.seeds is None else args.seeds
    result = run(workspace, freeze, args.output, seeds, progress)
    print(result["conclusions"], result["runtime_seconds"])


if __name__ == "__main__":
    main()
