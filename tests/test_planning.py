import itertools

import numpy as np

from payment_integrity.metrics import capacity
from payment_integrity.planning import Scenario, choose_count, choose_minutes, plan_summary


def test_capacity_and_cent_rounding():
    assert capacity(30, 5) == 2
    scenario = Scenario(5, 5, 100, 1)
    assert scenario.net([0.1, 0.5], [5, 5]).tolist() == [-1, 2]


def test_group_limit_and_exploration_use_distinct_claims():
    values = np.array([10, 9, 8, 5, 1])
    parts = np.array(["DME"] * 3 + ["Part B"] * 2)
    selected, explored = choose_count(values, np.arange(len(parts)), parts, 4, group_max=2, reserve=1)
    assert len(set(selected)) == 4 and explored == 1
    assert np.sum(parts[selected] == "DME") == 2


def test_milp_matches_exhaustive_and_burden_handles_zero_findings():
    values, times = np.array([15, 12, 10, -1]), np.array([7, 6, 5, 1])
    keys = np.arange(len(values))
    selected, result = choose_minutes(values, times, keys, 11, exact=True)
    feasible = [sum(values[list(pair)]) for size in range(5)
                for pair in itertools.combinations(keys, size) if sum(times[list(pair)]) <= 11]
    assert result["status"] == "optimal"
    assert sum(values[selected]) == max(feasible)
    summary = plan_summary(selected, np.array(["DME"] * 4), values, times, 4, np.zeros(4))
    assert summary["nonfinding_per_finding"] is None
