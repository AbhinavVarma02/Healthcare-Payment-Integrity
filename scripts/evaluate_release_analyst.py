"""Run the release deterministic analyst corpus against audited and fictional evidence."""

import argparse
import shutil
import time
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory

from pydantic import ValidationError

from payment_integrity.assistant import Assistant, Question
from payment_integrity.storage import read_json, sha256, write_json
from payment_integrity.workflow import Workflow
from payment_integrity.workflow_contracts import Intake

MANIFEST = Path("tests/fixtures/analyst-release-v1.json")
MISSING = object()


def read_path(reply, path):
    for key in path:
        try:
            reply = reply[key]
        except (KeyError, IndexError, TypeError):
            return MISSING
    return reply


def scenario_checks(scenario, reply):
    status = scenario["status"]
    expected = scenario.get("checks", [])
    checks = {"status": reply["status"] == status}
    for group in ("numeric", "scope", "tool", "source"):
        criteria = [item for item in expected if item["group"] == group]
        if criteria:
            checks[group] = all(read_path(reply, item["path"]) == item["value"] for item in criteria)
    if status != "ok":
        checks["no_unverified_data"] = "data" not in reply and "evidence" not in reply
    return checks


def run(output):
    corpus = read_json(MANIFEST)
    scenarios = corpus["scenarios"]
    if len({item["id"] for item in scenarios}) != len(scenarios):
        raise ValueError("Scenario IDs must be unique.")
    with TemporaryDirectory(dir=output.parent) as folder:
        root = Path(folder)
        source = Path("web/public/study.json")
        trusted = root / "approved/web/public"
        trusted.mkdir(parents=True)
        shutil.copyfile(source, trusted / "study.json")
        changed = root / "changed/web/public"
        changed.mkdir(parents=True)
        (changed / "study.json").write_bytes(source.read_bytes() + b"\n")
        workflow = Workflow(root / "review.sqlite3", lambda claims: [
            {"calibrated_risk": 0.25, "model": "release-fixture", "explanation": {"method": "fixture"}}
            for _ in claims
        ])
        intake = workflow.dispatch("intake", Intake(event_id="intake", idempotency_key="intake",
            run_id="release", event_tick=0, capacity=1, seed=31, claims=[
                {"case_id": "demo-release", "part": "DME", "provider_type": "Pharmacy",
                 "visible_lines": 1, "provider_types": 1},
            ]), "analyst")
        receipt = intake["receipt_digests"]["demo-release"]
        empty = Workflow(root / "empty.sqlite3", workflow.scorer)
        contexts = {
            "approved": Assistant(root / "approved", workflow),
            "changed": Assistant(root / "changed", workflow),
            "missing": Assistant(root / "missing", workflow),
            "empty": Assistant(root / "approved", empty),
        }
        rows = []
        for scenario in scenarios:
            assistant = contexts[scenario.get("context", "approved")]
            started = time.perf_counter()
            try:
                question = Question.model_validate(scenario["input"])
                reply = assistant.ask(question, scenario.get("role", "analyst"))
            except ValidationError:
                reply = {"status": "invalid"}
            elapsed = (time.perf_counter() - started) * 1000
            checks = scenario_checks(scenario, reply)
            if scenario.get("receipt_fixture"):
                checks["source"] = checks.get("source", True) and read_path(reply, ["evidence", "receipt"]) == receipt
            rows.append({"id": scenario["id"], "category": scenario["category"], "status": reply["status"],
                         "mode": "deterministic", "checks": checks, "passed": all(checks.values()),
                         "critical": scenario.get("critical", False), "latency_ms": elapsed})
    result = {
        "schema_version": 1, "corpus_sha256": sha256(MANIFEST), "mode": "deterministic",
        "approved_study_sha256": sha256(source), "scenarios": rows,
        "scenario_counts": dict(Counter(row["category"] for row in rows)),
        "passed": sum(row["passed"] for row in rows),
        "critical_failures": sum(row["critical"] and not row["passed"] for row in rows),
        "failure_counts": dict(Counter(name for row in rows for name, passed in row["checks"].items() if not passed)),
    }
    write_json(output, result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/assistant/release-v1.json"))
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result = run(args.output)
    count = len(result["scenarios"])
    print(f"Deterministic analyst: {result['passed']}/{count}, {result['critical_failures']} critical failures.")
    if result["passed"] != count:
        for row in result["scenarios"]:
            if not row["passed"]:
                print(row["id"], {name: passed for name, passed in row["checks"].items() if not passed})
        raise SystemExit(1)


if __name__ == "__main__":
    main()
