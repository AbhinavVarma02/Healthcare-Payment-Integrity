"""Reconcile frozen CERT evidence and run post-freeze interval sensitivity locally."""

import argparse
import csv
import hashlib
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from payment_integrity.cohorts import feature_snapshot
from payment_integrity.protocol import Evaluator
from payment_integrity.sampling import hypergeometric_bounds
from payment_integrity.storage import read_json, sha256, write_json


def reconcile(evaluator, year):
    workspace = evaluator.workspace
    ref = evaluator.freeze
    rows, manifest = feature_snapshot(workspace / "data" / "curated", year)
    labels = evaluator.outcomes(year, rows["claim_key"].tolist(), "H3")
    path = workspace / "data" / "raw" / f"{year}.csv"
    if sha256(path) != ref.config["source_sha256"][str(year)]:
        raise ValueError(f"{year}: audit source differs from the frozen study.")
    groups = defaultdict(list)
    total = 0
    parts = {"1. Part B": "Part B", "2. DME MAC": "DME"}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream, strict=True):
            total += 1
            key = row["claim_control_number"].strip()
            groups[key].append((row["Part"].strip(), row["Provider Type"].strip() or "Missing",
                                row["Review Decision"].strip()))
    expected = []
    actual_labels = []
    mixed = 0
    for key, group in sorted(groups.items()):
        part, providers, outcomes = zip(*group, strict=True)
        if not key or len(set(part)) != 1 or part[0] not in parts:
            continue
        frequencies = Counter(providers)
        modal = sorted(frequencies, key=lambda x: (-frequencies[x], x))[0]
        digest = hashlib.sha256(f"{year}:{key}".encode()).hexdigest()
        expected.append((digest, parts[part[0]], modal, len(group), len(frequencies)))
        distinct = set(outcomes)
        actual_labels.append(int("Disagree" in distinct) if distinct <= {"Agree", "Disagree"} else np.nan)
        mixed += int({"Agree", "Disagree"} <= distinct)
    if expected != list(rows.itertuples(index=False, name=None)) or total != manifest["counts"]["rows"]:
        raise ValueError(f"{year}: independent source grouping does not reconcile to feature projection.")
    np.testing.assert_array_equal(labels, actual_labels, err_msg=f"{year}: outcome mismatch")
    return labels, {"year": year, "source_rows": total, "groups_all_parts": len(groups),
                    "eligible_groups": len(labels), "selected_part_rows": int(rows.visible_lines.sum()),
                    "disagreements": int(np.nansum(labels)), "unknown": int(np.isnan(labels).sum()),
                    "mixed_agree_disagree": mixed, "max_visible_lines": int(rows.visible_lines.max())}


def audit_sample(row, chosen, labels, *, exact=False):
    population = len(labels)
    budget = (population * row["budget_percent"] + 50) // 100
    design = row["strategy"]
    strata = [tuple(pair) for pair in row["strata"]]
    if design == "uniform":
        expected = [(population, budget)]
    elif design == "stratified":
        top = population // 5
        target = min(top, (budget + 1) // 2)
        expected = [(top, target), (population - top, budget - target)]
    else:
        reserve = (max(1, (budget * int(design.split("-")[1]) + 50) // 100)
                   if design != "greedy" else 0)
        targeted = budget - reserve
        expected = [(targeted, targeted), (population - targeted, reserve)]
    if (strata != expected or len(chosen) != budget or len(set(chosen)) != budget
            or not ((0 <= chosen) & (chosen < population)).all() or row["reviews"] != budget):
        raise ValueError("Frozen replay selections do not reconcile to their design or budget.")
    y = labels[chosen]
    findings = int(y.sum())
    truth = float(labels.mean())
    if row["findings"] != findings or not np.isclose(row["naive"], findings / budget):
        raise ValueError("Frozen replay findings do not reconcile to the selected outcomes.")
    if not all(n for _, n in strata):
        if any(row[k] is not None for k in ("ht", "variance", "interval", "coverage", "ess")):
            raise ValueError("Deterministic greedy has an unsupported cohort estimator.")
        return None
    total = var = sum_sq = lower = upper = start = 0
    random_strata = sum(size != count for size, count in strata)
    for size, count in strata:
        k = int(y[start:start + count].sum())
        total += size * k / count
        sum_sq += size**2 / count
        if count < size:
            var += size * (size - count) * k * (count - k) / (count**2 * (count - 1))
        if exact:
            low, high = (hypergeometric_bounds(size, count, k, 0.025 / random_strata)
                         if count < size else (k, k))
            lower += low
            upper += high
        start += count
    rate = total / population
    variance = var / population**2
    radius = 1.959963984540054 * np.sqrt(variance)
    np.testing.assert_allclose([rate, variance, population**2 / sum_sq],
                               [row["ht"], row["variance"], row["ess"]], atol=1e-13, rtol=1e-12)
    np.testing.assert_allclose([rate - radius, rate + radius], row["interval"], atol=1e-13, rtol=0)
    if row["coverage"] != int(rate - radius <= truth <= rate + radius):
        raise ValueError("Frozen replay coverage does not reconcile.")
    return (lower / population <= truth <= upper / population, (upper - lower) / population) if exact else None


def replay_evidence(root, config, labels):
    records = defaultdict(list)
    audited = 0
    for seed in range(config["seed"], config["seed"] + config["replay_seeds"]):
        path = root / "seeds" / f"{seed}.npz"
        record = read_json(path.with_suffix(".json"))
        if record["seed"] != seed or record["selections_sha256"] != sha256(path):
            raise ValueError("Frozen seed evidence fails checksum validation.")
        with np.load(path, allow_pickle=False) as arrays:
            if len(arrays.files) != len(record["rows"]) or len(arrays.files) != 256:
                raise ValueError("Expected 256 frozen policy, budget and wave combinations per seed.")
            for year in (2022, 2023):
                for budget in config["budget_percent"]:
                    for design in ("uniform", "hybrid-5", "hybrid-10", "hybrid-20", "stratified"):
                        prefix = f"{year}-{budget}-{design}"
                        for weight_rule in ("ipw", "clipped"):
                            np.testing.assert_array_equal(arrays[f"{prefix}-unweighted"],
                                                          arrays[f"{prefix}-{weight_rule}"])
            for row in record["rows"]:
                year, budget, design, rule = (row[k] for k in ("year", "budget_percent", "strategy", "weight"))
                primary = year == config["primary_year"] and budget == 5
                diagnostic = audit_sample(row, arrays[f"{year}-{budget}-{design}-{rule}"], labels[year],
                                          exact=primary and rule == "unweighted")
                if primary:
                    records[design, rule].append((row, diagnostic))
                audited += 1
    return records, audited


def interval_sensitivity(records):
    primary = {design: values for (design, rule), values in records.items() if rule == "unweighted"}
    diagnostic = {}
    for design, outputs in primary.items():
        pairs = [(row, interval) for row, interval in outputs if interval is not None]
        if pairs:
            diagnostic[design] = {
                "wald_coverage": float(np.mean([row["coverage"] for row, _ in pairs])),
                "wald_mean_width": float(np.mean([row["interval"][1] - row["interval"][0] for row, _ in pairs])),
                "exact_bonferroni_coverage": float(np.mean([value[0] for _, value in pairs])),
                "exact_bonferroni_mean_width": float(np.mean([value[1] for _, value in pairs])),
            }

    def column(design, field):
        return np.array([row[field] for row, _ in primary[design]])

    size = len(primary["greedy"])
    draws = np.random.default_rng(138707).integers(0, size, size=(4000, size))

    def rmse(design, field):
        errors = column(design, field) - column(design, "truth")
        return np.sqrt(np.mean(errors[draws] ** 2, axis=1))

    gain = rmse("greedy", "naive") - rmse("hybrid-10", "ht")
    ratio = column("hybrid-10", "yield_rate")[draws].mean(axis=1) / column("greedy", "yield_rate")[draws].mean(axis=1)
    strata = rmse("uniform", "ht") - rmse("stratified", "ht")
    mc = {key: np.quantile(value, [0.025, 0.975]).tolist() for key, value in {
        "hybrid_minus_greedy_rmse_gain": gain, "hybrid_greedy_yield_ratio": ratio,
        "uniform_minus_stratified_rmse": strata}.items()}
    selection_effect = float(np.mean([row["brier"] for row, _ in records["hybrid-10", "ipw"]])
                             - np.mean(column("hybrid-10", "brier")))
    return {"intervals": diagnostic, "paired_seed_bootstrap_95": mc, "ipw_brier_increase": selection_effect}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", required=True)
    parser.add_argument("--replay", type=Path, default=Path("artifacts/replay"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/audit/research-audit.json"))
    args = parser.parse_args()
    evaluator = Evaluator(Path.cwd(), args.freeze)
    labels, cohorts = {}, []
    for year in range(2018, 2026):
        labels[year], row = reconcile(evaluator, year)
        cohorts.append(row)
    records, audited = replay_evidence(args.replay, evaluator.freeze.config, labels)
    result = {"freeze_commit": args.freeze, "cohorts": cohorts, "policy_wave_seed_rows_verified": audited,
              "identical_initial_samples_across_weighting_rules": [2022, 2023],
              "h3_source_sha256": sha256(args.replay / "h3.json"),
              "exploratory_2025_at_5_percent_capacity": interval_sensitivity(records)}
    write_json(args.output, result)
    print(f"Reconciled {len(cohorts)} cohorts and {audited} policy–wave–seed records. {args.output}")


if __name__ == "__main__":
    main()
