from itertools import combinations

import numpy as np

from payment_integrity.adaptive import adaptive_share, interval
from payment_integrity.sampling import estimate, targeted_sample


def test_adaptation_and_exact_tail_enumeration():
    assert adaptive_share(0.43, 0.40) == 10
    assert adaptive_share(0.47, 0.40) == 20
    assert adaptive_share(0.60, None) == 10
    sample = targeted_sample(np.arange(6), 3, 2, np.random.default_rng(1))
    assert sample.strata == ((1, 1), (5, 2))
    assert sample.indices[0] == 0
    assert sample.probabilities.tolist() == [1, 0.4, 0.4]
    labels = np.asarray([1, 0, 1, 0, 1, 0])
    values = []
    for draw in combinations(range(1, 6), 2):
        values.append(estimate(labels[[0, *draw]], sample.strata)["ht"])
    assert np.mean(values) == labels.mean()
    assert interval(5, 5, 2) == (2, 2)


def test_exact_interval_coverage_monte_carlo():
    counts = np.random.default_rng(440).hypergeometric(7, 43, 4, size=2_000)
    coverage = np.mean([low <= 7 <= high for low, high in (interval(50, 4, int(n)) for n in counts)])
    assert coverage >= 0.945
