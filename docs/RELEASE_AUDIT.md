# Release audit

## Scope and evidence

The v1.0.0 release candidate extends the audited commit `d5bfc8238c42cd62f622d41c3eb3445ec85fc1cd`. The frozen protocol remains at `aab39fdc790597c2c476e0f4d79aaf8543e74b09`. H1 remains unsupported, H2 inconclusive and H3 mixed. The original research aggregate SHA-256 is `eaf69560201573458508a359471a70d5720226e8e37d75d77b500d10db222b32`. The preserved local baseline export and its seven file hashes provide the original static reference. [Baseline audit](AUDIT_REPORT.md) · [Historical evidence](EVIDENCE.md)

| Gate | Release evidence |
| --- | --- |
| Bounded workflow | SQLite transaction recovery, duplicate idempotency, conflicts, capacity, delayed findings, corrections, role checks, rejected event metadata and a persisted review queue. |
| Decision provenance | Canonical payload, model and policy digests, rational inclusion probabilities, deterministic projection replay and independently retained anchor. Corruption and removed anchored events are detected. |
| Candidate lifecycle | Actual workflow recalibration, shadow scoring and gate rejection. Separate synthetic fixtures verify stale approval, corrupt shadow, interrupted rollback and recovery to the reference. |
| H4 adaptive allocation | Full four-cohort retrospective grid, 200 seeds and 22,400 policy records. Adaptive tied its matched fixed rule. An independent rerun reproduced all 200 seed artifacts byte for byte and the aggregate matched apart from elapsed time. Exact enumeration and interval coverage simulation passed. |
| H5 synthetic learning | Full 120-run grid with paired controls. Recalibration helped under the prespecified prevalence shift and worsened Brier slightly under stationarity. All 20 seed batches reproduced for decisions and statistics after excluding inference timing. |
| H6 analyst interface | Ten deterministic scenarios passed. The optional installed model timed out on seven requests and missed its gate. Release uses deterministic tools. |
| Reliability and recovery | Seed 5022 simulated 430 accepted events and ten checks. Restored a SQLite backup and verified its event anchor and model references. |
| Publication and privacy | Git allowlist, reviewed aggregate projection, content and history checks, synthetic static example, local static-only preview and versioned manifest. |

## Performance and dependencies

The local loopback benchmark used Windows 11, Python 3.13.2, 32 logical cores and 34.05 GB system memory. Cold readiness was 1.71 seconds. The 60 single-case requests had 10.78 ms p95 latency. The 40 requests of 32 cases with four concurrent clients had 23.26 ms p95 and 5,989 cases per second. Process-tree peak RSS was 201.43 MB. The synthetic workflow ended at 195.40 MB process RSS and restored and verified its backup in 0.132 seconds. These measurements characterize the tested hardware and loads. [Benchmark procedure](PERFORMANCE.md) · [Workflow procedure](OPERATIONS_RUNBOOK.md)

The locked npm and Windows Python runtime advisory queries returned zero known findings at the time of review. The project used local compute and public advisory queries with $0 additional expenditure. Source rights, the frozen CERT reporting frame, optional local model limits and a future untouched cohort remain documented. External publication requires authorization for the exact target. [Source rights](LICENSING.md) · [Scope limits](LIMITATIONS.md) · [Deployment](DEPLOYMENT.md)

## Verification commands

| Gate | Executed result |
| --- | --- |
| `uv sync --offline --locked --python 3.13.2`, `scripts/fixture_smoke.py`, `pytest -q --basetemp .cache/pytest`, Ruff and mypy | Exit 0 in a clean Windows archive. 30 Python tests passed. The upstream Starlette TestClient deprecation warning remains. |
| `npm --prefix web ci --offline --ignore-scripts`, `npm --prefix web run test`, `npm --prefix web run build` | Exit 0 in the clean archive. Two frontend tests passed. |
| `npm --prefix web run test:browser` | Exit 0. Five Edge flows passed, including static route reload, mobile layout, local replay, delayed review and correction. |
| `scripts/audit_release.py`, `payment_integrity.publication check`, `payment_integrity.publication export` | Exit 0. Git and static content checks passed. All seven files reproduced from the clean archive. Export manifest SHA-256 `2bd95090d39cc47b642a272ac6f83945a4ae29cf47cf16543a58329945a2733f`. |
| `npm audit --json --ignore-scripts`, `pip-audit` over the locked runtime | Exit 0. Zero known advisory findings at evaluation time. |
