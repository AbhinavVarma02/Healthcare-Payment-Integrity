"""Claim-level evaluation and paired comparison utilities."""

from math import ceil, sqrt

import numpy as np
from sklearn.metrics import average_precision_score, precision_recall_curve, roc_auc_score

from .models import calibration_coefficients


def capacity(size: int, percent: int) -> int:
    if not 0 <= percent <= 100 or size < 0:
        raise ValueError("Invalid frame or capacity.")
    return (size * percent + 50) // 100


def ranked(scores, keys):
    return np.lexsort((keys, -np.asarray(scores)))


def precision_at(y, p, keys, percent):
    budget = capacity(len(y), percent)
    return float(y[ranked(p, keys)[:budget]].mean()) if budget else None


def probability_metrics(y, p):
    if not len(y):
        return {"ap": None, "auroc": None, "brier": None, "ece": None}
    bin_ids = np.minimum(9, (np.asarray(p) * 10).astype(int))
    calibration = []
    calibration_error = 0.0
    for bucket in range(10):
        mask = bin_ids == bucket
        n = int(mask.sum())
        if n:
            prediction, observed = float(p[mask].mean()), float(y[mask].mean())
            calibration_error += n * abs(prediction - observed)
            calibration.append({"bin": bucket, "claims": n, "predicted": prediction,
                                "observed": observed})
    return {
        "ap": float(average_precision_score(y, p)) if y.sum() else None,
        "auroc": float(roc_auc_score(y, p)) if 0 < y.sum() < len(y) else None,
        "brier": float(np.mean(np.square(p - y))),
        "ece": calibration_error / len(y),
        "calibration": calibration,
    }


def study_metrics(y, p, keys, budgets, curve=True):
    results = probability_metrics(y, p)
    if not len(y):
        return results
    calibration = calibration_coefficients(p, y)
    results.update({
        "claims": len(y), "findings": int(y.sum()),
        "calibration_intercept": calibration.intercept if calibration else None,
        "calibration_slope": calibration.slope if calibration else None,
        "capacity": {},
    })
    order = ranked(p, keys)
    for budget_percent in budgets:
        reviews = capacity(len(y), budget_percent)
        findings = int(y[order[:reviews]].sum())
        results["capacity"][str(budget_percent)] = {
            "reviews": reviews, "findings": findings,
            "precision": findings / reviews if reviews else None,
            "recall": findings / y.sum() if y.sum() else None,
        }
    if curve and y.sum():
        precision, recall, _ = precision_recall_curve(y, p)
        indexes = np.unique(np.linspace(0, len(precision) - 1, min(51, len(precision))).astype(int))
        results["pr_curve"] = [[float(recall[i]), float(precision[i])] for i in indexes]
    return results


def paired_intervals(size, statistic, seed, iterations, interval=0.975):
    rng = np.random.default_rng(seed)
    draws = [statistic(rng.integers(0, size, size=size)) for _ in range(iterations)]
    values = np.asarray(draws, dtype=float)
    quantiles = [(1 - interval) / 2, (1 + interval) / 2]
    return [
        {"bounds": np.quantile(column[np.isfinite(column)], quantiles).tolist()
                   if np.isfinite(column).sum() >= ceil(iterations * 0.95) else None,
         "replicates": int(np.isfinite(column).sum()), "confidence": interval}
        for column in values.T
    ]


def mean_with_mcse(values):
    subset = np.asarray([value for value in values if value is not None])
    if not len(subset):
        return {"mean": None, "mcse": None, "quantiles": None, "n": 0}
    return {"mean": float(subset.mean()),
            "mcse": float(subset.std(ddof=1) / sqrt(len(subset))) if len(subset) > 1 else None,
            "quantiles": np.quantile(subset, [0.025, 0.5, 0.975]).tolist(), "n": len(subset)}
