"""Project completed experiment summaries into reviewed public aggregate fields."""

import argparse
import json
from pathlib import Path

from payment_integrity.storage import read_json, sha256, write_json


def collect(root):
    artifacts = root / "artifacts"
    h4, h5, h6 = (
        artifacts / "adaptive-complete" / "h4.json",
        artifacts / "lifecycle-final" / "h5.json",
        artifacts / "assistant" / "h6.json",
    )
    adaptive, lifecycle, analyst = (read_json(path) for path in (h4, h5, h6))
    if (adaptive["status"] != "complete" or adaptive["seed_count"] != 200 or adaptive["rows"] != 22_400
            or lifecycle["status"] != "complete" or lifecycle["runs"] != 120
            or analyst["deterministic_passes"] != 10 or analyst["critical_failures"] != 0):
        raise ValueError("Only completed, reviewed experiment grids can be projected.")
    policy_rows = []
    for row in adaptive["summary"]:
        displayed = {key: row[key] for key in ("year", "capacity_percent", "policy", "oracle_rate", "reviews")}
        policy_rows.append({
            **displayed,
            **{key: {stat: row[key][stat] for stat in ("mean", "mcse")}
               for key in ("findings", "yield", "coverage", "minutes", "exploration")},
            "cohort_rmse": row["rmse_ht"],
            "selected_only_rmse": row["rmse_selected_only"],
        })
    return {
        "schema_version": 1,
        "adaptive": {
            "evidence": {"run": "H4", "sha256": sha256(h4), "config_sha256": adaptive["config_sha256"]},
            "seeds": adaptive["seed_count"], "rows": adaptive["rows"],
            "cohorts": [{key: row[key] for key in ("year", "claims")} for row in adaptive["config"]["cohorts"]],
            "primary": {"status": adaptive["primary"]["status"],
                        "greedy_yield_retained": adaptive["primary"]["retained_greedy_yield"],
                        "matched_rmse_difference": adaptive["primary"]["paired_adaptive_minus_matched"]["rmse_delta"],
                        "matched_resource_percent": adaptive["config"]["matched_exploration_percent"]},
            "policy_results": policy_rows,
        },
        "lifecycle": {
            "evidence": {"run": "H5", "sha256": sha256(h5), "config_sha256": lifecycle["config_sha256"]},
            "scenarios": lifecycle["runs"], "waves": lifecycle["config"]["waves"],
            "cases_per_wave": lifecycle["config"]["cases_per_wave"],
            "updates": [{key: row[key] for key in ("scenario", "delay", "mode", "paired_seeds", "promoted", "rejected")}
                        | {key: {stat: row["post_wave_4_paired_difference"][key][stat] for stat in ("mean", "mcse")}
                           for key in ("brier", "yield")} for row in lifecycle["summary"]],
        },
        "assistant": {
            "evidence": {"run": "H6", "sha256": sha256(h6), "protocol_sha256": analyst["protocol_sha256"]},
            "deterministic_passes": analyst["deterministic_passes"], "critical_failures": analyst["critical_failures"],
            "local_model": analyst["model"], "model_gate": analyst["model_gate"],
            "model_attempts": analyst["model_attempts"], "model_matches": analyst["model_tool_matches"],
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = Path.cwd()
    result = collect(root)
    output = root / "web" / "src" / "research-evidence.json"
    if args.check:
        if json.loads(output.read_text(encoding="utf-8")) != result:
            raise SystemExit("The reviewed aggregate differs from current evidence.")
    else:
        write_json(output, result)
    print(sha256(output))


if __name__ == "__main__":
    main()
