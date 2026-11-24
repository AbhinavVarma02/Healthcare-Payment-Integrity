"""Verify local event, receipt and projection integrity against a retained checkpoint."""

import argparse
import json
import sqlite3
import time
from contextlib import closing
from pathlib import Path

from .storage import read_json, write_json
from .workflow import SCHEMA, Workflow, require
from .workflow_contracts import COMMANDS, ROLES

GENESIS = "0" * 64
PROJECTIONS = {
    "clock": "id",
    "runs": "id",
    "cases": "id",
    "outcomes": "case_id,version",
}


def verify(db, anchor=None, verify_score=None):
    """Reconstruct every projection and policy selection from canonical event input and saved scores."""
    require(not db.execute("PRAGMA foreign_key_check").fetchone(), "integrity", "Broken event reference.", 503)
    hashes = {0: GENESIS}
    with closing(sqlite3.connect(":memory:")) as rebuilt:
        rebuilt.row_factory = sqlite3.Row
        rebuilt.execute("PRAGMA foreign_keys=ON")
        for statement in SCHEMA:
            rebuilt.execute(statement)

        def historical_scores(claims):
            scores = []
            for claim in claims:
                row = db.execute("SELECT receipt FROM cases WHERE id=?", (claim.case_id,)).fetchone()
                require(row is not None, "integrity", "Intake is missing a receipt.", 503)
                scores.append(json.loads(row["receipt"])["score"])
            if verify_score:
                verify_score(claims, scores)
            return scores

        replay = Workflow(Path("."), historical_scores)
        for item in db.execute("SELECT * FROM events ORDER BY seq"):
            envelope = json.loads(item["envelope"])
            kind = envelope.pop("kind")
            role = envelope.pop("actor_role")
            envelope.pop("payload_sha256")
            envelope.pop("recorded_tick")
            require(role == ROLES.get(kind), "integrity", "Event role is inconsistent.", 503)
            event = COMMANDS[kind].model_validate(envelope)
            replay.record(rebuilt, kind, event, role, time.perf_counter())
            reproduced = rebuilt.execute("SELECT * FROM events ORDER BY seq DESC LIMIT 1").fetchone()
            require(all(reproduced[key] == item[key] for key in item.keys() if key != "latency_ms"),
                    "integrity", "Event sequence or content differs from replay.", 503)
            hashes[item["seq"]] = item["digest"]
        for table, ordering in PROJECTIONS.items():
            statement = f"SELECT * FROM {table} ORDER BY {ordering}"
            actual = [tuple(row) for row in db.execute(statement)]
            expected = [tuple(row) for row in rebuilt.execute(statement)]
            require(actual == expected, "integrity", f"Workflow {table} projection differs from replay.", 503)
    if anchor is not None:
        require(anchor["schema_version"] == 1 and hashes.get(anchor["sequence"]) == anchor["digest"],
                "integrity", "Event history differs from the retained checkpoint.", 503)
    sequence = max(hashes)
    return {"schema_version": 1, "sequence": sequence, "digest": hashes[sequence]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    parser.add_argument("--anchor", type=Path, help="Compare with an independently retained checkpoint.")
    parser.add_argument("--write-anchor", type=Path, help="Write a new checkpoint after successful verification.")
    parser.add_argument("--reference-registry", type=Path, help="Also verify model evidence in this local registry.")
    parser.add_argument("--candidate-root", type=Path, help="Operations folder containing candidate versions.")
    args = parser.parse_args()
    if not args.database.is_file():
        parser.error("Database does not exist.")
    if args.write_anchor and args.write_anchor.exists():
        parser.error("Choose a new checkpoint path.")
    try:
        verify_score = None
        if args.reference_registry:
            from .lifecycle import Lifecycle
            from .registry import Registry

            lifecycle = Lifecycle(args.candidate_root or args.database.parent,
                                  Registry(args.reference_registry), None, ())
            verify_score = lifecycle.reference_verifier()
        uri = args.database.resolve().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(uri, uri=True)) as db:
            db.row_factory = sqlite3.Row
            db.execute("BEGIN")
            result = verify(db, read_json(args.anchor) if args.anchor else None, verify_score)
        if args.write_anchor:
            write_json(args.write_anchor, result)
    except (OSError, sqlite3.DatabaseError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"Verification failed: {error}\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
