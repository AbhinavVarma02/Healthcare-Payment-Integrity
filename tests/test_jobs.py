import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from payment_integrity import storage
from payment_integrity.jobs import JobConflict, Jobs
from payment_integrity.storage import read_json, write_json


def wait_for(jobs, job_id, state):
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        row = jobs.get(job_id)
        if row["status"] == state and jobs.task is None:
            return row
        time.sleep(0.02)
    pytest.fail(f"Replay job did not enter {state}.")


def test_worker_cancellation_resume_and_process_lock(tmp_path):
    entered = threading.Event()
    finish = threading.Event()

    def work(row, _folder, progress, cancel):
        entered.set()
        for _ in range(150):
            if cancel():
                raise InterruptedError
            if finish.wait(0.02):
                progress(row["seeds_requested"], row["seeds_requested"])
                return {"conclusions": {"status": "fixture"}}
        raise RuntimeError("Timed out waiting for synthetic worker control.")

    jobs = Jobs(tmp_path, work)
    second = Jobs(tmp_path, work)
    try:
        assert jobs.recover() and not second.recover()
        job = jobs.start("fixture", 1)["id"]
        assert entered.wait(2)
        with pytest.raises(JobConflict):
            jobs.start("fixture", 1)
        jobs.cancel(job)
        wait_for(jobs, job, "cancelled")
        finish.set()
        jobs.resume(job)
        assert wait_for(jobs, job, "completed")["seeds_completed"] == 1
        assert [row["id"] for row in jobs.recent(1)] == [job]
    finally:
        jobs.close()
        second.close()
    ghost = "a" * 32
    write_json(tmp_path / f"{ghost}.json", {"id": ghost, "status": "running"})
    recovered = Jobs(tmp_path, work)
    try:
        assert recovered.recover()
        assert recovered.get(ghost)["status"] == "interrupted"
    finally:
        recovered.close()


def test_shutdown_marks_job_interrupted_for_restart(tmp_path):
    entered = threading.Event()

    def work(_row, _folder, _progress, cancelled):
        entered.set()
        deadline = time.monotonic() + 4
        while not cancelled() and time.monotonic() < deadline:
            time.sleep(0.01)
        if cancelled():
            raise InterruptedError
        raise RuntimeError("Shutdown did not signal the worker.")

    jobs = Jobs(tmp_path, work)
    assert jobs.recover()
    try:
        job_id = jobs.start("fixture", 1)["id"]
        assert entered.wait(2)
    finally:
        jobs.close()
    assert jobs.get(job_id)["status"] == "interrupted"


@pytest.mark.parametrize("platform,transient,expected_reads", [
    ("nt", 2, 3), ("nt", 8, 8), ("posix", 2, 1),
], ids=["recovers-on-windows", "bounded-on-windows", "immediate-on-posix"])
def test_job_manifest_read_handles_sharing_violations(tmp_path, monkeypatch, platform, transient, expected_reads):
    manifest = tmp_path / "job.json"
    write_json(manifest, {"status": "cancelled"})
    attempts, delays = 0, []
    original = Path.read_text

    def read(path, *args, **kwargs):
        nonlocal attempts
        if path == manifest:
            attempts += 1
            if attempts <= transient:
                raise PermissionError("Simulated denied read during atomic replacement.")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read)
    monkeypatch.setattr(storage, "os", SimpleNamespace(name=platform))
    monkeypatch.setattr(storage, "time", SimpleNamespace(sleep=delays.append))
    if transient < expected_reads:
        assert read_json(manifest) == {"status": "cancelled"}
    else:
        with pytest.raises(PermissionError):
            read_json(manifest)
    assert attempts == expected_reads
    assert delays == [0.01 * attempt for attempt in range(1, expected_reads)]
