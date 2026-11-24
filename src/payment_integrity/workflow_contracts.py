"""Typed commands for the synthetic review workspace."""

from typing import Annotated, Literal

from pydantic import Field

from .contracts import Claim, Input

Role = Literal["analyst", "reviewer", "supervisor", "operator"]
Tick = Annotated[int, Field(ge=0, le=1_000_000)]
Token = Annotated[str, Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")]
CaseID = Annotated[str, Field(pattern=r"^demo-[a-zA-Z0-9][a-zA-Z0-9_-]{0,57}$")]
Strategy = Literal["uniform", "greedy", "hybrid-5", "hybrid-10", "hybrid-20"]
Note = Literal["documentation", "coding", "eligibility", "other"]
Finding = Literal["agree", "disagree"]


class Event(Input):
    schema_version: Literal[1] = 1
    source: Literal["synthetic"] = "synthetic"
    event_id: Token
    run_id: Token
    idempotency_key: Token
    event_tick: Tick


class DemoClaim(Claim):
    case_id: CaseID
    provider_type: Annotated[str, Field(pattern=r"^[A-Za-z][A-Za-z &-]{0,59}$")]


class Intake(Event):
    claims: Annotated[list[DemoClaim], Field(min_length=1, max_length=100)]
    capacity: Annotated[int, Field(ge=0, le=100)]
    seed: Annotated[int, Field(ge=0, le=2_147_483_647)]
    strategy: Strategy = "hybrid-10"


class CaseEvent(Event):
    case_id: CaseID


class Assign(CaseEvent):
    reviewer: Literal["reviewer-a", "reviewer-b"]


class Close(CaseEvent):
    pass


class Submit(CaseEvent):
    finding: Finding
    note: Note
    available_tick: Tick


class Correction(Submit):
    replaces: Annotated[int, Field(ge=1, le=1_000)]
    reason: Literal["source_revision", "clerical_error"]


class Override(CaseEvent):
    replacement: CaseID
    reason: Literal["priority_change", "reviewer_capacity"]


class Clock(Event):
    advance_to: Tick


COMMANDS = {
    "intake": Intake, "assign": Assign, "submit": Submit, "close": Close,
    "correct": Correction, "override": Override, "advance": Clock,
}
ROLES = {
    "intake": "analyst", "assign": "reviewer", "submit": "reviewer", "close": "reviewer",
    "correct": "supervisor", "override": "supervisor", "advance": "operator",
}

Hash = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class Train(Input):
    cutoff: Tick
    mode: Literal["recalibrate", "retrain"]


class Authorization(Input):
    generation: Annotated[int, Field(ge=0)]
    model: Token
    artifact_sha256: Hash | None = None
    report_sha256: Hash | None = None
    reason: Literal["evaluate", "reviewed_evidence", "restore_reference"]
