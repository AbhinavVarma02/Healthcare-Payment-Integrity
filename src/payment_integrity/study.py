"""Train the frozen candidates, then evaluate H1 through isolated outcome access."""

import argparse
import importlib.metadata
import platform
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score
from threadpoolctl import threadpool_limits

from .cohorts import SCHEMA, development_outcomes, feature_snapshot, write_parquet
from .metrics import paired_intervals, precision_at, study_metrics
from .model_io import load_scorecard, save_scorecard
from .models import ML, Lookup, calibrate, feature_frame, fit_lookup, fit_ml
from .protocol import Evaluator, Freeze, load_freeze, verify_vintage
from .storage import read_json, sha256, write_json


def development_data(root: Path, years, freeze: Freeze):
    frames = []
    for year in years:
        features, manifest = feature_snapshot(root, year)
        verify_vintage(year, manifest, freeze)
        labels = development_outcomes(root, year)
        data = features.merge(labels, validate="one_to_one", on="claim_key", how="left")
        frames.append(data.dropna(subset=["disagreement"]))
    data = pd.concat(frames, ignore_index=True)
    if not data["claim_key"].is_unique:
        raise ValueError("Training snapshots overlap.")
    return feature_frame(data), data["disagreement"].to_numpy(dtype=int), data["claim_key"].to_numpy()


def select(root: Path, freeze: Freeze, output: Path):
    start = time.perf_counter()
    config = freeze.config
    curated = root / "data" / "curated"
    x_train, y_train, _ = development_data(curated, config["train"], freeze)
    x_cal, y_cal, _ = development_data(curated, [config["calibration"]], freeze)
    x_dev, y_dev, dev_keys = development_data(curated, [config["development"]], freeze)
    candidates: dict[str, Lookup | ML] = {
        name: fit_lookup(x_train, y_train, name) for name in ("global", "historical", "lookup")
    }
    for coefficient in (0.1, 1, 10):
        candidates[f"logistic-{coefficient}"] = fit_ml(
            x_train, y_train, "logistic", coefficient, config["seed"])
    for depth in (2, 4):
        candidates[f"xgb-{depth}"] = fit_ml(x_train, y_train, "xgb", depth, config["seed"])
    candidates["logistic-no-counts"] = fit_ml(
        x_train, y_train, "logistic", 1, config["seed"], counts=False)
    budgets = config["budget_percent"]
    summaries = {}
    for name, model in candidates.items():
        curve = calibrate(model.predict(x_cal), y_cal)
        raw = model.predict(x_dev)
        save_scorecard(output / "models" / name, model, curve)
        summaries[name] = {
            "raw": study_metrics(y_dev, raw, dev_keys, budgets),
            "calibrated": study_metrics(y_dev, curve.predict(raw), dev_keys, budgets),
            "calibration": vars(curve),
            "scorecard_sha256": sha256(output / "models" / name / "scorecard.json"),
        }

    def preference(name):
        results = summaries[name]["calibrated"]
        return (-results["ap"], results["brier"], name)

    challenger = min(set(candidates) - {"global", "historical", "lookup", "logistic-no-counts"},
                     key=preference)
    scoring = min((challenger, "lookup"), key=preference)
    # Development-only forward comparison. RY2021 supplies calibration before RY2023.
    early, early_y, _ = development_data(curated, config["train"][:-1], freeze)
    next_features, next_y, _ = development_data(curated, [config["train"][-1]], freeze)
    old = fit_ml(early, early_y, "logistic", 1, config["seed"])
    old_scores = old.predict(x_dev)
    early_cal = calibrate(old.predict(next_features), next_y)
    new_cal = calibrate(old.predict(x_cal), y_cal)
    retrained = summaries["logistic-1"]["calibrated"]
    result = {
        "schema": 1, "feature_schema": SCHEMA, "study_id": "dev-model-select",
        "freeze_sha256": freeze.sha256, "freeze_commit": freeze.commit,
        "split": {"train": len(y_train), "calibration": len(y_cal), "development": len(y_dev)},
        "selection": {"challenger": challenger, "scoring": scoring}, "models": summaries,
        "development_only_maintenance": {
            "early_model_early_calibration": study_metrics(y_dev, early_cal.predict(old_scores),
                                                          dev_keys, budgets, curve=False),
            "early_model_recent_calibration": study_metrics(y_dev, new_cal.predict(old_scores),
                                                           dev_keys, budgets, curve=False),
            "refit_and_recent_calibration": retrained,
        },
        "libraries": {name: importlib.metadata.version(name)
                      for name in ("pandas", "numpy", "duckdb", "scikit-learn", "xgboost")},
        "python": platform.python_version(),
        "runtime_seconds": time.perf_counter() - start,
    }
    write_json(output / "development.json", result)
    return result


def h1_comparison(y, scores, baseline, keys, config):
    def statistic(indices):
        labels = y[indices]
        if not labels.sum():
            return [np.nan, np.nan]
        ml, eb, sampled_keys = scores[indices], baseline[indices], keys[indices]
        return [average_precision_score(labels, ml) - average_precision_score(labels, eb),
                precision_at(labels, ml, sampled_keys, 5) - precision_at(labels, eb, sampled_keys, 5)]

    deltas = statistic(np.arange(len(y)))
    intervals = paired_intervals(len(y), statistic, config["seed"], config["bootstrap_replicates"])
    thresholds = [0.01, 0.02]
    if any(item["bounds"] is None for item in intervals):
        conclusion = "inconclusive"
    elif all(item["bounds"][0] > threshold for item, threshold in zip(intervals, thresholds, strict=True)):
        conclusion = "supported"
    elif any(item["bounds"][1] <= threshold for item, threshold in zip(intervals, thresholds, strict=True)):
        conclusion = "not supported"
    else:
        conclusion = "inconclusive"
    return {
        "average_precision_delta": float(deltas[0]), "precision_at_5_delta": float(deltas[1]),
        "intervals": dict(zip(("ap", "precision_at_5"), intervals, strict=True)), "status": conclusion,
    }


def evaluate(root: Path, freeze: Freeze, output: Path):
    development = read_json(output / "development.json")
    if development["freeze_sha256"] != freeze.sha256:
        raise ValueError("Select candidate models using this frozen protocol first.")
    evaluator = Evaluator(root, freeze.commit)
    config = freeze.config
    models = {name: load_scorecard(output / "models" / name, metadata["scorecard_sha256"])
              for name, metadata in development["models"].items()}
    results = []
    scoring = development["selection"]["scoring"]
    challenger = development["selection"]["challenger"]
    for year in config["holdout"]:
        start = time.perf_counter()
        rows, manifest = feature_snapshot(root / "data" / "curated", year)
        verify_vintage(year, manifest, freeze)
        frame = feature_frame(rows)
        keys = rows["claim_key"].to_numpy(dtype=str)
        scored = {name: curve.predict(model.predict(frame)) for name, (model, curve) in models.items()}
        labels = evaluator.outcomes(year, list(keys), "H1-H2")
        observed = np.isfinite(labels)
        y = labels[observed].astype(int)
        budget = config["budget_percent"]
        cohort = {
            "year": year, "claims": len(y), "excluded_unknown": int((~observed).sum()),
            "findings": int(y.sum()), "source_sha256": manifest["source_sha256"], "models": {},
        }
        for name, scores in scored.items():
            cohort["models"][name] = study_metrics(y, scores[observed], keys[observed], budget)
        selection = np.random.default_rng(config["seed"] + year).random(len(rows))
        random = study_metrics(y, selection[observed], keys[observed], budget, curve=False)
        cohort["random"] = {"capacity": random["capacity"], "ap": random["ap"]}
        cohort["comparison"] = h1_comparison(
            y, scored[challenger][observed], scored["lookup"][observed], keys[observed], config)
        cohort["groups"] = {}
        known = set(models[scoring][0].encoder.providers) if hasattr(
            models[scoring][0], "encoder") else {provider for _, provider in models[scoring][0].providers}
        group_cases = {
            "Part B": frame["part"].eq("Part B").to_numpy(),
            "DME": frame["part"].eq("DME").to_numpy(),
            "unknown_or_rare_provider": ~frame["provider_type"].isin(known).to_numpy(),
        }
        for name, subset in group_cases.items():
            mask = observed & subset
            group_y = labels[mask]
            if len(group_y) >= 100 and 20 <= group_y.sum() <= len(group_y) - 20:
                cohort["groups"][name] = study_metrics(
                    group_y, scored[scoring][mask], keys[mask], budget, curve=False)
        write_parquet(output / f"predictions-{year}.parquet",
                      rows.assign(score=scored[scoring], disagreement=labels))
        cohort["runtime_seconds"] = time.perf_counter() - start
        results.append(cohort)
        write_json(output / "h1.json", {
            "schema": 1, "study_id": "H1-holdout", "freeze_sha256": freeze.sha256,
            "freeze_commit": freeze.commit, "selection": development["selection"],
            "complete": len(results) == len(config["holdout"]), "cohorts": results,
        })
        print(year, cohort["comparison"], flush=True)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=["select", "evaluate"])
    parser.add_argument("--freeze", required=True)
    parser.add_argument("--output", type=Path, default=Path("artifacts/study"))
    args = parser.parse_args()
    root = Path.cwd()
    freeze = load_freeze(root, args.freeze)
    with threadpool_limits(limits=1):
        if args.step == "select":
            result = select(root, freeze, args.output)
            print(result["selection"], result["split"], result["runtime_seconds"])
        else:
            evaluate(root, freeze, args.output)


if __name__ == "__main__":
    main()
