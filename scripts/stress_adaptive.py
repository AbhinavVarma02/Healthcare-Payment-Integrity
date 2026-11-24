"""Evaluate the registered H4 rule in separately scoped synthetic shift scenarios."""

import argparse
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from payment_integrity.adaptive import POLICIES, adaptive_share, ballot, evaluate
from payment_integrity.metrics import mean_with_mcse, ranked
from payment_integrity.replay import HiddenWave, VisibleWave
from payment_integrity.storage import sha256, write_json

SIZE = 1000
REVIEWS = 50
SEEDS = 200
FIRST_SEED = 66310
SCENARIOS = {
    "stationary": (400, False),
    "visible-mix-shift": (650, False),
    "latent-rank-reversal": (400, True),
    "mix-shift-and-reversal": (650, True),
}


def run(output):
    rows = []
    summaries = {}
    for name, (dme_count, reversal) in SCENARIOS.items():
        rng = np.random.default_rng(8312)
        keys = np.array([f"synthetic-{index:04}" for index in range(SIZE)])
        parts = rng.permutation(["DME"] * dme_count + ["Part B"] * (SIZE - dme_count))
        scores = np.clip(rng.uniform(0.05, 0.65, SIZE) + 0.1 * (parts == "DME"), 0, 1)
        order = ranked(scores, keys)
        order.flags.writeable = False
        share = adaptive_share(dme_count / SIZE, 0.40)
        frame = pd.DataFrame({"claim_key": keys, "part": parts, "provider_type": "Fictional",
                              "visible_lines": 1})
        wave = VisibleWave.from_frame(2025, date(2024, 6, 30), frame)
        outcomes = rng.uniform(0, 1, SIZE) < (0.8 - scores if reversal else scores)
        hidden = HiddenWave(wave, outcomes, date(2025, 6, 30))
        minutes = np.where(parts == "DME", 28, 20)
        for seed in range(FIRST_SEED, FIRST_SEED + SEEDS):
            for policy in POLICIES:
                sample, reserve = ballot(order, REVIEWS, policy, np.random.default_rng(seed), share, 10)
                assert len(sample.indices) == len(np.unique(sample.indices)) == REVIEWS
                assert all(0 < n <= size for size, n in sample.strata) == (policy != "greedy")
                rows.append({"scenario": name, "policy": policy, "seed": seed,
                             **evaluate(hidden, sample, minutes, reserve)})
        summaries[name] = {"visible_dme_share": dme_count / SIZE, "adaptive_exploration_percent": share,
                           "latent_rank_reversal": reversal, "policies": {}}
        for policy in POLICIES:
            results = [row for row in rows if row["scenario"] == name and row["policy"] == policy]
            squared = mean_with_mcse([row["ht_error"] ** 2 for row in results if row["ht_error"] is not None])
            rmse = None if squared["mean"] is None else float(np.sqrt(squared["mean"]))
            summaries[name]["policies"][policy] = {
                "yield": mean_with_mcse([row["yield"] for row in results]),
                "coverage": mean_with_mcse([row["coverage"] for row in results]),
                "interval_width": mean_with_mcse([row["interval_width"] for row in results]),
                "rmse": rmse, "rmse_mcse": squared["mcse"] / (2 * rmse) if rmse else None,
                "selected_only_rmse": float(np.sqrt(np.mean([row["selected_only_error"] ** 2 for row in results]))),
                "mean_exploratory_reviews": mean_with_mcse([row["exploration"] for row in results])["mean"],
            }
    result = {"schema_version": 1, "scope": "synthetic conditional selection stress",
              "generator_seed": 8312, "first_sampling_seed": FIRST_SEED, "sampling_seeds": SEEDS,
              "eligible_per_scenario": SIZE, "reviews_per_draw": REVIEWS, "policies": POLICIES,
              "rows": rows, "summary": summaries, "script_sha256": sha256(Path(__file__))}
    write_json(output, result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/final-h4-stress.json"))
    args = parser.parse_args()
    result = run(args.output)
    print(f"Synthetic H4 stress: {len(result['rows'])} matched-budget policy evaluations.")


if __name__ == "__main__":
    main()
