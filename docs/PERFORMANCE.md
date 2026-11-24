# Local performance

The November 24, 2026 benchmark used the registered lookup on Windows 11 build 26200, Python 3.13.2, and an Intel Core i9-14900HX with 24 physical cores, 32 logical cores and 34.05 GB RAM. One Uvicorn worker served loopback HTTP. The study used 60 sequential single requests and 40 batch requests of 32 with four concurrent clients. Peak RSS sums the Windows Python launcher and child process.

| Measurement | Observed | Development objective |
| --- | ---: | ---: |
| Cold startup to readiness | 1.73 s | ≤ 3 s |
| Single request p50 / p95 | 11.36 / 12.78 ms | p95 ≤ 25 ms |
| 32-claim batch p50 / p95 | 28.67 / 43.83 ms | p95 ≤ 75 ms at four concurrent clients |
| Single / batch throughput | 90 / 3,908 claims/s | Informational |
| Peak process-tree RSS | 199.38 MB | ≤ 300 MB for the measured scoring load |

Objectives are local engineering targets set from development profiling. The measurements cover scoring requests against a small lookup model on one machine. Replay execution, disk caches and system load can affect results. Reference scientific runtime was 6.64 seconds for candidate fit, calibration and development selection plus 213 seconds for the full 200-seed replay. Reproduce scoring benchmarks with `python scripts/benchmark.py`. [Evidence ledger](EVIDENCE.md)
