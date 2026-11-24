"""Audit capacity and fictional financial scenarios."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

from .metrics import ranked


@dataclass(frozen=True)
class Scenario:
    part_b_cents: int
    dme_cents: int
    relevant_percent: int
    review_cost_cents: int

    def __post_init__(self):
        if (min(self.part_b_cents, self.dme_cents, self.review_cost_cents) < 0
                or not 0 <= self.relevant_percent <= 100):
            raise ValueError("Invalid fictional scenario.")

    def exposures(self, parts):
        return np.where(np.asarray(parts) == "DME", self.dme_cents, self.part_b_cents)

    def net(self, risks, exposures):
        multiplier = Decimal(self.relevant_percent) / Decimal(100)
        return np.array([
            cents(Decimal(str(float(risk))) * multiplier * int(exposure) - self.review_cost_cents)
            for risk, exposure in zip(risks, exposures, strict=True)
        ], dtype=np.int64)


def cents(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def review_minutes(visible_lines):
    return np.minimum(60, 20 + 2 * (np.asarray(visible_lines, dtype=int) - 1))


def choose_count(scores, keys, parts, budget, group_max=None, reserve=0, seed=0):
    if not 0 <= reserve <= budget <= len(scores):
        raise ValueError("Audit capacity is outside the frame.")
    if group_max is not None and group_max < 0:
        raise ValueError("Group cap must be nonnegative.")
    group_use = {}
    selected = []
    chosen = np.zeros(len(scores), dtype=bool)

    def fill(order, target):
        for i in order:
            if len(selected) == target:
                break
            part = parts[i]
            used = group_use.get(part, 0)
            if group_max is None or used < group_max:
                selected.append(i)
                chosen[i] = True
                group_use[part] = used + 1

    fill(ranked(scores, keys), budget - reserve)
    target_count = len(selected)
    pool = np.flatnonzero(~chosen)
    fill(np.random.default_rng(seed).permutation(pool), target_count + reserve)
    return np.asarray(selected, dtype=int), len(selected) - target_count


def choose_minutes(net, minutes, keys, budget, *, exact=False):
    if budget < 0 or np.any(minutes <= 0):
        raise ValueError("Invalid time budget or review minutes.")
    candidates = np.flatnonzero((net > 0) & (minutes <= budget))
    if not len(candidates):
        return np.empty(0, dtype=int), {"status": "empty", "gap": None}
    if exact:
        if len(candidates) > 2000:
            raise ValueError("Exact time optimization supports up to 2,000 candidates.")
        values, times = net[candidates], minutes[candidates]
        solve = milp(-values.astype(float), integrality=np.ones(len(values)),
                     bounds=Bounds(0, 1), constraints=LinearConstraint(times, 0, budget),
                     options={"time_limit": 5.0})
        if solve.success and solve.x is not None:
            selected = candidates[solve.x > 0.5]
            if minutes[selected].sum() > budget:
                raise ArithmeticError("Solver returned an infeasible plan.")
            return selected, {"status": "optimal", "gap": float(solve.mip_gap)}
        fallback, _ = choose_minutes(net, minutes, keys, budget)
        gap = getattr(solve, "mip_gap", None)
        return fallback, {"status": "solver_fallback", "gap": float(gap) if gap is not None else None}
    order = ranked(net[candidates] / minutes[candidates], keys[candidates])
    selected, remaining = [], budget
    for index in candidates[order]:
        if minutes[index] <= remaining:
            selected.append(index)
            remaining -= minutes[index]
    return np.asarray(selected, dtype=int), {"status": "greedy", "gap": None}


def plan_summary(indexes, parts, net, minutes, capacity, outcomes=None, exposures=None,
                 scenario: Scenario | None = None):
    reviews = len(indexes)
    result = {
        "reviews": reviews, "capacity": capacity, "unused_capacity": capacity - reviews,
        "expected_scenario_net_cents": int(net[indexes].sum()),
        "minutes": int(minutes[indexes].sum()),
        "review_share": {part: float(np.mean(parts[indexes] == part)) if reviews else None
                         for part in ("Part B", "DME")},
    }
    if outcomes is not None:
        y = outcomes[indexes]
        findings = int(y.sum())
        result.update(findings=findings, yield_rate=findings / reviews if reviews else None,
                      nonfinding_per_finding=(reviews - findings) / findings if findings else None)
        if exposures is not None and scenario is not None:
            weight = int(exposures[indexes][y == 1].sum())
            actual_scenario_net = cents(Decimal(weight) * scenario.relevant_percent / 100)
            result["observed_weighted_findings_cents"] = weight
            result["observed_scenario_net_cents"] = actual_scenario_net - reviews * scenario.review_cost_cents
    return result
