"""Independent lifecycle and receipt checks on fictional SQLite workspaces."""

from fractions import Fraction

import pytest

from payment_integrity.workflow import Workflow, WorkflowError
from payment_integrity.workflow_contracts import Assign, Clock, Close, Correction, Intake, Submit


def envelope(name, tick=0):
    return {"event_id": name, "idempotency_key": name, "run_id": "run", "event_tick": tick}


def intake(strategy="greedy", capacity=2, cases=4):
    return Intake(**envelope("intake"), capacity=capacity, seed=7, strategy=strategy, claims=[
        {"case_id": f"demo-{i:02}", "part": "DME", "provider_type": "Pharmacy",
         "visible_lines": i, "provider_types": 1} for i in range(1, cases + 1)
    ])


@pytest.fixture
def workspace(tmp_path):
    return Workflow(tmp_path / "workspace.sqlite3", lambda claims: [{
        "model": "release-lookup", "calibrated_risk": claim.visible_lines / 100,
        "shadow": {"status": "scored", "model": "release-shadow", "risk": 0.5},
    } for claim in claims])


@pytest.mark.parametrize("strategy,capacity,expected", [
    ("uniform", 10, [Fraction(1, 2)] * 20),
    ("greedy", 10, [Fraction(0)] * 10 + [Fraction(1)] * 10),
    ("hybrid-10", 10, [Fraction(1, 11)] * 11 + [Fraction(1)] * 9),
    ("hybrid-20", 10, [Fraction(1, 6)] * 12 + [Fraction(1)] * 8),
    ("uniform", 0, [Fraction(0)] * 20),
    ("uniform", 20, [Fraction(1)] * 20),
], ids=["uniform", "greedy", "one-tail-draw", "two-tail-draws", "zero-budget", "census"])
def test_receipt_probabilities_cover_the_entire_review_frame(workspace, strategy, capacity, expected):
    event = intake(strategy, capacity, 20)
    result = workspace.dispatch("intake", event, "analyst")
    probabilities = []
    for claim in event.claims:
        decision = workspace.receipt(claim.case_id)["receipt"]["decision"]
        rational = decision["probability"]
        actual = Fraction(rational["numerator"], rational["denominator"])
        probabilities.append(actual)
        assert decision["selected"] == (claim.case_id in result["intake"]["selected"])
    assert probabilities == expected
    assert sum(probabilities) == capacity


@pytest.fixture
def assigned(workspace):
    case = workspace.dispatch("intake", intake(), "analyst")["intake"]["selected"][0]
    workspace.dispatch("assign", Assign(**envelope("assignment"), case_id=case, reviewer="reviewer-a"), "reviewer")
    return workspace, case


def test_future_event_rolls_back_reserved_sequence(assigned):
    workspace, case = assigned
    event = Submit(**envelope("submission", 1), case_id=case, finding="agree", note="coding", available_tick=1)
    with pytest.raises(WorkflowError, match="Advance the simulation clock"):
        workspace.dispatch("submit", event, "reviewer")
    assert workspace.trace("run")["events"][0]["seq"] == 2
    workspace.dispatch("advance", Clock(**envelope("clock"), advance_to=1), "operator")
    assert workspace.dispatch("submit", event, "reviewer")["event_seq"] == 4


def test_close_requires_reveal_and_finding_stays_absent_in_shadow_metrics(assigned):
    workspace, case = assigned
    workspace.dispatch("submit", Submit(**envelope("submission"), case_id=case, finding="disagree",
                                       note="coding", available_tick=2), "reviewer")
    assert workspace.overview()["paired_shadow"]["brier_delta"] is None
    with pytest.raises(WorkflowError, match="after its finding is available"):
        workspace.dispatch("close", Close(**envelope("close"), case_id=case), "reviewer")
    workspace.dispatch("advance", Clock(**envelope("clock"), advance_to=2), "operator")
    assert workspace.overview()["paired_shadow"]["brier_delta"] == pytest.approx(0.25 - 0.96**2)
    assert workspace.dispatch("close", Close(**envelope("close", 2), case_id=case), "reviewer")["state"] == "closed"


def test_correction_training_lineage_excludes_pending_version(assigned):
    workspace, case = assigned
    workspace.dispatch("submit", Submit(**envelope("submission"), case_id=case,
                                       finding="agree", note="coding", available_tick=0), "reviewer")
    workspace.dispatch("correct", Correction(**envelope("correction"), case_id=case, replaces=1,
        finding="disagree", note="eligibility", available_tick=2, reason="clerical_error"), "supervisor")
    with pytest.raises(WorkflowError, match="latest revealed"):
        workspace.dispatch("correct", Correction(**envelope("stale"), case_id=case, replaces=1,
            finding="disagree", note="coding", available_tick=3, reason="source_revision"), "supervisor")
    old, old_digest = workspace.feedback(0)
    assert [(item.available, item.outcome) for item in old] == [(0, 0)]
    workspace.dispatch("advance", Clock(**envelope("clock"), advance_to=2), "operator")
    current, current_digest = workspace.feedback(2)
    assert [(item.available, item.outcome) for item in current] == [(2, 1)]
    assert workspace.feedback(0)[1] == old_digest != current_digest


def test_receipt_reader_fails_when_stored_plan_is_changed(assigned):
    workspace, case = assigned
    with workspace.transaction() as db:
        db.execute("UPDATE runs SET plan='{}' WHERE id='run'")
    with pytest.raises(WorkflowError, match="Allocation integrity"):
        workspace.receipt(case)
