"""Separate local state for experimental synthetic candidates, shadow and approval."""

import json
import time
from functools import cache
from hashlib import sha256 as bytes_sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from filelock import FileLock

from .cohorts import SCHEMA
from .learning import fit_candidate, passed
from .model_io import save_scorecard
from .receipts import verify
from .registry import Registry
from .storage import read_json, sha256, write_json
from .workflow import digest, require

INITIAL: dict = {"schema": 1, "generation": 0, "active": None, "previous": None, "shadow": None, "history": []}


class Lifecycle:
    def __init__(self, root: Path, reference, predict, errors):
        self.root = root
        self.registry = Registry(root / "candidates")
        self.reference = reference
        self.predict = predict
        self.errors = errors

    @property
    def pointer(self):
        return self.root / "lifecycle.json"

    def state(self):
        state = read_json(self.pointer) if self.pointer.exists() else INITIAL
        require(state.get("schema") == 1, "invalid_lifecycle", "Unsupported lifecycle state.", 503)
        return state

    def candidate(self, version):
        _, _, metadata = self.registry.load(version)
        source = (self.registry.root / version / "validation.json").read_bytes()
        require(bytes_sha256(source).hexdigest() == metadata["validation_sha256"],
                "candidate_integrity", "Candidate validation digest does not match.", 503)
        report = json.loads(source)
        require(metadata["provenance"].get("scope") == "synthetic" and report.get("scope") == "synthetic"
                and report.get("feature_schema") == SCHEMA
                and report.get("schema") == 1 and report.get("latest_label", -1) <= report.get("cutoff", -2),
                "candidate_integrity", "Candidate provenance or validation scope is invalid.", 503)
        return {"model": version, "artifact_sha256": metadata["scorecard_sha256"],
                "report_sha256": metadata["validation_sha256"], "report": report}

    def install(self, model, curve, report, provenance):
        self.root.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=self.root) as temporary:
            source = Path(temporary)
            save_scorecard(source, model, curve)
            artifact = sha256(source / "scorecard.json")
            version = "demo-" + digest({"artifact": artifact, "report": report, "data": provenance})[:24]
            self.registry.install(version, source, artifact, report, {**provenance, "scope": "synthetic"})
            return self.candidate(version)

    def train(self, workflow, cutoff, mode):
        feedback, data_sha = workflow.feedback(cutoff, verify_score=self.reference_verifier())
        try:
            reference = self.reference.active()
            model, curve, report = fit_candidate(reference, feedback, cutoff, mode)
        except self.errors as error:
            raise ValueError("Candidate training failed with insufficient or incompatible local evidence.") from error
        return self.install(model, curve, report, {
            "model_id": mode, "reference": reference[2]["version"], "feedback_sha256": data_sha,
            "training_cutoff": cutoff, "code_sha256": sha256(Path(__file__).with_name("learning.py")),
            "weighting": "unweighted selection-conditioned synthetic feedback",
        })

    def status(self):
        state = self.state()
        versions = []
        for version in self.registry.versions()[-20:]:
            try:
                versions.append(self.candidate(version))
            except self.errors:
                versions.append({"model": version, "status": "unavailable"})
        return {**state, "candidates": versions, "scope": "synthetic operation"}

    def change(self, workflow, action, role, authorization):
        required = {"shadow": "operator", "promote": "supervisor", "rollback": "supervisor"}
        require(role == required.get(action), "role_denied", "This demo role cannot change the lifecycle.", 403)
        self.root.mkdir(parents=True, exist_ok=True)
        with FileLock(self.root / ".lifecycle-lock", timeout=2), workflow.transaction(write=False) as db:
            verification = verify(db, verify_score=None if action == "rollback" else self.reference_verifier())
            old = self.state()
            require(authorization.generation == old["generation"], "stale_approval",
                    "Refresh lifecycle evidence before changing this state.")
            candidate = None
            if action != "rollback":
                candidate = self.candidate(authorization.model)
                require(candidate["artifact_sha256"] == authorization.artifact_sha256
                        and candidate["report_sha256"] == authorization.report_sha256,
                        "stale_approval", "Approval does not match the recorded artifact and report.")
            new = {**old, "generation": old["generation"] + 1}
            if action == "shadow":
                require(old["active"] != authorization.model, "already_active", "Choose a separate challenger.")
                new["shadow"] = authorization.model
            elif action == "promote":
                require(candidate is not None and passed(candidate["report"]) and old["shadow"] == authorization.model,
                        "promotion_rejected", "The candidate must be in shadow and pass every validation gate.")
                new.update(active=authorization.model, previous=old["active"], shadow=None)
            else:
                require(old["active"] is not None, "rollback_unavailable", "No synthetic activation can be reversed.")
                require(authorization.model == old["active"], "stale_approval",
                        "Rollback request does not identify the active synthetic model.")
                if old["previous"]:
                    self.candidate(old["previous"])
                else:
                    self.reference.active()
                new.update(active=old["previous"], previous=None, shadow=None)
            link = {"generation": new["generation"], "action": action, "role": role,
                    "model": authorization.model, "authorization": authorization.model_dump(),
                    "reason": authorization.reason, "workflow_anchor": verification}
            new["history"] = [*old["history"][-49:], link]
            write_json(self.pointer, new)
        return new

    def reference_verifier(self):
        @cache
        def evidence(version):
            registry = self.registry if version.startswith("demo-") else self.reference
            return registry.load(version)[2]

        def verify_scores(_claims, scores):
            for score in scores:
                model = evidence(score["model"])
                require(model["scorecard_sha256"] == score["scorecard_sha256"]
                        and model["validation_sha256"] == score["validation_sha256"],
                        "candidate_integrity", "A recorded model reference failed verification.", 503)
                shadow = score.get("shadow", {})
                if shadow.get("status") == "scored":
                    challenger = evidence(shadow["model"])
                    require(challenger["scorecard_sha256"] == shadow["artifact_sha256"]
                            and challenger["validation_sha256"] == shadow["report_sha256"],
                            "candidate_integrity", "A shadow model reference failed verification.", 503)

        return verify_scores

    def scores(self, claims):
        try:
            baseline = self.predict(self.reference, claims)
        except self.errors:
            return None
        try:
            state = self.state()
            active = state["active"]
            shadow = state["shadow"]
        except self.errors:
            return [{**row, "synthetic_lifecycle": "fallback_to_reference"} for row in baseline]
        selected = baseline
        if active:
            selected = [{**row, "synthetic_lifecycle": "fallback_to_reference"} for row in baseline]
            for version in (active, state["previous"]):
                if not version:
                    break
                try:
                    self.candidate(version)
                    candidate = self.predict(self.registry, claims, version=version)
                    status = "synthetic-active" if version == active else "synthetic-fallback"
                    selected = [{**row, "status": status, "reference_risk": old["calibrated_risk"]}
                                for row, old in zip(candidate, baseline, strict=True)]
                    break
                except self.errors:
                    continue
        if not shadow:
            return selected
        started = time.perf_counter()
        try:
            self.candidate(shadow)
            alternate = self.predict(self.registry, claims, version=shadow)
            latency = 1000 * (time.perf_counter() - started)
            return [{**row, "shadow": {"status": "scored", "batch_latency_ms": latency,
                                      "model": other["model"], "artifact_sha256": other["scorecard_sha256"],
                                      "report_sha256": other["validation_sha256"],
                                      "risk": other["calibrated_risk"]}}
                    for row, other in zip(selected, alternate, strict=True)]
        except self.errors:
            return [{**row, "shadow": {"status": "unavailable", "model": shadow}} for row in selected]
