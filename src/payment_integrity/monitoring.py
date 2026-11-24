"""Development-referenced drift and delayed outcome diagnostics."""

from collections import Counter

import numpy as np
from scipy.spatial.distance import jensenshannon

from .metrics import probability_metrics
from .models import calibration_coefficients


def proportions(counts):
    smoothed = np.asarray(counts, dtype=float) + 0.5
    return smoothed / smoothed.sum()


def histogram(scores):
    return np.histogram(scores, bins=np.linspace(0, 1, 11))[0]


def profile(frame, scores, providers):
    counts = Counter(frame["provider_type"].where(frame["provider_type"].isin(providers), "Other"))
    return {
        "count": len(frame),
        "categories": [counts.get(name, 0) for name in [*providers, "Other"]],
        "score_histogram": histogram(scores).tolist(),
        "unknown_rate": float((~frame["provider_type"].isin(providers)).mean()),
        "missing_rate": float(frame["provider_type"].eq("Missing").mean()),
    }


def describe_shift(baseline, current):
    p, q = (proportions(item["score_histogram"]) for item in (baseline, current))
    a, b = (proportions(item["categories"]) for item in (baseline, current))
    return {
        "score_psi": float(np.sum((q - p) * np.log(q / p))),
        "category_js_distance": float(jensenshannon(a, b, base=2)),
        "unknown_rate_delta": abs(current["unknown_rate"] - baseline["unknown_rate"]),
        "missing_rate_delta": abs(current["missing_rate"] - baseline["missing_rate"]),
    }


def development_thresholds(baseline, development):
    shift = describe_shift(baseline, development)
    floors = {"score_psi": 0.02, "category_js_distance": 0.03,
              "unknown_rate_delta": 0.01, "missing_rate_delta": 0.01}
    return {key: max(1.25 * value, floors[key]) for key, value in shift.items()}


def assess(baseline, current, thresholds, y=None, p=None):
    shift = describe_shift(baseline, current)
    alerts = [key for key in thresholds if shift[key] > thresholds[key]]
    measured = None
    if y is not None and p is not None:
        eligible = np.isfinite(y)
        if eligible.any():
            evaluated_y, evaluated_p = y[eligible], p[eligible]
            coeff = calibration_coefficients(evaluated_p, evaluated_y)
            measured = {
                "labelled_claims": int(eligible.sum()),
                "outcome_rate": float(evaluated_y.mean()),
                "calibration_intercept": coeff.intercept if coeff else None,
                "calibration_slope": coeff.slope if coeff else None,
                **probability_metrics(evaluated_y, evaluated_p),
            }
    return {"current": {k: v for k, v in current.items() if k != "categories"},
            "drift": shift, "covariate_alerts": alerts, "measured_performance": measured}
