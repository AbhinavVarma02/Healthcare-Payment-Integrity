"""Measure cold local startup, latency, throughput and peak process RSS."""

import argparse
import os
import platform
import statistics
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import numpy as np
import psutil

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from payment_integrity.storage import write_json  # noqa: E402

CLAIM = {"part": "DME", "provider_type": "Pharmacy", "visible_lines": 2, "provider_types": 1}


def benchmark(port):
    http_root = f"http://127.0.0.1:{port}"
    launched = time.perf_counter()
    child_env = os.environ.copy()
    child_env["PYTHONPATH"] = "src"
    with subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "payment_integrity.api:create_app", "--factory",
         "--host", "127.0.0.1", "--port", str(port), "--workers", "1", "--no-access-log"],
        env=child_env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ) as process:
        try:
            peak_ram = 0
            proc = psutil.Process(process.pid)
            with httpx.Client(base_url=http_root, timeout=5, trust_env=False) as client:
                for _ in range(150):
                    if process.poll() is not None:
                        raise RuntimeError("Benchmark server exited during startup.")
                    try:
                        if client.get("/ready").status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    time.sleep(0.05)
                else:
                    raise RuntimeError("Benchmark server did not become ready.")
                start_seconds = time.perf_counter() - launched

                def score_many(path, request, request_count, claims_per_request, workers):
                    def timed_request(_):
                        begun = time.perf_counter()
                        response = client.post(path, json=request)
                        response.raise_for_status()
                        return 1000 * (time.perf_counter() - begun)
                    nonlocal peak_ram
                    begun = time.perf_counter()
                    with ThreadPoolExecutor(max_workers=workers) as pool:
                        latencies = []
                        for delay in pool.map(timed_request, range(request_count)):
                            latencies.append(delay)
                            resident = sum(item.memory_info().rss
                                           for item in [proc, *proc.children(recursive=True)])
                            peak_ram = max(peak_ram, resident)
                    seconds = time.perf_counter() - begun
                    return {"requests": request_count, "claims_per_request": claims_per_request,
                            "concurrent_clients": workers, "p50_ms": statistics.median(latencies),
                            "p95_ms": float(np.percentile(latencies, 95)),
                            "claims_per_second": request_count * claims_per_request / seconds}

                single = score_many("/v1/score", CLAIM, 60, 1, 1)
                batch = score_many("/v1/score/batch", {"claims": [CLAIM] * 32}, 40, 32, 4)
            return {"os": platform.platform(), "python": platform.python_version(),
                    "logical_cores": psutil.cpu_count(), "physical_cores": psutil.cpu_count(logical=False),
                    "system_ram_bytes": psutil.virtual_memory().total, "process_peak_rss_bytes": peak_ram,
                    "cold_readiness_seconds": start_seconds, "single": single, "batch": batch}
        finally:
            if process.poll() is None:
                children = psutil.Process(process.pid).children(recursive=True)
                for child in reversed(children):
                    try:
                        child.terminate()
                    except psutil.NoSuchProcess:
                        pass
                process.terminate()
                process.wait(timeout=10)
                psutil.wait_procs(children, timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8011)
    args = parser.parse_args()
    result = benchmark(args.port)
    write_json(Path("artifacts/benchmark.json"), result)
    print(result)


if __name__ == "__main__":
    main()
