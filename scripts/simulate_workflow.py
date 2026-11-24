"""Run and measure an isolated synthetic operations scenario."""

import argparse
import re
import sqlite3
import time
from contextlib import closing
from pathlib import Path

import numpy as np
import psutil

from payment_integrity.api import ARTIFACT_ERRORS, predictions
from payment_integrity.learning import passed
from payment_integrity.lifecycle import Lifecycle
from payment_integrity.receipts import verify
from payment_integrity.registry import Registry
from payment_integrity.storage import write_json
from payment_integrity.workflow import Workflow, WorkflowError
from payment_integrity.workflow_contracts import Assign, Authorization, Clock, Correction, Intake, Submit


def run(output, seed):
    output.mkdir(parents=True, exist_ok=True)
    database = output / "scenario.sqlite3"
    if database.exists():
        raise ValueError("Choose a new directory for the isolated scenario.")
    started = time.perf_counter()
    registry = Registry(Path("artifacts/registry"))
    lifecycle = Lifecycle(output, registry, predictions, ARTIFACT_ERRORS)
    workflow = Workflow(database, lifecycle.scores)
    rng = np.random.default_rng(seed)
    checks: dict = {}

    def command(kind, role, model, run_id, event_id, tick, **payload):
        return workflow.dispatch(kind, model(event_id=event_id, run_id=run_id,
                                 idempotency_key=event_id, event_tick=tick, **payload), role)

    def rejected(code, action, *args, **kwargs):
        try:
            action(*args, **kwargs)
        except WorkflowError as error:
            if error.code == code:
                checks[code] = "pass"
                return
            raise
        raise ValueError(f"Scenario did not observe {code}.")

    reference = registry.active()
    categories = [(part, category) for part, category in sorted(reference[0].providers)
                  if re.fullmatch("[A-Za-z][A-Za-z &-]{0,59}", category)]
    if len(categories) < 2:
        raise ValueError("Reference does not include the bounded synthetic example vocabulary.")
    for tick in range(4):
        run_id = f"trial-{tick}"
        ids = [f"demo-trial-{tick}-{i}" for i in range(60)]
        rows = [{"case_id": case_id, "part": part, "provider_type": category if i else "Novel Category",
                 "visible_lines": int(rng.integers(1, 9)), "provider_types": 1}
                for i, (case_id, (part, category)) in enumerate(
                    zip(ids, [categories[j] for j in rng.integers(0, len(categories), 60)], strict=True))]
        count = 30 if tick == 3 else 60

        event_id = f"intake-{tick}"
        batch = Intake(event_id=event_id, idempotency_key=event_id, run_id=run_id, event_tick=tick,
                       claims=rows, capacity=count, strategy="hybrid-10", seed=seed)
        plan = workflow.dispatch("intake", batch, "analyst")
        assert workflow.dispatch("intake", batch, "analyst") == plan
        checks["duplicate_intake"] = "pass"
        rejected("event_conflict", workflow.dispatch, "intake", batch.model_copy(update={"capacity": count - 1}),
                 "analyst")
        assert len(plan["intake"]["selected"]) == count
        checks["capacity_cut"] = "pass"
        for i, case_id in enumerate(plan["intake"]["selected"]):
            event_id = f"a-{tick}-{i}"
            if not i:
                rejected("role_denied", command, "assign", "analyst", Assign, run_id, event_id, tick,
                         case_id=case_id, reviewer="reviewer-a")
            command("assign", "reviewer", Assign, run_id, event_id, tick, case_id=case_id, reviewer="reviewer-a")
            risk = workflow.receipt(case_id)["receipt"]["score"]["calibrated_risk"]
            probability = min(0.95, risk + (0.25 if tick >= 2 else 0.0))
            command("submit", "reviewer", Submit, run_id, f"s-{tick}-{i}", tick, case_id=case_id,
                    finding="disagree" if rng.random() < probability else "agree", note="coding", available_tick=tick + 1)
        assert all(not row["finding"] for row in workflow.cases(run_id)["cases"])
        checks["label_delay"] = "pass"
        command("advance", "operator", Clock, run_id, f"clock-{tick}", tick, advance_to=tick + 1)
        if tick == 1:
            case_id = plan["intake"]["selected"][0]
            command("correct", "supervisor", Correction, run_id, "correct", tick + 1, case_id=case_id,
                    finding="disagree", replaces=1, note="documentation", reason="source_revision",
                    available_tick=tick + 2)
            assert len(workflow.receipt(case_id)["outcomes"]) == 1
            checks["correction_as_of"] = "pass"

    candidate = lifecycle.train(workflow, 4, "recalibrate")
    approval = Authorization(model=candidate["model"], generation=0,
                             artifact_sha256=candidate["artifact_sha256"], report_sha256=candidate["report_sha256"],
                             reason="evaluate")
    lifecycle.change(workflow, "shadow", "operator", approval)
    rejected("stale_approval", lifecycle.change, workflow, "promote", "supervisor", approval)
    if not passed(candidate["report"]):
        rejected("promotion_rejected", lifecycle.change, workflow, "promote", "supervisor",
                 approval.model_copy(update={"generation": 1}))
    shadow_case = {**rows[0], "case_id": "demo-shadow"}
    command("intake", "analyst", Intake, "shadow-run", "shadow-intake", 4,
            claims=[shadow_case], capacity=1, strategy="uniform", seed=seed)
    scored = workflow.receipt("demo-shadow")["receipt"]["score"]
    assert scored["model"] == reference[2]["version"] and scored["shadow"]["model"] == candidate["model"]
    checks["shadow_provenance"] = "pass"
    with workflow.transaction(write=False) as db:
        anchor = verify(db, verify_score=lifecycle.reference_verifier())
    restore_started = time.perf_counter()
    restored = output / "restored.sqlite3"
    with closing(sqlite3.connect(database)) as source, closing(sqlite3.connect(restored)) as destination:
        source.backup(destination)
    with Workflow(restored, lifecycle.scores).transaction(write=False) as db:
        assert verify(db, anchor, lifecycle.reference_verifier()) == anchor
    recovery_seconds = time.perf_counter() - restore_started
    checks["backup_restore"] = "pass"
    report = {
        "schema_version": 1, "scope": "synthetic", "seed": seed, "checks": checks, "anchor": anchor,
        "operations": workflow.overview(), "candidate": candidate, "recovery_seconds": recovery_seconds,
        "elapsed_seconds": time.perf_counter() - started,
        "process_rss_mb_at_finish": psutil.Process().memory_info().rss / 1_000_000,
        "disclaimer": "Reference hardware and isolated workload.",
    }
    write_json(output / "scenario.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/workflow-scenario"))
    parser.add_argument("--seed", type=int, default=5022)
    args = parser.parse_args()
    report = run(args.output, args.seed)
    print(f"Scenario complete: {report['anchor']['sequence']} events, {len(report['checks'])} checks.")


if __name__ == "__main__":
    main()
