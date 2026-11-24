from datetime import date

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import average_precision_score

from payment_integrity.models import fit_lookup
from payment_integrity.replay import HiddenWave, Learner, VisibleWave, aggregate, ballot


def test_hidden_outcome_poisoning_and_delay():
    source = pd.DataFrame({
        "part": ["DME"] * 30 + ["Part B"] * 30,
        "provider_type": ["Supply"] * 30 + ["Lab"] * 30,
        "visible_lines": [1] * 20 + [3] * 10 + [1] * 30,
        "claim_key": [f"fictional-{i:03}" for i in range(60)],
    })
    first = VisibleWave.from_frame(2022, date(2021, 6, 30), source)
    truth = np.tile([1, 0, 1, 0, 0], 12)
    warm = aggregate(first.cells, first.groups, truth, np.ones(60))
    lookup = fit_lookup(source, truth)
    learner = Learner(warm, lookup.strength)
    available = date(2023, 3, 6)
    left = HiddenWave(first, truth, available)
    right = HiddenWave(first, 1 - truth, available)
    scores, sample = ballot(first, learner, [], 25, "stratified", np.random.default_rng(1))
    np.testing.assert_allclose(scores[first.groups], lookup.predict(source))
    assert left.metrics(scores)["ap"] == pytest.approx(average_precision_score(truth, scores[first.groups]))
    a = left.reveal(sample, "ipw")[1]
    b = right.reveal(sample, "ipw")[1]
    before = VisibleWave.from_frame(2023, date(2022, 6, 30), source)
    after = VisibleWave.from_frame(2024, date(2023, 6, 30), source)
    before_a, sa = ballot(before, learner, [a], 12, "hybrid-10", np.random.default_rng(2))
    before_b, sb = ballot(before, learner, [b], 12, "hybrid-10", np.random.default_rng(2))
    np.testing.assert_array_equal(sa.indices, sb.indices)
    np.testing.assert_allclose(before_a, before_b)
    assert not np.allclose(
        learner.score_cells(after.cells, [a], after.decision_date),
        learner.score_cells(after.cells, [b], after.decision_date),
    )
