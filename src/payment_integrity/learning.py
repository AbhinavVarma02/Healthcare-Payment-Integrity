"""Fit and validate simulated scorecard updates using matured review findings."""

import time
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .cohorts import FEATURES, SCHEMA
from .metrics import capacity, probability_metrics, ranked
from .models import calibration_coefficients, feature_frame, fit_lookup
from .planning import review_minutes

GATES = ("feature_schema", "cutoff", "artifact", "brier", "uncertainty", "ap", "yield", "subgroup", "latency")


@dataclass(frozen=True)
class Feedback:
    arrival: int
    available: int
    inputs: dict
    outcome: int


def candidate_input(rows):
    return feature_frame(pd.DataFrame([row.inputs for row in rows], columns=FEATURES))


def fit_candidate(reference, feedback, cutoff, mode):
    """Use separate arrival periods for fitting, calibration and validation."""
    if mode not in {"recalibrate", "retrain"}:
        raise ValueError("Unsupported candidate training mode.")
    eligible = [item for item in feedback if item.available <= cutoff]
    if any(item.arrival > item.available or item.outcome not in (0, 1) for item in eligible):
        raise ValueError("Invalid feedback provenance.")
    ticks = sorted({item.arrival for item in eligible})
    if len(ticks) < 3:
        raise ValueError("Training requires at least three mature intake periods.")
    train = [item for item in eligible if item.arrival < ticks[-2]]
    calibration = [item for item in eligible if item.arrival == ticks[-2]]
    validation = [item for item in eligible if item.arrival == ticks[-1]]
    if min(len(train), len(calibration), len(validation)) < 30:
        raise ValueError("Training, calibration and validation each require at least 30 mature findings.")
    cal_y = np.array([item.outcome for item in calibration])
    val_y = np.array([item.outcome for item in validation])
    if len(set(cal_y)) < 2 or len(set(val_y)) < 2:
        raise ValueError("Calibration and validation require both finding classes.")
    model, base_curve = reference[:2]
    candidate = model if mode == "recalibrate" else fit_lookup(
        candidate_input(train), [item.outcome for item in train],
    )
    curve = calibration_coefficients(candidate.predict(candidate_input(calibration)), cal_y)
    if curve is None or not np.isfinite([curve.slope, curve.intercept]).all() or curve.slope <= 0:
        raise ValueError("Candidate calibration could not establish a finite positive slope.")
    val_x = candidate_input(validation)
    scores = curve.predict(candidate.predict(val_x))
    timing_frame = val_x.iloc[np.arange(500) % len(val_x)]
    check_start = time.perf_counter()
    timed_scores = curve.predict(candidate.predict(timing_frame))
    latency = (time.perf_counter() - check_start) * 1000
    if not np.isfinite(timed_scores).all():
        raise ValueError("Candidate emitted nonfinite scores at batch capacity.")
    baseline = base_curve.predict(model.predict(val_x))
    metrics = {key: performance(val_x, val_y, value)
               for key, value in (("candidate", scores), ("reference", baseline))}
    new, old = metrics["candidate"], metrics["reference"]
    losses = (scores - val_y)**2 - (baseline - val_y)**2
    rng = np.random.default_rng(5501)
    indices = rng.integers(0, len(val_y), size=(400, len(val_y)))
    interval = np.quantile(losses[indices].mean(axis=1), [0.025, 0.975]).tolist()
    report = {
        "schema": 1, "feature_schema": SCHEMA, "scope": "synthetic", "mode": mode,
        "cutoff": cutoff, "latest_label": max(row.available for row in eligible),
        "split": {"train": len(train), "calibration": len(calibration), "validation": len(validation),
                  "train_end": max(item.arrival for item in train),
                  "calibration_tick": ticks[-2], "validation_tick": ticks[-1]},
        "validation_metrics": metrics, "brier_loss_interval": interval, "latency_ms": latency,
        "latency_cases": len(timing_frame),
        "gates": {"feature_schema": True, "cutoff": True, "artifact": True,
                  "brier": new["brier"] <= old["brier"] - 0.001,
                  "uncertainty": interval[1] <= 0,
                  "ap": new["ap"] >= old["ap"] - 0.025,
                  "yield": new["yield"] >= old["yield"] - 0.10,
                  "subgroup": all(row["absolute_rate_error"] <= 0.25 for row in new["subgroups"].values()),
                  "latency": latency <= 250},
    }
    return candidate, curve, report


def passed(report):
    gates = report.get("gates", {})
    return gates.keys() == set(GATES) and all(result is True for result in gates.values())


def performance(frame, outcomes, risk):
    if not np.isfinite(risk).all() or not np.all((0 <= risk) & (risk <= 1)):
        raise ValueError("Scorecard emitted invalid probabilities.")
    rows = len(frame)
    order = ranked(risk, np.arange(rows))[:capacity(rows, 10)]
    stats = probability_metrics(outcomes, risk)
    parts = frame["part"].to_numpy()
    groups = {part: {"cases": int(mask.sum()),
                     "absolute_rate_error": float(abs(risk[mask].mean() - outcomes[mask].mean()))}
              for part in ("Part B", "DME") if (mask := parts == part).sum() >= 10}
    return {"brier": stats["brier"], "ap": stats["ap"], "ece": stats["ece"],
            "yield": float(outcomes[order].mean()), "reviews": len(order),
            "review_minutes": int(review_minutes(frame["visible_lines"].to_numpy()[order]).sum()),
            "subgroups": groups}
