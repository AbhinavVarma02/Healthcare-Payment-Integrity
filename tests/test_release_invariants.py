"""Independent oracles for release-critical research and monetary invariants."""

from datetime import date
from fractions import Fraction
from itertools import combinations

import numpy as np
import pandas as pd
import pytest

from payment_integrity.adaptive import adaptive_share
from payment_integrity.cohorts import FEATURES
from payment_integrity.learning import GATES, Feedback, fit_candidate, passed
from payment_integrity.models import MIN_GROUP, Encoder, Sigmoid, feature_frame, fit_lookup
from payment_integrity.planning import Scenario, choose_count, choose_minutes, plan_summary
from payment_integrity.replay import HiddenWave, Learner, RevealedBatch, VisibleWave, ballot
from payment_integrity.sampling import STRATEGIES, effective_size, estimate


def claim(part="DME", provider="Supply", lines=1):
    return {"part": part, "provider_type": provider, "visible_lines": lines, "provider_types": 1}


@pytest.mark.parametrize("current,previous,expected", [
    (0.4, None, 10),
    (0.449, 0.4, 10),
    (0.45, 0.4, 20),
    (0.4, 0.45, 20),
    (0.65, 0.4, 20),
], ids=["initial", "below-trigger", "inclusive-up", "inclusive-down", "large-visible-shift"])
def test_adaptive_threshold_has_inclusive_five_point_boundary(current, previous, expected):
    assert adaptive_share(current, previous) == expected


@pytest.fixture
def replay_frame():
    return pd.DataFrame([claim()] * 30 + [claim("Part B", "Lab")] * 30).assign(
        claim_key=[f"synthetic-{number:03}" for number in range(60)],
    )


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_every_policy_ignores_poisoned_pending_feedback(replay_frame, strategy):
    day = date(2024, 6, 30)
    wave = VisibleWave.from_frame(2025, day, replay_frame)
    left = Learner((), 20)
    future = date(2024, 7, 1)
    all_zero = HiddenWave(wave, np.zeros(60), future).oracle()
    all_one = HiddenWave(wave, np.ones(60), future).oracle()
    expected, base = ballot(wave, left, (), 12, strategy, np.random.default_rng(910))
    np.testing.assert_array_equal(expected, [0.5, 0.5])
    for hidden in (all_zero, all_one):
        scores, chosen = ballot(wave, left, (hidden,), 12, strategy, np.random.default_rng(910))
        np.testing.assert_array_equal(scores, expected)
        np.testing.assert_array_equal(chosen.indices, base.indices)


def test_reveal_boundary_uses_mature_observations_only(replay_frame):
    day = date(2024, 6, 30)
    wave = VisibleWave.from_frame(2025, day, replay_frame)
    batch = RevealedBatch(day, ((wave.cells[0], (30, 30)),))
    scores, _ = ballot(wave, Learner((), 20), [batch], 10, "greedy", np.random.default_rng(9))
    assert scores[0] > 0.96
    assert scores[1] == pytest.approx(Fraction(31, 32))


def test_unknown_outcomes_cannot_be_revealed(replay_frame):
    day = date(2024, 6, 30)
    wave = VisibleWave.from_frame(2025, day, replay_frame)
    labels = np.ones(60)
    labels[-1] = np.nan
    hidden = HiddenWave(wave, labels, day)
    _, sample = ballot(wave, Learner((), 20), (), 10, "greedy", np.random.default_rng(0))
    with pytest.raises(ValueError, match="unknown outcomes"):
        hidden.reveal(sample, "unweighted")


def test_ipw_requires_support_even_when_selected_weights_are_finite(replay_frame):
    day = date(2024, 6, 30)
    wave = VisibleWave.from_frame(2025, day, replay_frame)
    _, sample = ballot(wave, Learner((), 20), (), 10, "greedy", np.random.default_rng(0))
    with pytest.raises(ValueError, match="requires positivity"):
        HiddenWave(wave, np.zeros(60), day).reveal(sample, "ipw")


def test_clipping_bounds_effective_learning_weights(replay_frame):
    day = date(2024, 6, 30)
    wave = VisibleWave.from_frame(2025, day, replay_frame)
    _, sample = ballot(wave, Learner((), 20), (), 1, "uniform", np.random.default_rng(0))
    hidden = HiddenWave(wave, np.ones(60), day)
    assert hidden.reveal(sample, "ipw")[1].entries[0][1] == (60.0, 60.0)
    assert hidden.reveal(sample, "clipped")[1].entries[0][1] == (20.0, 20.0)


@pytest.mark.parametrize("labels,strata", [
    ([1], ((2, 2),)), ([0, 0], ((1, 2),)), ([], ((0, 0),)), ([], ((10, -1),)),
    ([2], ((2, 1),)), ([float("nan")], ((2, 1),)), ([0.5], ((2, 1),)),
], ids=["draw-count", "overdraw", "empty-stratum", "negative-draw", "multiclass", "missing", "fractional"])
def test_estimator_rejects_invalid_design_records(labels, strata):
    with pytest.raises(ValueError, match="inconsistent"):
        estimate(labels, strata)


@pytest.mark.parametrize("weight,expected", [
    ([1, 1, 1], 3), ([1, 3], 1.6), ([100, 300], 1.6), ([0, 0], None),
], ids=["uniform", "variable", "scale-invariant", "zero-weight"])
def test_effective_sample_size_reference_cases(weight, expected):
    assert effective_size(np.array(weight)) == expected


def test_estimator_zero_findings_and_zero_reviews_are_distinct():
    assert estimate([], ((10, 0),))["ht"] is None
    observed = estimate([0, 0], ((10, 2),))
    assert observed["ht"] == 0
    assert observed["variance"] == 0
    assert observed["ess"] == 2


def test_feature_projection_omits_outcome_and_identifier(replay_frame):
    contaminated = replay_frame.assign(disagreement=1, error_code="synthetic-secret")
    projected = feature_frame(contaminated)
    assert tuple(projected.columns) == FEATURES
    pd.testing.assert_frame_equal(projected, replay_frame.loc[:, list(FEATURES)])


def test_encoder_keeps_unseen_holdout_category_out_of_feature_space():
    train = pd.DataFrame([claim(provider="Common")] * MIN_GROUP + [claim(provider="Rare")])
    heldout = pd.DataFrame([claim(provider="Unseen")] * MIN_GROUP)
    encoder = Encoder.fit(train, counts=False)
    assert encoder.providers == ("Common",)
    assert np.count_nonzero(encoder.transform(heldout)[:, 2].toarray()) == MIN_GROUP
    assert np.count_nonzero(encoder.transform(heldout)[:, 3].toarray()) == 0


def test_hierarchical_lookup_matches_hand_calculation():
    frame = pd.DataFrame([claim()] * 20 + [claim("Part B", "Lab")] * 5)
    fitted = fit_lookup(frame, [1] * 10 + [0] * 15)
    global_rate = Fraction(11, 27)
    part_rate = (10 + 20 * global_rate) / 40
    provider_rate = (10 + 20 * part_rate) / 40
    band_rate = (10 + 20 * provider_rate) / 40
    assert fitted.rate == pytest.approx(float(global_rate))
    assert fitted.strength == 20
    predicted = fitted.predict(pd.DataFrame([claim(), claim(provider="Unseen"), claim(lines=2)]))
    assert predicted == pytest.approx([float(band_rate), float(part_rate), float(provider_rate)])


def test_calibration_bounds_extreme_probabilities():
    adjusted = Sigmoid(0.0, 1.0).predict([0, 0.5, 1])
    assert adjusted == pytest.approx([1e-6, 0.5, 1 - 1e-6])
    assert np.all((adjusted > 0) & (adjusted < 1))


@pytest.mark.parametrize("basis_points,exposure,relevance,cost,expected", [
    (1, 100_000, 100, 0, 10), (5_000, 1, 100, 0, 1), (4_999, 1, 100, 0, 0),
    (5_000, 1, 100, 1, -1), (0, 100, 100, 23, -23), (10_000, 5, 50, 5, -3),
    (10_000, 0, 100, 0, 0), (3_333, 10_500, 35, 333, 892),
], ids=["small-risk", "positive-tie", "below-tie", "negative-tie", "zero-risk", "negative-net",
        "missing-exposure-zero-scenario", "mixed-units"])
def test_scenario_cents_matches_hand_calculation(basis_points, exposure, relevance, cost, expected):
    scenario = Scenario(exposure, exposure, relevance, cost)
    assert scenario.net([basis_points / 10000], scenario.exposures(["DME"])).item() == expected


@pytest.mark.parametrize("budget,reserve,cap,expected,explored", [
    (0, 0, None, [], 0), (1, 0, None, [1], 0), (3, 0, None, [1, 0, 2], 0),
    (3, 0, 1, [1, 2], 0), (3, 2, 0, [], 0), (3, 1, 2, [1, 0, 2], 1),
], ids=["zero", "stable-tie", "census", "impossible-cap", "zero-cap", "reserve"])
def test_count_plans_match_small_fixed_cases(budget, reserve, cap, expected, explored):
    chosen, random_count = choose_count(np.array([0.4, 0.4, -1]), np.array(["b", "a", "c"]),
        np.array(["DME", "DME", "Part B"]), budget, group_max=cap, reserve=reserve, seed=33)
    assert chosen.tolist() == expected
    assert random_count == explored


@pytest.mark.parametrize("budget", [0, 2, 4, 6, 9, 16])
def test_exact_time_objective_against_exhaustive_oracle(budget):
    values, durations = np.array([7, 6, 5, 3, 0, -5, 2]), np.array([5, 4, 3, 2, 1, 1, 2])
    keys = np.arange(len(values))
    indexes, _ = choose_minutes(values, durations, keys, budget, exact=True)
    possible = [subset for n in range(len(keys) + 1) for subset in combinations(keys, n)]
    expected = max(sum(values[list(subset)]) for subset in possible if sum(durations[list(subset)]) <= budget)
    assert durations[indexes].sum() <= budget
    assert values[indexes].sum() == expected


def test_plan_totals_reconcile_to_selected_exposures_and_cost():
    scenario = Scenario(100, 300, 35, 80)
    parts = np.array(["DME", "Part B", "DME"])
    exposure = scenario.exposures(parts)
    expected = scenario.net([0.5, 0.0, 1.0], exposure)
    plan = plan_summary(np.array([0, 2]), parts, expected, np.array([20, 20, 22]), 3,
                        np.array([1, 1, 0]), exposure, scenario)
    assert exposure.tolist() == [300, 100, 300]
    assert plan["expected_scenario_net_cents"] == -3
    assert plan["observed_weighted_findings_cents"] == 300
    assert plan["observed_scenario_net_cents"] == -55
    assert plan["unused_capacity"] == 1


@pytest.mark.parametrize("gate", GATES)
def test_every_promotion_gate_must_be_literal_true(gate):
    report = {"gates": dict.fromkeys(GATES, True)}
    assert passed(report)
    report["gates"][gate] = 1
    assert not passed(report)


def test_candidate_excludes_future_arrival_period():
    reference = (fit_lookup(pd.DataFrame([claim()] * 40), [0, 1] * 20), Sigmoid())
    pending = [Feedback(0, 1, claim(), 0), Feedback(1, 2, claim(), 1), Feedback(2, 4, claim(), 1)]
    with pytest.raises(ValueError, match="three mature"):
        fit_candidate(reference, pending, 3, "retrain")


@pytest.mark.parametrize("periods,expected", [
    ([30, 30, 29], "at least 30 mature"), ([30, 30, 30], "require both finding classes"),
], ids=["low-validation-count", "single-class-calibration"])
def test_candidate_rejects_insufficient_evidence(periods, expected):
    reference = (fit_lookup(pd.DataFrame([claim()] * 40), [0, 1] * 20), Sigmoid())
    findings = [Feedback(tick, tick + 1, claim(), 0) for tick, count in enumerate(periods) for _ in range(count)]
    with pytest.raises(ValueError, match=expected):
        fit_candidate(reference, findings, 3, "recalibrate")
