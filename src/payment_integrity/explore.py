"""Summarize claim coverage and development outcomes without opening holdout labels."""

import argparse
from pathlib import Path

import pandas as pd

from .cohorts import DEVELOPMENT, HOLDOUT, development_outcomes, feature_snapshot
from .storage import write_json


def collect(root: Path):
    results = []
    for year in DEVELOPMENT + HOLDOUT:
        features, manifest = feature_snapshot(root, year)
        counts = manifest["counts"]
        if counts["rows"] != sum(counts.get(k, 0) for k in
                                 ("malformed_rows", "in_scope_rows", "out_of_scope_rows",
                                  "unrecognized_part_rows")):
            raise ValueError("Source row accounting failed.")
        if counts["claim_groups"] != sum(counts.get(k, 0) for k in
                                          ("feature_groups", "out_of_scope_groups",
                                           "quarantined_groups")):
            raise ValueError("Claim group accounting failed.")
        if (not features["claim_key"].is_unique or len(features) != counts["feature_groups"]
                or features["visible_lines"].sum() != counts["feature_rows"]):
            raise ValueError("Claim snapshot accounting failed.")
        row = {
            "year": year, "counts": counts, "source_sha256": manifest["source_sha256"],
            "version": manifest["source"]["version"], "parts": {},
        }
        if year in DEVELOPMENT:
            labels = development_outcomes(root, year)
            features = features.merge(labels, on="claim_key", validate="one_to_one")
        for name, part in features.groupby("part", sort=True):
            quantiles = part["visible_lines"].quantile([0.5, 0.9, 0.99])
            result = {
                "claims": len(part), "visible_lines": int(part["visible_lines"].sum()),
                "provider_categories": part["provider_type"].nunique(),
                "missing_provider": int(part["provider_type"].eq("Missing").sum()),
                "multiple_providers": int(part["provider_types"].gt(1).sum()),
                "visible_lines_p50_p90_p99": quantiles.tolist(),
            }
            if year in DEVELOPMENT:
                result["known_outcomes"] = int(part["disagreement"].count())
                result["findings"] = int(part["disagreement"].sum())
                result["rate"] = float(part["disagreement"].mean())
                bands = pd.cut(part["visible_lines"], [0, 1, 3, 6, float("inf")])
                result["line_bands"] = [
                    {"band": str(band), "claims": len(group),
                     "findings": int(group["disagreement"].sum())}
                    for band, group in part.groupby(bands, observed=True)
                ]
            row["parts"][name] = result
        results.append(row)
    return {"schema": 1, "scope": "CMS CERT with 2024–2025 outcomes sealed", "cohorts": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/curated"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/eda.json"))
    args = parser.parse_args()
    result = collect(args.root)
    write_json(args.output, result)
    for cohort in result["cohorts"]:
        print(cohort["year"], [(part, stats["claims"], stats.get("rate"))
                               for part, stats in cohort["parts"].items()])


if __name__ == "__main__":
    main()
