# Operations runbook

## Start and exercise

Follow the repository setup and point the app at the integrity-verified local research registry. Open the loopback Operations tab, intake a four-case fictional batch, assign a queued case, and submit a finding. Advance one tick to reveal it, record a correction and advance again. The receipt should show the original and corrected findings. A supervisor swap of an unassigned case keeps the original design and marks the estimate unavailable for the intervened run. [Startup](../README.md) · [Loopback operations](http://127.0.0.1:5173/#/operations)

The local simulation limits intake to 100 cases per event, 2,000 cases per database and 10,000 accepted events. The replay worker has separate bounded jobs and seed checkpoints. The operator can inspect queue state, last accepted events, redacted rejection reasons and recent request timings. Feature fallback above a 25% unknown-category share prompts inspection. The latest two batch mixes are descriptive. Shadow Brier differences use only case pairs with eligible outcomes.

## Verify, back up and restore

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe scripts/simulate_workflow.py --output artifacts/workflow-example
.venv/Scripts/python.exe -m payment_integrity.receipts artifacts/workflow-example/scenario.sqlite3 --reference-registry artifacts/registry --write-anchor artifacts/workflow-example/anchor.json
.venv/Scripts/python.exe -m payment_integrity.receipts artifacts/workflow-example/restored.sqlite3 --reference-registry artifacts/registry --anchor artifacts/workflow-example/anchor.json
```

The exercise uses SQLite's backup API and checks a separately retained event anchor. For manual backups, stop local writers or use SQLite's online backup API. Retain the synthetic registry, active pointer and anchor together with the database. Verify a restored copy against the retained anchor and model digests before restarting operations.

An interrupted event transaction rolls back with its projections. Retry an uncertain delivery with exactly the same event ID, idempotency key and payload. For a conflicting ID, inspect the accepted event and give a replacement its own ID. Review quarantine codes for malformed, out-of-order, denied or over-capacity actions. Retry eligible transient failures after capacity or service readiness recovers. When receipt or model verification fails, freeze promotion and export and inspect a verified backup in a separate directory.

## Measured scenario

The seed-5022 exercise produced 430 accepted events with 10 scenario checks. It verified delayed and corrected findings, duplicate and conflicting submissions, capacity reduction, role checks, shadow provenance, stale and rejected approvals, and restoration. On the Windows reference system it took 3.81 seconds and restoration plus anchor verification took 0.132 seconds. Accepted event p50 and p95 were 1.62 and 5.78 ms. Process memory at finish was 195.40 MB. Timing characterizes this workload and machine. [Performance methodology](PERFORMANCE.md)
