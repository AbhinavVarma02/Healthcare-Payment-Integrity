"""Bounded local replay jobs with persistent state and explicit recovery."""

import logging
import re
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from filelock import FileLock
from filelock import Timeout as LockTimeout

from .storage import read_json, write_json

LOG = logging.getLogger("uvicorn.error").getChild("replay")
JOB_ID = re.compile(r"[0-9a-f]{32}")


def timestamp():
    return datetime.now(UTC).isoformat(timespec="seconds")


class JobConflict(Exception):
    """The local worker or requested job is unavailable."""


class Jobs:
    def __init__(self, folder: Path, work: Callable):
        self.folder = folder
        self.work = work
        self.folder.mkdir(parents=True, exist_ok=True)
        self.process_lock = FileLock(folder / ".worker-lock", timeout=0)
        self.mutex = threading.RLock()
        self.task: str | None = None
        self.stop_signal = threading.Event()
        self.worker = None

    def recover(self):
        try:
            self.process_lock.acquire()
        except LockTimeout:
            return False
        for path in self.folder.glob("*.json"):
            if JOB_ID.fullmatch(path.stem):
                row = read_json(path)
                if row["status"] in {"running", "queued"}:
                    self.store({**row, "status": "interrupted"})
        self.worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="cert-replay")
        return True

    def close(self):
        self.stop_signal.set()
        if self.worker is not None:
            self.worker.shutdown(wait=True)
            self.worker = None
        self.process_lock.release()

    def path(self, job_id):
        if not JOB_ID.fullmatch(job_id):
            raise FileNotFoundError("Invalid local job reference.")
        return self.folder / f"{job_id}.json"

    def store(self, row):
        row = {**row, "updated_utc": timestamp()}
        write_json(self.path(row["id"]), row)
        return row

    def get(self, job_id):
        return read_json(self.path(job_id))

    def start(self, freeze, seeds):
        with self.mutex:
            if self.task is not None or self.worker is None:
                raise JobConflict("One replay job can run at a time.")
            row = self.store({"id": uuid4().hex, "status": "queued", "freeze": freeze,
                              "seeds_requested": seeds, "seeds_completed": 0,
                              "created_utc": timestamp(), "scope": "local replay preview"})
            return self.queue(row)

    def queue(self, row):
        if self.task is not None or self.worker is None:
            raise JobConflict("The replay worker is busy or disabled.")
        self.stop_signal.clear()
        self.task = row["id"]
        self.worker.submit(self.execute, row)
        return row

    def resume(self, job_id):
        with self.mutex:
            row = self.get(job_id)
            if (row["status"] not in {"interrupted", "cancelled", "failed"}
                    or self.task is not None or self.worker is None):
                raise JobConflict("The job cannot be resumed in its current state.")
            return self.queue(self.store({**row, "status": "queued", "error": None}))

    def cancel(self, job_id):
        with self.mutex:
            row = self.get(job_id)
            if job_id != self.task:
                raise JobConflict("The job is not running.")
            self.stop_signal.set()
            return row

    def execute(self, row):
        job_id = row["id"]

        def progress(done, total):
            self.store({**self.get(job_id), "status": "running", "seeds_completed": done})

        try:
            self.store({**row, "status": "running"})
            result = self.work(row, self.folder / job_id, progress, self.stop_signal.is_set)
            self.store({**self.get(job_id), "status": "completed", "summary": result["conclusions"]})
        except InterruptedError:
            self.store({**self.get(job_id), "status": "cancelled"})
        except Exception as exc:
            LOG.warning("replay_failed id=%s error_family=%s", job_id, type(exc).__name__)
            self.store({**self.get(job_id), "status": "failed", "error": "replay_execution_failed"})
        finally:
            with self.mutex:
                self.task = None
