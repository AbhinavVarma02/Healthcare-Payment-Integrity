"""Local FastAPI for research scorecards and analyst workflows."""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal, Self

import numpy as np
import pandas as pd
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .cohorts import FEATURES, SCHEMA
from .jobs import JobConflict, Jobs
from .models import Lookup, feature_frame, line_band
from .planning import Scenario, choose_count, choose_minutes, plan_summary, review_minutes
from .protocol import load_freeze
from .registry import Registry
from .replay import run as run_replay
from .storage import read_json

LOG = logging.getLogger("uvicorn.error").getChild("payment_integrity")
MAX_BODY = 256_000
MAX_BATCH = 500


def problem(status, code, message):
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)


class RequestLimits:
    def __init__(self, app):
        self.app = app
        self.slots = asyncio.Semaphore(12)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if self.slots.locked():
            await problem(503, "busy", "The local request limit was reached.")(scope, receive, send)
            return
        async with self.slots:
            if scope["method"] != "POST":
                await self.app(scope, receive, send)
                return
            body = bytearray()
            while True:
                try:
                    packet = await asyncio.wait_for(receive(), timeout=5)
                except TimeoutError:
                    await problem(408, "read_timeout", "Timed out reading request body.")(scope, receive, send)
                    return
                if packet["type"] == "http.disconnect":
                    return
                if len(body) + len(packet.get("body", b"")) > MAX_BODY:
                    await problem(413, "payload_limit", "Request body exceeds the local limit.")(
                        scope, receive, send)
                    return
                body.extend(packet.get("body", b""))
                if not packet.get("more_body"):
                    break
            replayed = False

            async def bounded_receive():
                nonlocal replayed
                if replayed:
                    return await receive()
                replayed = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}

            await self.app(scope, bounded_receive, send)


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True,
                             allow_inf_nan=False)


class Claim(Input):
    part: Literal["Part B", "DME"]
    provider_type: Annotated[str, Field(min_length=1, max_length=160)]
    visible_lines: Annotated[int, Field(ge=1, le=250)]
    provider_types: Annotated[int, Field(ge=1, le=50)]

    @model_validator(mode="after")
    def line_structure(self) -> Self:
        if self.provider_types > self.visible_lines:
            raise ValueError("Provider category count cannot exceed the visible line count.")
        return self


class Batch(Input):
    claims: Annotated[list[Claim], Field(min_length=1, max_length=MAX_BATCH)]


class FinancialScenario(Input):
    part_b_cents: Annotated[int, Field(ge=0, le=10_000_000)] = 10_000
    dme_cents: Annotated[int, Field(ge=0, le=10_000_000)] = 25_000
    relevant_percent: Annotated[int, Field(ge=0, le=100)] = 35
    review_cost_cents: Annotated[int, Field(ge=0, le=10_000_000)] = 3_000


class Plan(Batch):
    capacity: Annotated[int, Field(ge=0, le=MAX_BATCH)]
    strategy: Literal["uniform", "risk", "value", "value_per_minute", "time"] = "risk"
    group_cap: Annotated[int, Field(ge=0, le=MAX_BATCH)] | None = None
    exploration_count: Annotated[int, Field(ge=0, le=MAX_BATCH)] = 0
    seed: Annotated[int, Field(ge=0, le=2_147_483_647)] = 37301
    minute_budget: Annotated[int, Field(ge=0, le=30_000)] | None = None
    scenario: FinancialScenario = Field(default_factory=FinancialScenario)

    @model_validator(mode="after")
    def valid_plan(self) -> Self:
        if self.strategy == "time":
            if self.minute_budget is None or self.exploration_count or self.group_cap is not None:
                raise ValueError("Time optimization requires minutes and uses no count constraints.")
        elif self.capacity > len(self.claims) or self.exploration_count > self.capacity:
            raise ValueError("Review capacity or exploration reserve exceeds the candidate frame.")
        return self


class ReplayRequest(Input):
    seeds: Annotated[int, Field(ge=1, le=10)] = 1


def predictions(registry, claims):
    model, curve, meta = registry.active()
    frame = feature_frame(pd.DataFrame([claim.model_dump() for claim in claims], columns=FEATURES))
    raw = model.predict(frame)
    scored = curve.predict(raw)
    if not np.isfinite(scored).all() or np.any((scored < 0) | (scored > 1)):
        raise ValueError("Model returned invalid probabilities.")
    bands = line_band(frame["visible_lines"])
    estimates = []
    for i, claim in enumerate(claims):
        key = (claim.part, claim.provider_type)
        if isinstance(model, Lookup):
            parent = model.parts.get(claim.part, model.rate)
            group = model.providers.get(key, parent)
            subgroup = (*key, int(bands[i]))
            level = "line-band lookup" if subgroup in model.bands else (
                "provider-category lookup" if key in model.providers else "claim-part fallback")
            explanation = {"method": level, "part_raw_risk": parent, "provider_raw_risk": group,
                           "case_raw_risk": float(raw[i])}
            known = key in model.providers
        else:
            known = claim.provider_type in model.encoder.providers
            explanation = {"method": "encoded part, provider category and observed line features",
                           "case_raw_risk": float(raw[i])}
        estimates.append({
            "calibrated_risk": float(scored[i]), "feature_schema": SCHEMA, "model": meta["version"],
            "status": meta["status"], "provenance": meta["provenance"], "explanation": explanation,
            "input_support": "fitted category" if known else "rare or unseen category; fallback applies",
            "individual_interval": None,
        })
    return estimates


def create_app(workspace: Path | None = None, registry_root: Path | None = None, jobs_root: Path | None = None):
    workspace = workspace or Path.cwd()
    registry = Registry(registry_root or workspace / "artifacts" / "registry")

    def work(row, output, progress, cancelled):
        freeze = load_freeze(workspace, row["freeze"])
        result = run_replay(workspace, freeze, output, row["seeds_requested"], progress, cancelled)
        result["conclusions"] = {"status": "preview", "seeds": result["seeds"],
                                 "illustrative_components": result["conclusions"]["components"]}
        return result

    jobs = Jobs(jobs_root or workspace / "artifacts" / "jobs", work)

    @asynccontextmanager
    async def lifespan(_app):
        jobs.recover()
        try:
            yield
        finally:
            jobs.close()

    app = FastAPI(title="Healthcare Payment Integrity", version="1.0", lifespan=lifespan)
    app.add_middleware(RequestLimits)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]"])
    app.add_middleware(CORSMiddleware, allow_origins=[
        "http://127.0.0.1:5173", "http://localhost:5173",
        "http://127.0.0.1:4173", "http://localhost:4173",
    ], allow_methods=["GET", "POST"], allow_headers=["content-type"])

    @app.middleware("http")
    async def request_log(request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        route = request.scope.get("route")
        LOG.info("request method=%s route=%s status=%d ms=%.1f", request.method,
                 route.path if route else "unmatched", response.status_code,
                 1000 * (time.perf_counter() - started))
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid(_request: Request, _error):
        return problem(422, "invalid_input", "Input did not match the required request schema.")

    @app.exception_handler(JobConflict)
    async def busy(_request, _error):
        return problem(409, "replay_conflict", "A replay worker or job is currently unavailable.")

    def active_or_error():
        try:
            return registry.active()
        except (OSError, ValueError, KeyError, TypeError):
            return None

    @app.get("/health")
    def health():
        return {"status": "running", "scope": "local research"}

    @app.get("/ready")
    def ready():
        if active_or_error() is None:
            return problem(503, "model_unavailable", "No integrity-verified local scorecard is active.")
        return {"status": "research-only", "feature_schema": SCHEMA}

    @app.get("/v1/models")
    def models():
        return {"versions": registry.versions()}

    @app.get("/v1/models/active")
    def active():
        value = active_or_error()
        if value is None:
            return problem(503, "model_unavailable", "The local model is unavailable.")
        return value[2]

    def score_claims(claims):
        try:
            return predictions(registry, claims)
        except (OSError, ValueError, KeyError, TypeError):
            return None

    @app.post("/v1/score")
    def score(claim: Claim):
        scored = score_claims([claim])
        if scored is None:
            return problem(503, "model_unavailable", "The local model cannot score this request.")
        return scored[0]

    @app.post("/v1/score/batch")
    def score_batch(batch: Batch):
        scored = score_claims(batch.claims)
        if scored is None:
            return problem(503, "model_unavailable", "The local model cannot score this request.")
        return {"predictions": scored}

    @app.post("/v1/audit-plan")
    def planner(payload: Plan):
        scored = score_claims(payload.claims)
        if scored is None:
            return problem(503, "model_unavailable", "The local model cannot score this request.")
        risk = np.array([row["calibrated_risk"] for row in scored])
        parts = np.array([claim.part for claim in payload.claims])
        times = review_minutes([claim.visible_lines for claim in payload.claims])
        scenario = Scenario(**payload.scenario.model_dump())
        net = scenario.net(risk, scenario.exposures(parts))
        keys = np.arange(len(risk))
        if payload.strategy == "time":
            chosen, solver = choose_minutes(net, times, keys, payload.minute_budget or 0, exact=True)
            stats = plan_summary(chosen, parts, net, times, len(chosen))
            stats["unused_minutes"] = payload.minute_budget - stats["minutes"]
            explored = 0
        else:
            score_map = {"uniform": np.random.default_rng(payload.seed).random(len(risk)), "risk": risk,
                         "value": net, "value_per_minute": net / times}
            chosen, explored = choose_count(score_map[payload.strategy], keys, parts, payload.capacity,
                                            payload.group_cap, payload.exploration_count, payload.seed)
            stats = plan_summary(chosen, parts, net, times, payload.capacity)
            solver = {"status": "ranked", "gap": None}
        return {"summary": stats, "strategy": payload.strategy, "exploration_count": explored,
                "selected_input_positions": chosen.tolist(), "model": scored[0]["model"],
                "scope": "fictional scenario", "solver": solver}

    @app.post("/v1/replay", status_code=202)
    def replay(payload: ReplayRequest):
        value = active_or_error()
        if value is None:
            return problem(503, "model_unavailable", "A registered frozen study is required for replay.")
        return jobs.start(value[2]["provenance"]["freeze_commit"], payload.seeds)

    @app.get("/v1/runs/{job_id}")
    def run_status(job_id: str):
        try:
            return jobs.get(job_id)
        except FileNotFoundError:
            return problem(404, "run_not_found", "The local run does not exist.")

    @app.post("/v1/runs/{job_id}/cancel", status_code=202)
    def cancel_job(job_id: str):
        try:
            return jobs.cancel(job_id)
        except FileNotFoundError:
            return problem(404, "run_not_found", "The local run does not exist.")

    @app.post("/v1/runs/{job_id}/resume", status_code=202)
    def resume_job(job_id: str):
        try:
            return jobs.resume(job_id)
        except FileNotFoundError:
            return problem(404, "run_not_found", "The local run does not exist.")

    @app.get("/v1/validation/{version}")
    def validation(version: str):
        try:
            registry.load(version)
            return read_json(registry.root / version / "validation.json")
        except (OSError, ValueError, KeyError, TypeError):
            return problem(404, "validation_unavailable", "Verified validation evidence is unavailable.")

    return app
