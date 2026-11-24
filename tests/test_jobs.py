import threading
import time

import pytest

from payment_integrity.jobs import JobConflict, Jobs
from payment_integrity.storage import write_json


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
