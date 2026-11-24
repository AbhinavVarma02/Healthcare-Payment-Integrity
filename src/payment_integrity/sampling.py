"""Known-probability selection designs and finite-population estimators."""

from dataclasses import dataclass
from math import sqrt

import numpy as np

from .metrics import capacity, ranked

STRATEGIES = ("uniform", "greedy", "hybrid-5", "hybrid-10", "hybrid-20", "stratified")
Z95 = 1.959963984540054


@dataclass(frozen=True)
class Sample:
    indices: np.ndarray
    strata: tuple[tuple[int, int], ...]

    @property
    def probabilities(self):
        return np.concatenate([np.full(n, n/N) for N, n in self.strata]) if self.strata else np.empty(0)

    @property
    def positive(self):
        return bool(self.strata) and all(n > 0 for _, n in self.strata)


def select(scores, keys, budget: int, strategy: str, rng, *, order=None) -> Sample:
    size = len(scores)
    if strategy not in STRATEGIES or budget < 0 or budget > size:
        raise ValueError("Unknown design or infeasible budget.")
    if size == 0:
        return Sample(np.empty(0, dtype=int), ())
    if budget in {0, size}:
        return Sample(np.arange(budget, dtype=int), ((size, budget),))
    if strategy == "uniform" or (strategy == "stratified" and budget == 1):
        return Sample(rng.choice(size, size=budget, replace=False), ((size, budget),))
    if order is None:
        order = ranked(scores, keys)
    if strategy == "stratified":
        top_size = max(1, size // 5)
        rest_size = size - top_size
        top_count = min(top_size, budget - 1, max(1, (budget + 1)//2, budget - rest_size))
        rest_count = budget - top_count
        picked = np.concatenate((
            rng.choice(order[:top_size], size=top_count, replace=False),
            rng.choice(order[top_size:], size=rest_count, replace=False),
        ))
        return Sample(picked, ((top_size, top_count), (rest_size, rest_count)))
    reserve = 0 if strategy == "greedy" else max(1, capacity(budget, int(strategy.split("-")[-1])))
    targeted = budget - reserve
    tail = rng.choice(order[targeted:], size=reserve, replace=False)
    picked = np.concatenate((order[:targeted], tail))
    strata = ((targeted, targeted),) if targeted else ()
    return Sample(picked, strata + ((size - targeted, reserve),))


def effective_size(weights) -> float | None:
    squared = np.dot(weights, weights)
    return float(weights.sum() ** 2 / squared) if squared else None


def estimate(selected_labels, strata, confidence_z=Z95):
    """HT and SRS-without-replacement variance using only selected labels."""
    values = np.asarray(selected_labels, dtype=float)
    n_total = sum(n for _, n in strata)
    population = sum(N for N, _ in strata)
    if (n_total != len(values) or any(N < n or n < 0 or N <= 0 for N, n in strata)
            or not np.isin(values, [0, 1]).all()):
        raise ValueError("Selected outcomes or stratum sizes are inconsistent.")
    result = {
        "naive": float(values.mean()) if n_total else None,
        "ht": None, "variance": None, "interval": None, "ess": None,
    }
    if not population or any(n == 0 for _, n in strata):
        return result
    start, total, variance, weights = 0, 0.0, 0.0, []
    for size, n in strata:
        subset = values[start:start + n]
        weight = size / n
        weights.append(np.full(n, weight))
        total += weight * subset.sum()
        if n < size:
            if n < 2:
                variance = np.nan
            else:
                variance += (size / population) ** 2 * (1 - n / size) * subset.var(ddof=1) / n
        start += n
    rate = float(total / population)
    result.update(ht=rate, ess=effective_size(np.concatenate(weights)))
    if np.isfinite(variance):
        radius = confidence_z * sqrt(variance)
        result.update(variance=float(variance), interval=[rate - radius, rate + radius])
    return result
