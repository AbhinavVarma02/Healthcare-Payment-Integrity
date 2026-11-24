"""Read-only tools and bounded structured selection through an installed local model."""

import http.client
import json
import sqlite3
import threading
from hashlib import sha256
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field

from .contracts import Input
from .planning import Scenario
from .publication import APPROVED_STUDY
from .workflow_contracts import CaseID

TOOLS = Literal["risk", "policies", "budget", "validation", "drift", "report"]
MODELS = {"qwen2.5:1.5b"}
MODEL_LIMIT = threading.BoundedSemaphore(1)
QUESTIONS = {
    "explain this case risk": "risk",
    "show the score explanation": "risk",
    "compare review policies": "policies",
    "compare sampling approaches": "policies",
    "simulate a fictional budget": "budget",
    "calculate the scenario budget": "budget",
    "retrieve model validation": "validation",
    "show validation results": "validation",
    "summarize observed drift": "drift",
    "show the drift summary": "drift",
    "generate the research report": "report",
    "generate a structured report": "report",
}


class Risk(Input):
    tool: Literal["risk"]
    case_id: CaseID


class Policies(Input):
    tool: Literal["policies"]


class Budget(Input):
    tool: Literal["budget"]
    part: Literal["Part B", "DME"]
    risk_bps: Annotated[int, Field(ge=0, le=10_000)]
    exposure_cents: Annotated[int, Field(ge=0, le=10_000_000)]
    relevant_percent: Annotated[int, Field(ge=0, le=100)]
    review_cost_cents: Annotated[int, Field(ge=0, le=10_000_000)]


class Validation(Input):
    tool: Literal["validation"]


class Drift(Input):
    tool: Literal["drift"]
    source: Literal["historical", "synthetic"] = "historical"


class Report(Input):
    tool: Literal["report"]


ToolCall = Annotated[Risk | Policies | Budget | Validation | Drift | Report, Field(discriminator="tool")]


class Question(Input):
    question: Annotated[str, Field(min_length=1, max_length=140)]
    call: ToolCall
    mode: Literal["deterministic", "local-model"] = "deterministic"


class ModelChoice(Input):
    tool: TOOLS | Literal["abstain"]


def choose_with_ollama(model, question):
    if model not in MODELS or not MODEL_LIMIT.acquire(blocking=False):
        return None
    conn = http.client.HTTPConnection("127.0.0.1", 11434, timeout=8)
    try:
        payload = json.dumps({
            "model": model, "stream": False, "format": ModelChoice.model_json_schema(),
            "messages": [
                {"role": "system", "content": (
                    "Choose one action. risk explains a case score. policies compares review strategies. "
                    "budget calculates fictional amounts. validation retrieves validation results. "
                    "drift summarizes monitoring. report creates a research report. Otherwise abstain. "
                    "Respond only with the tool field." )},
                {"role": "user", "content": question},
            ],
            "options": {"temperature": 0, "num_ctx": 512, "num_predict": 32, "seed": 60721},
            "keep_alive": "30s",
        })
        conn.request("POST", "/api/chat", body=payload, headers={"Content-Type": "application/json"})
        response = conn.getresponse()
        if response.status != 200:
            return None
        raw = response.read(16_385)
        if len(raw) > 16_384:
            return None
        return ModelChoice.model_validate_json(json.loads(raw)["message"]["content"]).tool
    except (OSError, ValueError, KeyError, TypeError, http.client.HTTPException):
        return None
    finally:
        conn.close()
        MODEL_LIMIT.release()


class Assistant:
    def __init__(self, workspace: Path, workflow, model=None):
        self.study = workspace / "web" / "public" / "study.json"
        self.workflow = workflow
        self.model = model

    def ask(self, question, role):
        if role not in {"analyst", "supervisor"}:
            return {"status": "denied", "mode": "deterministic"}
        normalized = " ".join(question.question.casefold().split()).rstrip("?.")
        intent = QUESTIONS.get(normalized)
        if intent is None or intent != question.call.tool:
            return {"status": "abstain", "mode": "deterministic",
                    "message": "Choose a supported research, scenario or explanation request."}
        mode = "deterministic"
        selected = None
        if question.mode == "local-model":
            # Only approved phrases are passed to the model. Case data and all arguments stay local to tools.
            selected = choose_with_ollama(self.model, normalized) if self.model else None
            mode = "local-model" if selected == intent else "deterministic-fallback"
        result = self.evaluate(question.call, role)
        return {**result, "mode": mode, "model_selection": selected, "model": self.model if mode != "deterministic" else None}

    def evaluate(self, call, role):
        if role not in {"analyst", "supervisor"}:
            return {"status": "denied", "mode": "deterministic"}
        try:
            data, evidence, scope = self.run_tool(call)
        except (OSError, ValueError, KeyError, TypeError, sqlite3.DatabaseError):
            return {"status": "evidence_unavailable", "mode": "deterministic", "tool": call.tool}
        return {"status": "ok", "mode": "deterministic", "tool": call.tool, "scope": scope,
                "evidence": evidence, "data": data}

    def run_tool(self, call):
        if isinstance(call, Risk):
            if not self.workflow.path.is_file():
                raise ValueError("No demo receipt is available.")
            result = self.workflow.receipt(call.case_id)
            score = result["receipt"]["score"]
            return ({"risk": score["calibrated_risk"], "explanation": score["explanation"]},
                    {"receipt": result["digest"], "model": score["model"]}, "synthetic explanation")
        if isinstance(call, Budget):
            scenario = Scenario(call.exposure_cents, call.exposure_cents,
                                call.relevant_percent, call.review_cost_cents)
            net = int(scenario.net([call.risk_bps / 10_000], scenario.exposures([call.part]))[0])
            return {"net_cents": net, "assumptions": call.model_dump()}, {"formula": "scenario-net-v1"}, "fictional"
        if isinstance(call, Drift) and call.source == "synthetic":
            overview = self.workflow.overview() if self.workflow.path.is_file() else {"status": "no_data", "tick": 0}
            data = {key: overview.get(key) for key in ("status", "average_score", "unknown_category_rate", "alert")}
            return data, {"source": "synthetic workspace", "as_of": overview["tick"]}, "synthetic"
        source = self.study.read_bytes()
        if sha256(source).hexdigest() != APPROVED_STUDY:
            raise ValueError("Reviewed aggregate digest does not match.")
        study = json.loads(source)
        evidence = {"protocol": study["protocol"], "freeze": study["freeze_commit"],
                    "aggregate_sha256": APPROVED_STUDY}
        if isinstance(call, Policies):
            comparisons = [{
                "strategy": row["strategy"], "reviews": row["review_count"],
                "yield": row["metrics"]["yield_rate"], "cohort_rmse": row["metrics"]["ht_rmse"],
                "selected_only_rmse": row["metrics"]["naive_rmse"],
            } for row in study["replay"]["policies"]
                if row["year"] == 2025 and row["budget_percent"] == 5 and row["weight"] == "unweighted"]
            return ({"seeds": study["replay"]["seeds"], "conclusions": study["replay"]["conclusions"],
                     "year": 2025, "capacity_percent": 5, "policies": comparisons},
                    {**evidence, "run": "H3-sequential"}, "frozen historical replay")
        if isinstance(call, (Validation, Drift)):
            validation = study["validation"]
            data = validation if isinstance(call, Validation) else {
                "status": "observed" if validation["cohorts"] else "no_data",
                "cohorts": validation["cohorts"], "thresholds": validation["thresholds"],
            }
            return data, {**evidence, "model": validation["active"], "run": "Governance"}, "historical"
        return ({"cohorts": len(study["cohorts"]), "eligible_groups": sum(row["claims"] for row in study["cohorts"]),
                 "model": study["validation"]["active"], "H3": study["replay"]["conclusions"]["status"]},
                {**evidence, "runs": [row["run"] for row in study["ledger"]]}, "historical")
