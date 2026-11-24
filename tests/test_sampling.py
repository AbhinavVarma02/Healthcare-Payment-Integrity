from itertools import combinations, product

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from payment_integrity.sampling import STRATEGIES, estimate, hypergeometric_bounds, select


@given(size=st.integers(0, 100), percent=st.integers(0, 100))
def test_exact_budget_and_claims_are_unique(size, percent):
    count = size * percent // 100
    scores, keys = np.arange(size), np.arange(size)
    for design in STRATEGIES:
        result = select(scores, keys, count, design, np.random.default_rng(4))
        assert len(set(result.indices)) == count
        assert sum(N for N, _ in result.strata) == size
        assert sum(n for _, n in result.strata) == count
        if design != "greedy" and count:
            assert np.all((result.probabilities > 0) & (result.probabilities <= 1))
            assert result.positive


@pytest.mark.parametrize("counts", [(1, 2), (2, 2)])
def test_ht_expectation_and_variance_against_enumeration(counts):
    populations = (np.array([1]), np.array([0, 1, 0, 1, 1]))
    if counts[0] == 2:
        populations = (np.array([1, 0, 1]), populations[1])
    strata = tuple(zip(map(len, populations), counts, strict=True))
    possibilities = [combinations(values, n) for values, n in zip(populations, counts, strict=True)]
    samples = [estimate(np.concatenate(combined), strata) for combined in product(*possibilities)]
    expected = np.concatenate(populations).mean()
    estimates = [item["ht"] for item in samples]
    assert np.mean(estimates) == pytest.approx(expected)
    assert np.mean([item["variance"] for item in samples]) == pytest.approx(np.var(estimates))


def test_positivity_tiny_budget_and_no_variance():
    y = np.array([1])
    assert estimate(y, ((1, 1), (9, 0)))["ht"] is None
    estimate_one = estimate(y, ((10, 1),))
    assert estimate_one["ht"] == 1.0 and estimate_one["interval"] is None
    census = estimate([1, 0], ((2, 2),))
    assert census["interval"] == [0.5, 0.5]


def test_hybrid_inclusion_marginals():
    hits = np.zeros(8)
    for seed in range(1500):
        sample = select(np.arange(8), np.arange(8), 4, "hybrid-20", np.random.default_rng(seed))
        hits[sample.indices] += 1
        assert sample.strata == ((3, 3), (5, 1))
    assert np.all(hits[-3:] == 1500)
    assert np.allclose(hits[:5] / 1500, 0.2, atol=0.03)


def test_exploratory_exact_interval_covers_toy_populations():
    for events in range(13):
        population = [1] * events + [0] * (12 - events)
        intervals = [hypergeometric_bounds(12, 4, findings, 0.025) for findings in range(5)]
        draws = list(combinations(population, 4))
        covers = sum(intervals[sum(draw)][0] <= events <= intervals[sum(draw)][1] for draw in draws)
        assert covers / len(draws) >= 0.95
    assert hypergeometric_bounds(12, 4, 0, 0.025)[1] > 0
    assert hypergeometric_bounds(12, 12, 4, 0.025) == (4, 4)
