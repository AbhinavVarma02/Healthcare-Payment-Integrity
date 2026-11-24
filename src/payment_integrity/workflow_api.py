"""Loopback-only routes for the fictional operations workspace."""

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Body, Query

from .receipts import verify
from .workflow import WorkflowError
from .workflow_contracts import (
    COMMANDS,
    Assign,
    Authorization,
    CaseID,
    Clock,
    Close,
    Correction,
    Intake,
    Override,
    Role,
    Submit,
    Tick,
    Token,
    Train,
)

Command = Annotated[Intake | Assign | Submit | Close | Correction | Override | Clock, Body()]


def workflow_router(workflow, lifecycle, telemetry, problem):
    router = APIRouter(prefix="/v1/operations", tags=["Synthetic operations"])

    def local(action, *args):
        try:
            return action(*args)
        except WorkflowError as error:
            return problem(error.status, error.code, str(error))
        except (sqlite3.DatabaseError, ValueError, KeyError, TypeError):
            return problem(503, "operations_unavailable", "Local operations state could not be verified.")

    @router.post("/events/{kind}")
    def submit(kind: Token, role: Annotated[Role, Query()], command: Command):
        if type(command) is not COMMANDS.get(kind):
            return problem(422, "command_mismatch", "This payload does not match the requested workflow action.")
        return local(workflow.dispatch, kind, command, role)

    @router.get("/runs/{run_id}/cases")
    def cases(run_id: Token, as_of: Tick | None = None):
        return local(workflow.cases, run_id, as_of)

    @router.get("/runs/{run_id}/estimate")
    def estimate(run_id: Token):
        return local(workflow.run_estimate, run_id)

    @router.get("/overview")
    def overview():
        def read():
            return {**workflow.overview(), "requests": telemetry.snapshot()}

        return local(read)

    @router.get("/runs/{run_id}/trace")
    def trace(run_id: Token):
        return local(workflow.trace, run_id)

    @router.get("/integrity")
    def integrity():
        def read():
            with workflow.transaction(write=False) as db:
                return verify(db, verify_score=lifecycle.reference_verifier())

        return local(read)

    @router.get("/receipts/{case_id}")
    def receipt(case_id: CaseID, as_of: Tick | None = None):
        return local(workflow.receipt, case_id, as_of)

    @router.get("/lifecycle")
    def status():
        return local(lifecycle.status)

    @router.post("/lifecycle/train")
    def train(command: Train, role: Annotated[Role, Query()]):
        if role != "operator":
            return problem(403, "role_denied", "This demo role cannot train a candidate.")
        try:
            return lifecycle.train(workflow, command.cutoff, command.mode)
        except WorkflowError as error:
            return problem(error.status, error.code, str(error))
        except ValueError as error:
            return problem(422, "candidate_training_failed", str(error))
        except (OSError, sqlite3.DatabaseError):
            return problem(503, "candidate_unavailable", "Local training artifacts are unavailable.")

    @router.post("/lifecycle/{action}")
    def change(action: Token, command: Authorization, role: Annotated[Role, Query()]):
        return local(lifecycle.change, workflow, action, role, command)

    return router
