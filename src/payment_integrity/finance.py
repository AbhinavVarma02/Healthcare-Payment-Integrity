"""Evaluate matched-count and time-budget financial scenarios on frozen cohorts."""

import argparse
from itertools import product
from pathlib import Path

import numpy as np

from .cohorts import read_parquet
from .metrics import capacity, paired_intervals, ranked
from .planning import Scenario, choose_count, choose_minutes, plan_summary, review_minutes
from .protocol import load_freeze
from .storage import read_json, sha256, write_json


def compare(y, risk, net, keys, exposure, config):
    def statistic(indices):
        count = capacity(len(indices), 5)
        selected_risk = indices[ranked(risk[indices], keys[indices])[:count]]
        selected_value = indices[ranked(net[indices], keys[indices])[:count]]
        yield_risk, yield_value = y[selected_risk].sum(), y[selected_value].sum()
        old = np.dot(y[selected_risk], exposure[selected_risk])
        new = np.dot(y[selected_value], exposure[selected_value])
        return [(new - old) / old if old else np.nan,
                count / yield_value - count / yield_risk if yield_value and yield_risk else np.nan]

    point = [float(v) if np.isfinite(v) else None for v in statistic(np.arange(len(y)))]
    intervals = paired_intervals(len(y), statistic, config["seed"] + 19, config["bootstrap_replicates"])
    weight, burden = [item["bounds"] for item in intervals]
    if weight is None or burden is None:
        status = "inconclusive"
    elif weight[0] > 0.05 and burden[1] < 0.5:
        status = "supported"
    elif weight[1] <= 0.05 or burden[0] >= 0.5:
        status = "not supported"
    else:
        status = "inconclusive"
    return {"relative_weighted_gain": point[0], "burden_delta": point[1],
            "intervals": dict(zip(("weighted_gain", "burden_delta"), intervals, strict=True)),
            "status": status}


def run(freeze, output: Path):
    config = freeze.config
    value = read_json(output / "h1.json")
    if value["freeze_sha256"] != freeze.sha256 or not value["complete"]:
        raise ValueError("A complete held-out prediction run from this protocol is required.")
    result = {
        "schema": 1, "study_id": "H2-holdout", "freeze_sha256": freeze.sha256,
        "source_h1_sha256": sha256(output / "h1.json"),
        "model": value["selection"]["scoring"], "cohorts": [],
        "amounts": "fictional scenario cents", "primary": config["scenario"]["primary"],
    }
    for year in config["holdout"]:
        frame = read_parquet(output / f"predictions-{year}.parquet").dropna(subset=["disagreement"])
        risk, keys = frame["score"].to_numpy(), frame["claim_key"].to_numpy(dtype=str)
        parts, y = frame["part"].to_numpy(), frame["disagreement"].to_numpy(dtype=int)
        times = review_minutes(frame["visible_lines"])
        scenarios = config["scenario"]
        grid = product(scenarios["exposures_cents"].items(), scenarios["relevant_percent"],
                       scenarios["review_costs_cents"])
        rows, primary = [], None
        for (name, (part_b, dme)), fraction, cost in grid:
            scenario = Scenario(part_b, dme, fraction, cost)
            exposures = scenario.exposures(parts)
            net = scenario.net(risk, exposures)
            details = {"exposure": name, "relevant_percent": fraction, "review_cost_cents": cost}
            for percent in config["budget_percent"]:
                budget = capacity(len(y), percent)
                orders = {
                    "uniform": np.random.default_rng(config["seed"] + year).permutation(len(y))[:budget],
                    "risk": ranked(risk, keys)[:budget],
                    "value": ranked(net, keys)[:budget],
                    "value_per_minute": ranked(net / times, keys)[:budget],
                }
                values = {strategy: plan_summary(indexes, parts, net, times, budget, y, exposures, scenario)
                          for strategy, indexes in orders.items()}
                rows.append({**details, "budget_percent": percent, "plans": values})
            if details == scenarios["primary"]:
                primary = compare(y, risk, net, keys, exposures, config)
                budget = capacity(len(y), 5)
                group_cap = (3 * budget + 3) // 4
                constrained, explored = choose_count(
                    net, keys, parts, budget, group_cap, max(1, budget // 10), config["seed"])
                primary["constrained"] = {
                    **plan_summary(constrained, parts, net, times, budget, y, exposures, scenario),
                    "group_max_reviews": group_cap, "exploratory_reviews": explored,
                }
                candidates = np.random.default_rng(config["seed"]).permutation(len(y))[:500]
                sample_budget = int(times[candidates].sum()) // 10
                primary["time_solver_comparison"] = {}
                for exact in (False, True):
                    picked, solver = choose_minutes(net[candidates], times[candidates], keys[candidates],
                                                    sample_budget, exact=exact)
                    primary["time_solver_comparison"][solver["status"]] = {
                        "scenario_net_cents": int(net[candidates][picked].sum()),
                        "minutes": int(times[candidates][picked].sum()),
                        "reviews": len(picked), "solver": solver, "minute_budget": sample_budget,
                    }
        result["cohorts"].append({"year": year, "eligible": len(y), "primary": primary, "grid": rows})
        write_json(output / "h2.json", result)
        print(year, primary, flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", required=True)
    parser.add_argument("--output", type=Path, default=Path("artifacts/study"))
    args = parser.parse_args()
    run(load_freeze(Path.cwd(), args.freeze), args.output)


if __name__ == "__main__":
    main()
