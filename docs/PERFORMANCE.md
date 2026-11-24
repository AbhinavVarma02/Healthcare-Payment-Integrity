# Local performance

The November 24, 2026 release rerun used the registered lookup on Windows 11 build 26200, Python 3.13.2, and an Intel Core i9-14900HX with 24 physical cores, 32 logical cores and 34.05 GB RAM. One Uvicorn worker served loopback HTTP. Cold readiness was measured separately from the 60 sequential single-case requests and 40 batch requests of 32 cases with four concurrent clients. Peak RSS sums the Windows Python launcher and child process.

| Measurement | Observed | Development objective |
| --- | ---: | ---: |
| Cold startup to readiness | 1.713 s | ≤ 3 s |
| Single request p50 / p95 | 9.50 / 10.51 ms | p95 ≤ 25 ms |
| 32-claim batch p50 / p95 | 21.74 / 40.29 ms | p95 ≤ 75 ms at four concurrent clients |
| Single / batch throughput | 108 / 4,871 cases/s | Informational |
| Peak process-tree RSS | 201.96 MB | ≤ 300 MB for the measured scoring load |
| Failed scoring requests | 0 of 100 | Informational |

The seed 5022 workload applied 430 accepted synthetic events in 1.99 seconds, including 210 assignments and 210 submissions. Event p50 and p95 were 1.270 and 1.553 ms. End-of-run process RSS was 195.07 MB. Restoring the SQLite backup and verifying its model-linked event anchor took 0.050 seconds. All ten targeted fault, provenance and recovery checks passed.

Objectives are local engineering targets set from development profiling. Loads use one machine, one worker and an in-memory lookup with no production traffic. Replay execution, disk caches and system load can affect results. The reference H3 replay took 213 seconds over 200 seeds. Reproduce the workloads with `python scripts/benchmark.py --output artifacts/final-benchmark.json` and `python scripts/simulate_workflow.py --output artifacts/workflow-release --seed 5022`. [Evidence ledger](EVIDENCE.md)
