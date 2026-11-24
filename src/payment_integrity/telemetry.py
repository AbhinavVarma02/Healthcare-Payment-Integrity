"""Bounded in-process telemetry for local operation. Events stay in SQLite."""

import math
import threading
import time
from collections import deque

MAX_OBSERVATIONS = 512


def percentiles(values):
    ordered = sorted(values)
    return {f"p{q}_ms": round(ordered[math.ceil(len(ordered) * q / 100) - 1], 3) if ordered else None
            for q in (50, 95)}


class Telemetry:
    def __init__(self):
        self.lock = threading.Lock()
        self.window = deque(maxlen=MAX_OBSERVATIONS)

    def observe(self, route, status, elapsed, size):
        with self.lock:
            self.window.append((time.monotonic(), route, status, elapsed, size))

    def snapshot(self):
        with self.lock:
            observations = list(self.window)
        groups = {}
        for _, route, status, elapsed, size in observations:
            group = groups.setdefault(route, {"times": [], "failures": 0, "input_rejections": 0, "bytes": 0})
            group["times"].append(elapsed)
            group["failures"] += status >= 500
            group["input_rejections"] += status in {400, 403, 409, 413, 422, 429}
            group["bytes"] += size
        return {
            "window": len(observations),
            "requests_per_second": (round((len(observations) - 1) /
                                    max(0.001, observations[-1][0] - observations[0][0]), 3)
                                    if len(observations) > 1 else None),
            "routes": {key: {**percentiles(group["times"]), "requests": len(group["times"]),
                             "error_rate": group["failures"] / len(group["times"]),
                             "input_rejections": group["input_rejections"], "bytes": group["bytes"]}
                       for key, group in groups.items()},
        }
