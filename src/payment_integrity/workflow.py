"""Transactional synthetic review state. Historical outcomes never enter this store."""

import hashlib
import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

import numpy as np

from .learning import Feedback
from .metrics import ranked
from .sampling import estimate, select
from .telemetry import percentiles
from .workflow_contracts import (
    COMMANDS,
    ROLES,
    Assign,
    CaseEvent,
    Clock,
    Close,
    Correction,
    Event,
    Intake,
    Override,
    Submit,
)

MAX_CASES = 2_000
MAX_EVENTS = 10_000
QUARANTINE_LIMIT = 200
QUARANTINE = """CREATE TABLE rejections (
    seq INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, code TEXT NOT NULL,
    tick INTEGER NOT NULL, retryable INTEGER NOT NULL
)"""
SCHEMA = (
    "CREATE TABLE clock (id INTEGER PRIMARY KEY CHECK(id=1), tick INTEGER NOT NULL)",
    "INSERT INTO clock VALUES (1, 0)",
    """CREATE TABLE events (
        seq INTEGER PRIMARY KEY, event_id TEXT NOT NULL UNIQUE, idem TEXT NOT NULL UNIQUE,
        run_id TEXT NOT NULL, kind TEXT NOT NULL, tick INTEGER NOT NULL,
        envelope TEXT NOT NULL, previous TEXT NOT NULL, digest TEXT NOT NULL,
        result TEXT NOT NULL, latency_ms REAL NOT NULL
    )""",
    """CREATE TABLE runs (
        id TEXT PRIMARY KEY, intake_seq INTEGER NOT NULL REFERENCES events(seq),
        plan TEXT NOT NULL, overridden INTEGER NOT NULL DEFAULT 0
    )""",
    """CREATE TABLE cases (
        id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id),
        receipt TEXT NOT NULL, digest TEXT NOT NULL, state TEXT NOT NULL,
        reviewer TEXT, last_tick INTEGER NOT NULL
    )""",
    """CREATE TABLE outcomes (
        case_id TEXT NOT NULL REFERENCES cases(id), version INTEGER NOT NULL,
        event_seq INTEGER NOT NULL REFERENCES events(seq), available INTEGER NOT NULL,
        finding TEXT NOT NULL, note TEXT NOT NULL, PRIMARY KEY(case_id, version)
    )""",
    "CREATE INDEX cases_by_run ON cases(run_id, id)",
    "CREATE INDEX events_by_run ON events(run_id, seq)",
)


class WorkflowError(ValueError):
    def __init__(self, code, message, status=409):
        super().__init__(message)
        self.code, self.status = code, status


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def require(condition, code, message, status=409):
    if not condition:
        raise WorkflowError(code, message, status)


def design(scores, ids, budget, strategy, seed):
    order = ranked(np.asarray(scores), np.asarray(ids))
    sample = select(scores, ids, budget, strategy, np.random.default_rng(seed), order=order)
    targeted = 0
    if 0 < budget < len(ids) and strategy != "uniform":
        targeted = budget - sample.strata[-1][1]
    certainty = set(order[:targeted].tolist())
    selected = sample.indices.tolist()
    tail_population, tail_draws = sample.strata[-1]
    return selected, [
        [1, 1] if position in certainty else [tail_draws, tail_population]
        for position in range(len(ids))
    ], sample.strata, targeted


class Workflow:
    def __init__(self, path: Path, scorer):
        self.path = path
        self.scorer = scorer

    @contextmanager
    def transaction(self, *, write=True):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=2, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("BEGIN IMMEDIATE")
            version = db.execute("PRAGMA user_version").fetchone()[0]
            require(version in (0, 1, 2), "incompatible_store", "Unsupported workflow database schema.", 503)
            if version == 0:
                for statement in SCHEMA:
                    db.execute(statement)
            if version < 2:
                db.execute(QUARANTINE)
                db.execute("PRAGMA user_version=2")
            if not write:
                db.execute("PRAGMA query_only=ON")
            yield db
            db.commit()
        finally:
            db.close()

    @staticmethod
    def now(db):
        return db.execute("SELECT tick FROM clock WHERE id=1").fetchone()[0]

    def dispatch(self, kind, event: Event, role):
        started = time.perf_counter()
        try:
            require(role == ROLES.get(kind), "role_denied", "This demo role cannot perform the action.", 403)
            require(type(event) is COMMANDS.get(kind), "command_mismatch", "Unexpected workflow command.", 422)
            with self.transaction() as db:
                return self.record(db, kind, event, role, started)
        except WorkflowError as error:
            # Report rejection metadata separately from accepted effects and never retain a rejected payload.
            if kind in COMMANDS and error.code != "incompatible_store":
                try:
                    with self.transaction() as db:
                        current = self.now(db)
                        saved = db.execute("INSERT INTO rejections (kind,code,tick,retryable) VALUES (?,?,?,?)",
                                           (kind, error.code, current, int(error.status in {429, 503})))
                        db.execute("DELETE FROM rejections WHERE seq<=?", ((saved.lastrowid or 0) - QUARANTINE_LIMIT,))
                except (sqlite3.DatabaseError, OSError):
                    pass
            raise

    def record(self, db, kind, event, role, started):
        payload = event.model_dump(mode="json")
        envelope = {"actor_role": role, "kind": kind, "payload_sha256": digest(payload), **payload}
        old = db.execute(
            "SELECT seq,envelope,result,digest FROM events WHERE event_id=? OR idem=?",
            (event.event_id, event.idempotency_key),
        ).fetchall()
        if old:
            saved = json.loads(old[0]["envelope"])
            saved.pop("recorded_tick", None)
            require(len(old) == 1 and saved == envelope,
                    "event_conflict", "Event ID or idempotency key was reused with different content.")
            return {**json.loads(old[0]["result"]), "event_seq": old[0]["seq"], "event_digest": old[0]["digest"]}
        current = self.now(db)
        require(event.event_tick <= current, "future_event", "Advance the simulation clock first.")
        envelope["recorded_tick"] = current
        tail = db.execute("SELECT seq,digest FROM events ORDER BY seq DESC LIMIT 1").fetchone()
        seq, previous = (tail["seq"] + 1, tail["digest"]) if tail else (1, "0" * 64)
        require(seq <= MAX_EVENTS, "event_limit", "The local event store is full.", 429)
        # Reserve the sequence so projections can reference it within the same transaction.
        db.execute("""INSERT INTO events
                   (seq,event_id,idem,run_id,kind,tick,envelope,previous,digest,result,latency_ms)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                   (seq, event.event_id, event.idempotency_key, event.run_id, kind, event.event_tick,
                    canonical(envelope), previous, "", "", 0))
        if isinstance(event, Intake):
            result = self.intake(db, event, seq, envelope["payload_sha256"])
        elif isinstance(event, Clock):
            require(event.event_tick == current and event.advance_to > current, "invalid_clock",
                    "Clock advancement requires current event time and a later target.")
            db.execute("UPDATE clock SET tick=? WHERE id=1", (event.advance_to,))
            result = {"tick": event.advance_to}
        elif isinstance(event, CaseEvent):
            result = self.review(db, event, seq, current)
        else:
            raise ValueError("Unsupported workflow event.")
        link = digest({"seq": seq, "previous": previous, "envelope": envelope, "result": result})
        db.execute("UPDATE events SET digest=?,result=?,latency_ms=? WHERE seq=?",
                   (link, canonical(result), 1000 * (time.perf_counter() - started), seq))
        return {**result, "event_seq": seq, "event_digest": link}

    def intake(self, db, event: Intake, seq, input_digest):
        ids = [claim.case_id for claim in event.claims]
        require(len(set(ids)) == len(ids), "duplicate_case", "A batch must contain distinct demo cases.", 422)
        require(event.capacity <= len(ids), "infeasible_capacity", "Capacity exceeds candidate count.", 422)
        require(db.execute("SELECT COUNT(*) FROM cases").fetchone()[0] + len(ids) <= MAX_CASES,
                "queue_limit", "The local case limit was reached.", 429)
        require(not db.execute("SELECT 1 FROM runs WHERE id=?", (event.run_id,)).fetchone(),
                "run_exists", "Use a distinct run ID for each intake batch.")
        slots = ",".join("?" for _ in ids)
        require(not db.execute(f"SELECT 1 FROM cases WHERE id IN ({slots})", ids).fetchone(),
                "case_exists", "A demo case is already registered.")
        scores = self.scorer(event.claims)
        require(scores is not None, "model_unavailable", "The verified reference model is unavailable.", 503)
        selected, probabilities, strata, targeted = design(
            [score["calibrated_risk"] for score in scores], ids, event.capacity, event.strategy, event.seed,
        )
        config = {"strategy": event.strategy, "seed": event.seed, "capacity": event.capacity,
                  "tie_break": "case_id", "minimum_exploration": 1, "algorithm": "targeted-then-srswor-v1"}
        plan = {**config, "config_sha256": digest(config),
                "design": "targeted-then-srswor-v1", "population": len(ids),
                "strata": [list(row) for row in strata], "targeted": targeted, "selected": [ids[i] for i in selected]}
        db.execute("INSERT INTO runs (id,intake_seq,plan) VALUES (?,?,?)", (event.run_id, seq, canonical(plan)))
        positions = {index: rank for rank, index in enumerate(selected)}
        receipts = {}
        for i, case_id in enumerate(ids):
            position = positions.get(i)
            state = "queued" if position is not None else "unselected"
            count, size = probabilities[i]
            snapshot = event.claims[i].model_dump(exclude={"case_id"})
            receipt = {
                "schema_version": 1, "case_id": case_id, "run_id": event.run_id, "source": "synthetic",
                "intake_event": event.event_id, "intake_seq": seq, "event_tick": event.event_tick,
                "available_tick": self.now(db), "input_sha256": input_digest,
                "snapshot_sha256": digest(snapshot), "score": scores[i], "plan_sha256": digest(plan),
                "decision": {"reason": "unselected" if position is None else (
                    "targeted" if position < targeted else "census" if count == size else "random"),
                    "selected": position is not None, "position": position,
                    "probability": {"status": "known" if count else "zero",
                                    "numerator": count, "denominator": size}},
            }
            receipts[case_id] = digest(receipt)
            db.execute("INSERT INTO cases VALUES (?,?,?,?,?,NULL,?)",
                       (case_id, event.run_id, canonical(receipt), receipts[case_id], state, event.event_tick))
        return {"run_id": event.run_id, "intake": plan, "receipt_digests": receipts}

    def review(self, db, event, seq, current):
        case = db.execute("SELECT * FROM cases WHERE id=? AND run_id=?",
                          (event.case_id, event.run_id)).fetchone()
        require(case is not None, "unknown_case", "The demo case does not belong to this run.", 404)
        require(case["last_tick"] <= event.event_tick, "out_of_order", "The event predates this case history.")
        result = {"case_id": event.case_id}
        if isinstance(event, Assign):
            require(case["state"] == "queued", "invalid_transition", "Only a queued case can be assigned.")
            db.execute("UPDATE cases SET reviewer=? WHERE id=?", (event.reviewer, event.case_id))
            state = "assigned"
        elif isinstance(event, Override):
            require(case["state"] == "queued", "invalid_transition", "Only an unassigned review can be swapped.")
            other = db.execute("SELECT * FROM cases WHERE id=? AND run_id=?",
                               (event.replacement, event.run_id)).fetchone()
            require(other is not None and other["state"] == "unselected"
                    and other["last_tick"] <= event.event_tick,
                    "invalid_override", "Replacement must be an eligible unselected case in the same run.")
            db.execute("UPDATE cases SET state='queued',last_tick=? WHERE id=?", (event.event_tick, event.replacement))
            db.execute("UPDATE runs SET overridden=1 WHERE id=?", (event.run_id,))
            result.update(replacement=event.replacement, probability_status="invalid_after_intervention")
            state = "removed"
        elif isinstance(event, Close):
            require(case["state"] == "submitted" and self.revealed(db, event.case_id, current),
                    "invalid_transition", "Close a review after its finding is available.")
            state = "closed"
        elif isinstance(event, Submit):
            require(event.available_tick >= max(current, event.event_tick), "invalid_availability",
                    "A finding must become available on or after submission.")
            latest = db.execute("SELECT version,available FROM outcomes WHERE case_id=? ORDER BY version DESC LIMIT 1",
                                (event.case_id,)).fetchone()
            if isinstance(event, Correction):
                require(latest is not None and latest["available"] <= current and latest["version"] == event.replaces,
                        "invalid_correction", "Correct the latest revealed finding version.")
                version = latest["version"] + 1
            else:
                require(case["state"] == "assigned" and latest is None, "invalid_transition",
                        "Only an assigned case without a finding can be submitted.")
                version = 1
            db.execute("INSERT INTO outcomes VALUES (?,?,?,?,?,?)",
                       (event.case_id, version, seq, event.available_tick, event.finding, event.note))
            result.update(version=version, available_tick=event.available_tick)
            state = "closed" if case["state"] == "closed" else "submitted"
        else:
            raise ValueError("Unsupported review event.")
        db.execute("UPDATE cases SET state=?,last_tick=? WHERE id=?", (state, event.event_tick, event.case_id))
        return {**result, "state": state}

    @staticmethod
    def revealed(db, case_id, cutoff):
        return [dict(item) for item in db.execute(
            """SELECT version,event_seq,available,finding,note FROM outcomes
               WHERE case_id=? AND available<=? ORDER BY version""", (case_id, cutoff),
        )]

    def cases(self, run_id, cutoff=None):
        with self.transaction(write=False) as db:
            now = self.now(db)
            cutoff = now if cutoff is None else cutoff
            require(0 <= cutoff <= now, "invalid_cutoff", "Cutoff is outside the simulation clock.", 422)
            result = []
            for item in db.execute("SELECT * FROM cases WHERE run_id=? ORDER BY id", (run_id,)):
                outcomes = self.revealed(db, item["id"], cutoff)
                receipt = json.loads(item["receipt"])
                if receipt["available_tick"] > cutoff:
                    continue
                state, reviewer = self.case_state(db, receipt, cutoff)
                if state == "submitted":
                    state = "reviewed" if outcomes else "pending"
                result.append({"case_id": item["id"], "state": state, "reviewer": reviewer,
                               "finding": outcomes[-1] if outcomes else None})
            return {"tick": now, "as_of": cutoff, "run_id": run_id, "cases": result}

    def receipt(self, case_id, cutoff=None):
        with self.transaction(write=False) as db:
            return self.read_receipt(db, case_id, cutoff)

    def read_receipt(self, db, case_id, cutoff=None):
        now = self.now(db)
        cutoff = now if cutoff is None else cutoff
        require(0 <= cutoff <= now, "invalid_cutoff", "Cutoff is outside the simulation clock.", 422)
        item = db.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
        require(item is not None, "unknown_case", "The demo case does not exist.", 404)
        receipt = json.loads(item["receipt"])
        intake = db.execute("SELECT result,digest FROM events WHERE seq=?", (receipt["intake_seq"],)).fetchone()
        require(digest(receipt) == item["digest"] and intake is not None
                and json.loads(intake["result"])["receipt_digests"].get(case_id) == item["digest"],
                "receipt_integrity", "Receipt integrity check failed.", 503)
        require(receipt["available_tick"] <= cutoff, "case_not_available", "Case intake follows the cutoff.", 404)
        run = db.execute("SELECT plan,overridden FROM runs WHERE id=?", (item["run_id"],)).fetchone()
        plan = json.loads(run["plan"])
        require(digest(plan) == receipt["plan_sha256"], "receipt_integrity", "Allocation integrity check failed.", 503)
        outcomes = self.revealed(db, case_id, cutoff)
        history, overridden = [], False
        for row in db.execute("SELECT * FROM events WHERE run_id=? AND tick<=? ORDER BY seq",
                              (item["run_id"], cutoff)):
            if json.loads(row["envelope"])["recorded_tick"] > cutoff:
                continue
            overridden |= row["kind"] == "override"
            data = json.loads(row["result"])
            if case_id in {data.get("case_id"), data.get("replacement")}:
                history.append({"seq": row["seq"], "kind": row["kind"], "tick": row["tick"],
                                "digest": row["digest"]})
        return {"receipt": receipt, "digest": item["digest"], "plan": plan, "outcomes": outcomes,
                "history": history, "as_of": cutoff, "intake_event_digest": intake["digest"],
                "design_status": "intervened" if overridden else "original"}

    @staticmethod
    def case_state(db, receipt, cutoff):
        state = "queued" if receipt["decision"]["selected"] else "unselected"
        reviewer = None
        for event in db.execute("SELECT envelope,result FROM events WHERE run_id=? AND tick<=? ORDER BY seq",
                                (receipt["run_id"], cutoff)):
            envelope = json.loads(event["envelope"])
            if envelope["recorded_tick"] > cutoff:
                continue
            result = json.loads(event["result"])
            if result.get("case_id") == receipt["case_id"]:
                state = result["state"]
                reviewer = envelope.get("reviewer", reviewer)
            if result.get("replacement") == receipt["case_id"]:
                state = "queued"
        return state, reviewer

    def run_estimate(self, run_id):
        with self.transaction(write=False) as db:
            row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
            require(row is not None, "unknown_run", "The demo run does not exist.", 404)
            plan = json.loads(row["plan"])
            if row["overridden"]:
                return {"status": "intervention", "estimate": None}
            outcomes = [self.revealed(db, case, self.now(db)) for case in plan["selected"]]
            if not all(outcomes):
                return {"status": "incomplete_feedback", "estimate": None}
            result = estimate([int(items[-1]["finding"] == "disagree") for items in outcomes], plan["strata"])
            return {"status": "estimable" if result["ht"] is not None else "no_positivity", "estimate": result}

    def feedback(self, cutoff, verify_score=None):
        from .receipts import verify

        with self.transaction(write=False) as db:
            require(0 <= cutoff <= self.now(db), "invalid_cutoff", "Training cutoff exceeds the simulation clock.", 422)
            verify(db, verify_score=verify_score)
            feedback = []
            for event in db.execute("SELECT envelope,result FROM events WHERE kind='intake' ORDER BY seq"):
                envelope, result = (json.loads(event[key]) for key in ("envelope", "result"))
                if envelope["recorded_tick"] > cutoff:
                    continue
                overrides = db.execute("SELECT envelope FROM events WHERE run_id=? AND kind='override' AND tick<=?",
                                       (envelope["run_id"], cutoff))
                if any(json.loads(row[0])["recorded_tick"] <= cutoff for row in overrides):
                    continue
                selected = set(result["intake"]["selected"])
                for case in envelope["claims"]:
                    if case["case_id"] not in selected:
                        continue
                    known = self.revealed(db, case["case_id"], cutoff)
                    if known:
                        latest = known[-1]
                        feedback.append(Feedback(envelope["recorded_tick"], latest["available"],
                                                 case, int(latest["finding"] == "disagree")))
            return feedback, digest([vars(item) for item in feedback])

    def overview(self):
        with self.transaction(write=False) as db:
            now = self.now(db)
            counts = dict(db.execute("SELECT state,COUNT(*) FROM cases GROUP BY state"))
            feedback = db.execute("SELECT COUNT(DISTINCT case_id) FROM outcomes WHERE available<=?", (now,)).fetchone()[0]
            event_counts = dict(db.execute("SELECT kind,COUNT(*) FROM events GROUP BY kind"))
            timing = [row[0] for row in db.execute("SELECT latency_ms FROM events ORDER BY seq DESC LIMIT 512")]
            runs = [dict(row) for row in db.execute(
                "SELECT id run_id,intake_seq,overridden FROM runs ORDER BY intake_seq DESC LIMIT 20")]
            rejections = [dict(row) for row in db.execute(
                "SELECT kind,code,tick,retryable FROM rejections ORDER BY seq DESC LIMIT 20")]
            scores = [json.loads(row[0])["score"] for row in db.execute("SELECT receipt FROM cases ORDER BY id")]
            known = sum(row.get("input_support") == "fitted category" for row in scores)
            unknown_rate = 1 - known / len(scores) if scores else None
            paired = []
            for row in db.execute("""SELECT c.receipt,o.finding FROM cases c JOIN outcomes o ON c.id=o.case_id
                    WHERE o.version=(SELECT MAX(x.version) FROM outcomes x WHERE x.case_id=c.id AND x.available<=?)""",
                                  (now,)):
                score = json.loads(row["receipt"])["score"]
                shadow = score.get("shadow", {})
                if shadow.get("status") == "scored":
                    actual = int(row["finding"] == "disagree")
                    paired.append((shadow["risk"] - actual)**2 - (score["calibrated_risk"] - actual)**2)
            recent = db.execute("SELECT envelope FROM events WHERE kind='intake' ORDER BY seq DESC LIMIT 2")
            mix = [json.loads(row[0])["claims"] for row in recent]
            dme_delta = ((sum(row["part"] == "DME" for row in mix[0]) / len(mix[0])) -
                         (sum(row["part"] == "DME" for row in mix[1]) / len(mix[1]))) if len(mix) == 2 else None
            return {"status": "active" if scores else "no_data", "source": "synthetic", "tick": now,
                    "states": counts, "revealed_cases": feedback, "events": event_counts, "recent_runs": runs,
                    "recent_rejections": rejections,
                    "case_limit": MAX_CASES, "event_limit": MAX_EVENTS, "event_latency": percentiles(timing),
                    "average_score": sum(row["calibrated_risk"] for row in scores)/len(scores) if scores else None,
                    "recent_dme_share_delta": dme_delta,
                    "paired_shadow": {"scope": "revealed synthetic cases", "cases": len(paired),
                                      "brier_delta": sum(paired) / len(paired) if paired else None},
                    "unknown_category_rate": unknown_rate, "alert": "review_feature_support"
                    if unknown_rate is not None and unknown_rate >= 0.25 else None,
                    "shadow_failures": sum(row.get("shadow", {}).get("status") == "unavailable" for row in scores)}

    def trace(self, run_id):
        with self.transaction(write=False) as db:
            return {"run_id": run_id, "events": [dict(row) for row in db.execute(
                "SELECT seq,kind,tick,digest,latency_ms FROM events WHERE run_id=? ORDER BY seq DESC LIMIT 100",
                (run_id,),
            )]}
