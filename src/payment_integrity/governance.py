"""Evaluate and register scorecards using frozen study evidence."""

import argparse
from pathlib import Path

from .cohorts import feature_snapshot, read_parquet
from .model_io import load_scorecard
from .models import ML, feature_frame
from .monitoring import assess, development_thresholds, profile
from .protocol import Freeze, load_freeze, verify_vintage
from .registry import Registry
from .storage import read_json, sha256, write_json


def run(workspace: Path, freeze: Freeze, study: Path, replay: Path, destination: Path):
    dev = read_json(study / "development.json")
    h1 = read_json(study / "h1.json")
    h2 = read_json(study / "h2.json")
    h3 = read_json(replay / "h3.json")
    if any(item["freeze_sha256"] != freeze.sha256 for item in (dev, h1, h2, h3)):
        raise ValueError("Study evidence does not match the requested protocol.")
    if not h1["complete"] or not h3["complete"] or len(h2["cohorts"]) != len(freeze.config["holdout"]):
        raise ValueError("Governance requires completed H1–H3 core studies.")
    registry = Registry(destination)
    selection = dev["selection"]
    curated = workspace / "data" / "curated"
    primary = next(row for row in h1["cohorts"] if row["year"] == freeze.config["primary_year"])
    versions = []
    for name in dict.fromkeys((selection["scoring"], selection["challenger"])):
        model_dir = study / "models" / name
        model_hash = dev["models"][name]["scorecard_sha256"]
        model, curve = load_scorecard(model_dir, model_hash)
        providers = (model.encoder.providers if isinstance(model, ML)
                     else tuple(sorted({key[1] for key in model.providers})))
        reference = {}
        for year in (freeze.config["calibration"], freeze.config["development"]):
            rows, manifest = feature_snapshot(curated, year)
            verify_vintage(year, manifest, freeze)
            features = feature_frame(rows)
            reference[year] = profile(features, curve.predict(model.predict(features)), providers)
        baseline = reference[freeze.config["calibration"]]
        thresholds = development_thresholds(baseline, reference[freeze.config["development"]])
        monitors = []
        for year in freeze.config["holdout"]:
            rows = read_parquet(study / f"predictions-{year}.parquet")
            features = feature_frame(rows)
            scores = curve.predict(model.predict(features))
            current = profile(features, scores, providers)
            y = rows["disagreement"].to_numpy(dtype=float)
            monitors.append({
                "year": year, "before_label_release": assess(baseline, current, thresholds),
                "after_label_release": assess(baseline, current, thresholds, y, scores),
            })
        version = f"cert-v1-{name}-{model_hash[:10]}"
        results = {
            "schema": 1, "version": version, "model": name, "status": "research-only",
            "risk_tier": "high for potential external payer deployment; local research use",
            "validation_scope": "developer-authored temporal outcomes analysis",
            "primary_brier_delta": primary["models"][name]["brier"] - primary["models"]["lookup"]["brier"],
            "primary_h1_practical_gates": primary["comparison"]["status"],
            "operations_promotion": "not approved",
            "threshold_reference": {"baseline_year": freeze.config["calibration"],
                                    "development_year": freeze.config["development"],
                                    "thresholds": thresholds},
            "monitoring": monitors,
            "h2": h2["cohorts"][-1]["primary"]["status"], "h3": h3["conclusions"]["status"],
            "evidence": {
                "h1": sha256(study / "h1.json"), "h2": sha256(study / "h2.json"),
                "h3": sha256(replay / "h3.json"),
            },
        }
        provenance = {"freeze_sha256": freeze.sha256, "freeze_commit": freeze.commit,
                      "training": freeze.config["train"], "calibration": freeze.config["calibration"],
                      "development_run": dev["study_id"], "model_id": name}
        registry.install(version, model_dir, model_hash, results, provenance)
        versions.append(version)
    registry.activate(versions[0])
    result = {"active": versions[0], "versions": versions, "status": "research-only",
              "publication_model_artifacts": "excluded"}
    write_json(study / "governance.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", required=True)
    parser.add_argument("--study", type=Path, default=Path("artifacts/study"))
    parser.add_argument("--replay", type=Path, default=Path("artifacts/replay"))
    parser.add_argument("--registry", type=Path, default=Path("artifacts/registry"))
    args = parser.parse_args()
    root = Path.cwd()
    print(run(root, load_freeze(root, args.freeze), args.study, args.replay, args.registry))


if __name__ == "__main__":
    main()
