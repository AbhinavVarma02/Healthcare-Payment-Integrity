from concurrent.futures import ThreadPoolExecutor

import pytest

from payment_integrity.workflow import Workflow, WorkflowError
from payment_integrity.workflow_contracts import Assign, Clock, Close, Correction, Intake, Override, Submit


def envelope(name, tick=0):
    return dict(event_id=name, idempotency_key=name, run_id="trial", event_tick=tick)


def batch(capacity=2, seed=1):
    return Intake(**envelope("intake"), capacity=capacity, seed=seed, claims=[
        {"case_id": f"demo-{i}", "part": "DME", "provider_type": "Pharmacy",
         "visible_lines": i, "provider_types": 1} for i in range(1, 5)
    ])


def scorer(claims):
    return [{"calibrated_risk": claim.visible_lines / 10, "model": "fixture",
             "feature_schema": "fixture", "provenance": {"training": "synthetic"}} for claim in claims]


def advance(workflow, current, target):
    return workflow.dispatch("advance", Clock(**envelope(f"clock-{target}", current), advance_to=target), "operator")


def test_closed_loop_as_of_correction_and_persistence(tmp_path):
    path = tmp_path / "workflow.sqlite3"
    workflow = Workflow(path, scorer)
    intake = workflow.dispatch("intake", batch(), "analyst")
    selected = intake["intake"]["selected"]
    assert len(selected) == 2
    first, second = selected
    assert workflow.receipt(first)["receipt"]["decision"]["probability"]["numerator"] == 1
    assert workflow.receipt(first)["receipt"]["decision"]["probability"]["denominator"] == 1
    for i, case in enumerate((first, second)):
        assign = Assign(**envelope(f"assign-{i}"), case_id=case, reviewer="reviewer-a")
        with pytest.raises(WorkflowError, match="role"):
            workflow.dispatch("assign", assign, "analyst")
        workflow.dispatch("assign", assign, "reviewer")
        workflow.dispatch("submit", Submit(**envelope(f"submit-{i}"), case_id=case,
                                           finding="agree", note="documentation", available_tick=2), "reviewer")
    assert workflow.run_estimate("trial")["status"] == "incomplete_feedback"
    assert workflow.receipt(first)["outcomes"] == []
    advance(workflow, 0, 2)
    workflow = Workflow(path, scorer)
    assert workflow.run_estimate("trial")["estimate"]["ht"] == 0
    workflow.dispatch("close", Close(**envelope("close", 2), case_id=first), "reviewer")
    correction = Correction(**envelope("correction", 2), case_id=first, replaces=1,
                            finding="disagree", note="coding", available_tick=3, reason="source_revision")
    workflow.dispatch("correct", correction, "supervisor")
    assert workflow.receipt(first)["outcomes"][0]["finding"] == "agree"
    advance(workflow, 2, 3)
    assert [v["finding"] for v in workflow.receipt(first)["outcomes"]] == ["agree", "disagree"]
    assert len(workflow.receipt(first, 2)["outcomes"]) == 1
    assert workflow.run_estimate("trial")["estimate"]["ht"] == 0.25
    assert next(row for row in workflow.cases("trial")["cases"] if row["case_id"] == first)["state"] == "closed"


def test_concurrent_duplicate_conflict_and_override(tmp_path):
    workflow = Workflow(tmp_path / "workflow.sqlite3", scorer)
    with ThreadPoolExecutor(max_workers=3) as workers:
        results = list(workers.map(lambda _: workflow.dispatch("intake", batch(), "analyst"), range(3)))
    assert results[0] == results[1] == results[2]
    with pytest.raises(WorkflowError, match="reused"):
        workflow.dispatch("intake", batch(seed=2), "analyst")
    first = results[0]["intake"]["selected"][0]
    other = next(item for item in workflow.cases("trial")["cases"] if item["state"] == "unselected")["case_id"]
    override = Override(**envelope("override"), case_id=first, replacement=other, reason="priority_change")
    workflow.dispatch("override", override, "supervisor")
    assert workflow.run_estimate("trial") == {"status": "intervention", "estimate": None}
    assert workflow.receipt(first)["receipt"]["decision"]["selected"]
    assert workflow.receipt(other)["history"][0]["kind"] == "override"
    assert sum(row["state"] == "queued" for row in workflow.cases("trial")["cases"]) == 2


def test_rollback_after_interrupted_scoring(tmp_path):
    def interrupted(_claims):
        raise RuntimeError("simulated interruption")

    path = tmp_path / "workflow.sqlite3"
    with pytest.raises(RuntimeError, match="interruption"):
        Workflow(path, interrupted).dispatch("intake", batch(), "analyst")
    restarted = Workflow(path, scorer)
    assert restarted.dispatch("intake", batch(), "analyst")["event_seq"] == 1

def test_receipt_chain_and_retained_anchor_detect_alteration(tmp_path):
    from payment_integrity.receipts import verify

    workflow = Workflow(tmp_path / "workflow.sqlite3", scorer)
    intake = workflow.dispatch("intake", batch(), "analyst")
    with workflow.transaction(write=False) as db:
        anchor = verify(db)
        assert anchor["digest"] == intake["event_digest"]
    advance(workflow, 0, 2)
    with workflow.transaction() as db:
        assert verify(db, anchor)["sequence"] == 2
        db.execute("UPDATE events SET previous=? WHERE seq=2", ("9" * 64,))
        with pytest.raises(WorkflowError, match="differs"):
            verify(db, anchor)
        db.execute("DELETE FROM events WHERE seq=2")
        db.execute("UPDATE clock SET tick=0")
        assert verify(db, anchor)["sequence"] == 1
        with pytest.raises(WorkflowError, match="retained"):
            verify(db, {"schema_version": 1, "sequence": 2, "digest": "9" * 64})
        db.execute("UPDATE cases SET digest=? WHERE id=?", ("0" * 64, "demo-1"))
        with pytest.raises(WorkflowError, match="projection"):
            verify(db)

def test_workflow_quarantines_invalid_transition_queue_pressure_and_out_of_order(tmp_path, monkeypatch):
    workflow = Workflow(tmp_path / "workflow.sqlite3", scorer)
    first = workflow.dispatch("intake", batch(), "analyst")["intake"]["selected"][0]
    premature = Submit(**envelope("premature"), case_id=first, finding="agree", note="coding", available_tick=1)
    with pytest.raises(WorkflowError, match="assigned"):
        workflow.dispatch("submit", premature, "reviewer")
    advance(workflow, 0, 2)
    workflow.dispatch("assign", Assign(**envelope("assignment", 2), case_id=first, reviewer="reviewer-a"), "reviewer")
    with pytest.raises(WorkflowError, match="predates"):
        workflow.dispatch("submit", premature, "reviewer")
    monkeypatch.setattr("payment_integrity.workflow.MAX_CASES", 4)
    other = batch().model_copy(update=envelope("over-capacity", 2) | {"run_id": "different"})
    with pytest.raises(WorkflowError, match="case limit"):
        workflow.dispatch("intake", other, "analyst")
    summary = workflow.overview()
    assert [entry["code"] for entry in summary["recent_rejections"]] == [
        "queue_limit", "out_of_order", "invalid_transition",
    ]
    assert summary["revealed_cases"] == 0
    assert len(summary["recent_runs"]) == 1
