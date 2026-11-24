"""Local recovery state and cooperative single-writer lease."""

import argparse
import hashlib
import json
import os
import platform
import re
import socket
import subprocess
import tempfile
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / ".project"
STATE = PROJECT / "STATE.json"
LOCK = PROJECT / "writer.lock"
HEARTBEAT = PROJECT / "heartbeat.json"
SNAPSHOTS = PROJECT / "checkpoints"
MASTER = PROJECT / "MASTER_PROMPT.md"
LEDGERS = ("TASKS", "DECISIONS", "SESSION_LOG", "ERRORS", "VALIDATION", "BLOCKERS")


def utc():
    return datetime.now(UTC).isoformat(timespec="seconds")


def atomic(path, value):
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False, mode="w",
                                     encoding="utf-8", newline="\n") as handle:
        temporary = Path(handle.name)
        handle.write(value)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def dump(value):
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def git(*args):
    result = subprocess.run(["git", *args], check=False, cwd=ROOT, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else None


def lock(owner, minutes):
    metadata = {"owner": owner, "pid": os.getpid(), "host": socket.gethostname(),
                    "workspace": str(ROOT), "created": utc()}
    with LOCK.open("x", encoding="utf-8") as handle:
        handle.write(dump(metadata))
        handle.flush()
        os.fsync(handle.fileno())
    end = time.monotonic() + minutes * 60
    print(f"Acquired writer lease ({owner})", flush=True)
    try:
        while time.monotonic() < end:
            atomic(HEARTBEAT, dump({"owner": owner, "heartbeat": utc()}))
            if (PROJECT / f"stop-{owner}").exists():
                break
            time.sleep(2)
    finally:
        if LOCK.exists() and read(LOCK) == metadata:
            HEARTBEAT.unlink(missing_ok=True)
            (PROJECT / f"stop-{owner}").unlink(missing_ok=True)
            LOCK.unlink()


def assert_owner(owner):
    if read(LOCK)["owner"] != owner:
        raise SystemExit("Checkpoint requires the active writer lease.")


def validate(state):
    required = {"schema_version", "revision", "phase", "task", "run_ids", "commit",
                "timestamp_utc", "status", "spec_sha256"}
    if not required <= state.keys() or state["schema_version"] != 1:
        raise SystemExit("Unsupported recovery state schema.")
    if not isinstance(state["revision"], int) or state["revision"] < 1:
        raise SystemExit("Invalid recovery state revision.")
    if not isinstance(state["run_ids"], list) or not set(state["status"]) >= {
        "research", "implementation", "validation", "publication", "deployment"
    }:
        raise SystemExit("Missing research or release status.")
    for path in (*[PROJECT / f"{name}.md" for name in LEDGERS],
                 ROOT / "AGENTS.md", ROOT / "CLAUDE.md"):
        if not path.is_file():
            raise SystemExit(f"Missing recovery file: {path.name}")
    if hashlib.file_digest(MASTER.open("rb"), "sha256").hexdigest() != state["spec_sha256"]:
        raise SystemExit("Master specification checksum has changed.")


def commit_checkpoint(args):
    assert_owner(args.owner)
    SNAPSHOTS.mkdir(exist_ok=True)
    previous = read(STATE) if STATE.exists() else None
    if previous:
        validate(previous)
        atomic(SNAPSHOTS / f"{previous['revision']:06d}.json", dump(previous))
    with MASTER.open("rb") as handle:
        spec_hash = hashlib.file_digest(handle, "sha256").hexdigest()
    revision = previous["revision"] + 1 if previous else 1
    status = {"research": "Incomplete", "implementation": "Incomplete", "validation": "Incomplete",
                  "publication": "Unverified", "deployment": "Undeployed"}
    if previous:
        status.update(previous["status"])
    for update in args.status:
        key, value = update.split("=", 1)
        if key not in status:
            raise SystemExit(f"Unrecognized status key: {key}")
        status[key] = value
    current = {"schema_version": 1, "revision": revision, "phase": args.phase, "task": args.task,
                   "spec_version": "2.0", "spec_sha256": spec_hash, "timestamp_utc": utc(),
                   "branch": git("branch", "--show-current"), "commit": git("rev-parse", "HEAD"),
                   "run_ids": args.run or (previous["run_ids"] if previous else []), "status": status,
                   "action": args.action, "next": args.next, "checks": args.check,
                   "research": args.research, "blockers": args.blockers, "jobs": args.jobs,
                   "dirty_tree": git("status", "--short"), "task_state": args.task_state}
    validate(current)
    statuses = Counter(re.findall(r"\| (pending|in progress|implemented|verified|blocked|deferred) \|",
                                 (PROJECT / "TASKS.md").read_text(encoding="utf-8")))
    summary = ", ".join(f"{key} {count}" for key, count in sorted(statuses.items()))
    progress = f"""# Current checkpoint

- Specification `.project/MASTER_PROMPT.md` v2.0, SHA-256 `{spec_hash}`
- Workspace `{ROOT}`, Windows PowerShell. Updated {current['timestamp_utc']}. Revision {revision}.
- Phase {args.phase}, task {args.task}, {args.task_state}. Branch {current['branch']}, latest commit `{current['commit'] or 'none'}`.
- Tracked status\n\n```text\n{current['dirty_tree'] or 'clean'}\n```
- Task counts from TASKS.md: {summary}
- Current action: {args.action}
- Next action and exit gate: {args.next}
- Checks and evidence: {args.check}
- Research state and runs: {args.research}. {', '.join(current['run_ids']) or 'None recorded'}.
- Budget: no metered service enabled or additional charges incurred by recorded actions.
- Jobs and restart: {args.jobs}
- Blockers and handoff: {args.blockers}

## Deliverable status

""" + "".join(f"- {key.capitalize()}: {value}\n" for key, value in status.items())
    atomic(PROJECT / "PROGRESS.md", progress)
    atomic(STATE, dump(current))
    atomic(SNAPSHOTS / f"{revision:06d}.md", progress)
    atomic(SNAPSHOTS / f"{revision:06d}.json", dump(current))
    for path in sorted(SNAPSHOTS.glob("[0-9]*"))[:-12]:
        path.unlink()
    print(f"Checkpoint {revision} ({args.phase}/{args.task})")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    lease = commands.add_parser("lock")
    lease.add_argument("owner")
    lease.add_argument("--minutes", type=int, choices=range(1, 121), default=45)
    commands.add_parser("verify")
    release = commands.add_parser("release")
    release.add_argument("owner")
    checkpoint = commands.add_parser("write")
    for field in ("owner", "phase", "task", "task-state", "action", "next", "check", "research",
                  "blockers", "jobs"):
        checkpoint.add_argument(f"--{field}", required=True)
    checkpoint.add_argument("--run", action="append", default=[])
    checkpoint.add_argument("--status", action="append", default=[])
    args = parser.parse_args()
    if hasattr(args, "owner") and not re.fullmatch(r"[a-zA-Z0-9-]{1,64}", args.owner):
        parser.error("Invalid owner identifier.")
    if args.command == "lock":
        lock(args.owner, args.minutes)
    elif args.command == "release":
        assert_owner(args.owner)
        (PROJECT / f"stop-{args.owner}").touch()
    elif args.command == "write":
        commit_checkpoint(args)
    else:
        state = read(STATE)
        validate(state)
        if f"Revision {state['revision']}." not in (PROJECT / "PROGRESS.md").read_text(encoding="utf-8"):
            raise SystemExit("Recovery files disagree. Inspect the matching last-known-good snapshot.")
        print(f"Valid recovery state revision {state['revision']} on {platform.system()}.")


if __name__ == "__main__":
    main()
