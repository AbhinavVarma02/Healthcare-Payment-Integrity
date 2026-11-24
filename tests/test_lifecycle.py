from pathlib import Path

import pytest

from payment_integrity.api import ARTIFACT_ERRORS, predictions
from payment_integrity.cohorts import SCHEMA
from payment_integrity.learning import GATES
from payment_integrity.lifecycle import Lifecycle
from payment_integrity.model_io import save_scorecard
from payment_integrity.models import Lookup, Sigmoid
from payment_integrity.registry import Registry
from payment_integrity.storage import sha256
from payment_integrity.workflow import Workflow, WorkflowError
from payment_integrity.workflow_contracts import Authorization, DemoClaim, Intake


def test_synthetic_shadow_rejection_approval_and_rollback(tmp_path: Path, monkeypatch):
    root = tmp_path / "registry"
    source = tmp_path / "source"
    reference = Registry(root)
    model = Lookup(0.25, 10, {"DME": 0.28}, {}, {}, {}, "lookup")
    curve = Sigmoid()
    save_scorecard(source, model, curve)
    reference.install("reference", source, sha256(source / "scorecard.json"), {}, {})
    reference.activate("reference")
    lifecycle = Lifecycle(tmp_path / "ops", reference, predictions, ARTIFACT_ERRORS)
    workflow = Workflow(tmp_path / "ops" / "reviews.sqlite3", lifecycle.scores)
    claim = DemoClaim(part="DME", provider_type="Fictional", visible_lines=1, provider_types=1, case_id="demo-1")
    gates = dict.fromkeys(GATES, True)
    report = {"scope": "synthetic", "schema": 1, "feature_schema": SCHEMA, "latest_label": 1, "cutoff": 2,
              "gates": gates}
    # Controlled fixtures demonstrate the approval mechanism separately from H5's measured candidates.
    rejected = lifecycle.install(model, Sigmoid(0.5), {**report, "gates": {**gates, "brier": False}}, {})
    accepted = lifecycle.install(model, Sigmoid(0.5), report, {})

    def bound(candidate, generation):
        return Authorization(model=candidate["model"], generation=generation,
                             artifact_sha256=candidate["artifact_sha256"], report_sha256=candidate["report_sha256"],
                             reason="reviewed_evidence")

    lifecycle.change(workflow, "shadow", "operator", bound(rejected, 0))
    scored = lifecycle.scores([claim])[0]
    assert scored["model"] == "reference" and scored["shadow"]["model"] == rejected["model"]
    assert scored["calibrated_risk"] != scored["shadow"]["risk"]
    with pytest.raises(WorkflowError, match="every validation gate"):
        lifecycle.change(workflow, "promote", "supervisor", bound(rejected, 1))
    damaged = lifecycle.registry.root / rejected["model"] / "scorecard.json"
    damaged.write_text("{}", encoding="utf-8")
    assert lifecycle.scores([claim])[0]["shadow"]["status"] == "unavailable"
    lifecycle.change(workflow, "shadow", "operator", bound(accepted, 1))
    with pytest.raises(WorkflowError, match="Refresh"):
        lifecycle.change(workflow, "promote", "supervisor", bound(accepted, 1))
    with pytest.raises(WorkflowError, match="role"):
        lifecycle.change(workflow, "promote", "operator", bound(accepted, 2))
    lifecycle.change(workflow, "promote", "supervisor", bound(accepted, 2))
    assert lifecycle.scores([claim])[0]["status"] == "synthetic-active"
    with monkeypatch.context() as fault:
        def interrupt(*_args):
            raise OSError("simulated interruption before pointer replacement")

        fault.setattr("payment_integrity.lifecycle.write_json", interrupt)
        with pytest.raises(OSError, match="interruption"):
            lifecycle.change(workflow, "rollback", "supervisor", bound(accepted, 3))
        assert lifecycle.state()["active"] == accepted["model"]
    workflow.dispatch("intake", Intake(event_id="one", idempotency_key="one", run_id="fixture",
                                      event_tick=0, capacity=1, seed=3, claims=[claim]), "analyst")
    (lifecycle.registry.root / accepted["model"] / "scorecard.json").write_text("{}", encoding="utf-8")
    assert lifecycle.scores([claim])[0]["synthetic_lifecycle"] == "fallback_to_reference"
    lifecycle.change(workflow, "rollback", "supervisor", bound(accepted, 3))
    assert lifecycle.scores([claim])[0]["model"] == "reference"
    assert reference.active()[2]["version"] == "reference"
