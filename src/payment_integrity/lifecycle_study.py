"""Prespecified delayed-feedback experiments for simulated model updates."""

import argparse
import time
from pathlib import Path

import numpy as np
import pandas as pd
from filelock import FileLock
from scipy.special import expit, logit

from .learning import Feedback, fit_candidate, passed, performance
from .metrics import mean_with_mcse
from .models import feature_frame
from .registry import Registry
from .storage import read_json, sha256, write_json
from .workflow import digest

SCENARIOS = ("stationary", "prevalence", "subgroup")
MODES = ("recalibrate", "retrain")
SEEDS = tuple(range(20, 40))


class SimulatedWave:
    def __init__(self, reference, rng, tick, scenario):
        model, curve, _ = reference
        categories = sorted(model.providers)
        selected = rng.integers(0, len(categories), 500)
        frame = pd.DataFrame([categories[i] for i in selected], columns=["part", "provider_type"])
        frame["visible_lines"] = rng.integers(1, 8, 500)
        frame["provider_types"] = 1
        self.frame = feature_frame(frame)
        self.reference = curve.predict(model.predict(self.frame))
        change = np.zeros(len(frame))
        if tick >= 4 and scenario == "prevalence":
            change[:] = 0.9
        if tick >= 4 and scenario == "subgroup":
            change[np.asarray(frame["part"] == "DME")] = 1.8
        p = expit(logit(np.clip(self.reference, 1e-9, 1 - 1e-9)) + change)
        self._labels = (rng.random(len(frame)) < p).astype(int)
        self.tick = tick

    def reveal(self, indices, cutoff, delay):
        if self.tick + delay > cutoff:
            raise ValueError("Simulation feedback is unavailable at this cutoff.")
        return [Feedback(self.tick, self.tick + delay, row, int(label))
                for row, label in zip(self.frame.iloc[indices].to_dict("records"),
                                      self._labels[indices], strict=True)]

    def metrics(self, scores):
        return performance(self.frame, self._labels, scores)


def simulate(reference, seed, scenario, delay):
    rng = np.random.default_rng(seed)
    feedback = []
    pending = []
    active: dict = {}
    metrics = []
    outcomes = {mode: {"promoted": 0, "rejected": 0, "first_promotion": None} for mode in MODES}
    detect = None
    for tick in range(8):
        if len(pending) >= delay:
            past, indices = pending.pop(0)
            revealed = past.reveal(indices, tick, delay)
            feedback.extend(revealed)
            residual = np.mean([row.outcome for row in revealed]) - past.reference[indices].mean()
            if abs(residual) >= 0.12 and detect is None:
                detect = tick
        wave = SimulatedWave(reference, rng, tick, scenario)
        pending.append((wave, rng.choice(500, size=100, replace=False)))
        metrics.append({"tick": tick, "mode": "no-update", **wave.metrics(wave.reference), "inference_ms": 0.0})
        for mode in MODES:
            status = "insufficient_periods"
            if len({item.arrival for item in feedback}) >= 3:
                try:
                    model, curve, report = fit_candidate(reference, feedback, tick, mode)
                    if passed(report):
                        active[mode] = (model, curve)
                        outcomes[mode]["promoted"] += 1
                        if outcomes[mode]["first_promotion"] is None:
                            outcomes[mode]["first_promotion"] = tick
                        status = "validated_simulated_approval"
                    else:
                        outcomes[mode]["rejected"] += 1
                        status = "rejected_gate"
                except ValueError:
                    outcomes[mode]["rejected"] += 1
                    status = "failed_fit"
            started = time.perf_counter()
            if mode in active:
                model, curve = active[mode]
                score = curve.predict(model.predict(wave.frame))
            else:
                score = wave.reference
            elapsed = 1000 * (time.perf_counter() - started)
            metrics.append({"tick": tick, "mode": mode, "decision": status, **wave.metrics(score),
                            "inference_ms": elapsed})
    return {"seed": seed, "scenario": scenario, "delay": delay, "detection_tick": detect,
            "lifecycle": outcomes, "metrics": metrics}


def summarize(rows):
    summary = []
    for scenario in SCENARIOS:
        for delay in (1, 2):
            subset = [row for row in rows if row["scenario"] == scenario and row["delay"] == delay]
            for mode in MODES:
                paired = {key: [] for key in ("brier", "ap", "yield", "ece", "review_minutes", "inference_ms")}
                recovery = []
                for row in subset:
                    base = [m for m in row["metrics"] if m["mode"] == "no-update" and m["tick"] >= 4]
                    cand = [m for m in row["metrics"] if m["mode"] == mode and m["tick"] >= 4]
                    recovered = [a["tick"] - 4 for a, b in zip(cand, base, strict=True)
                                 if a["brier"] <= b["brier"] - 0.001]
                    recovery.append(min(recovered) if recovered else None)
                    for key in paired:
                        differences = [a[key] - b[key] for a, b in zip(cand, base, strict=True)
                                       if a[key] is not None and b[key] is not None]
                        paired[key].append(float(np.mean(differences)) if differences else None)
                summary.append({
                    "scenario": scenario, "delay": delay, "mode": mode, "paired_seeds": len(subset),
                    "promoted": sum(row["lifecycle"][mode]["promoted"] for row in subset),
                    "rejected": sum(row["lifecycle"][mode]["rejected"] for row in subset),
                    "first_recovery_since_wave_4": mean_with_mcse(recovery),
                    "detection_delay_after_eligible_wave_4": mean_with_mcse([
                        row["detection_tick"] - (4 + delay) for row in subset
                        if row["detection_tick"] is not None and row["detection_tick"] >= 4 + delay]),
                    "detections_before_eligible_wave_4": sum(
                        row["detection_tick"] is not None and row["detection_tick"] < 4 + delay for row in subset),
                    "post_wave_4_paired_difference": {key: mean_with_mcse(value) for key, value in paired.items()},
                })
    return summary


def run(reference, output, seeds, protocol):
    started = time.perf_counter()
    config = {"hypothesis": "H5", "scope": "synthetic", "scenarios": SCENARIOS, "delays": [1, 2], "waves": 8,
              "cases_per_wave": 500, "reviews_per_wave": 100, "seeds": seeds, "protocol_sha256": sha256(protocol),
              "reference": reference[2]["version"], "reference_scorecard": reference[2]["scorecard_sha256"],
              "code": {name: sha256(Path(__file__).with_name(name)) for name in ("learning.py", "lifecycle_study.py")}}
    signature = digest(config)
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    with FileLock(output / ".lock", timeout=0):
        for seed in seeds:
            path = output / "seeds" / f"{seed}.json"
            if path.exists():
                saved = read_json(path)
                if saved["config_sha256"] != signature or saved["rows_sha256"] != digest(saved["rows"]):
                    raise ValueError("H5 seed checkpoint is incompatible or corrupt.")
                batch = saved["rows"]
            else:
                batch = [simulate(reference, seed, scenario, delay)
                         for scenario in SCENARIOS for delay in (1, 2)]
                write_json(path, {"config_sha256": signature, "rows_sha256": digest(batch), "rows": batch})
            rows.extend(batch)
        result = {"config": config, "config_sha256": signature, "runs": len(rows),
                  "status": "complete" if seeds == SEEDS else "development",
                  "summary": summarize(rows), "elapsed_seconds": time.perf_counter() - started,
                  "seed_artifacts": {str(seed): sha256(output / "seeds" / f"{seed}.json") for seed in seeds}}
        write_json(output / "h5.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/lifecycle-study"))
    parser.add_argument("--development", action="store_true")
    args = parser.parse_args()
    seeds = tuple(range(10, 15)) if args.development else SEEDS
    result = run(Registry(Path("artifacts/registry")).active(), args.output, seeds,
                 Path("docs/RESEARCH_PROTOCOL_EXTENSIONS.md"))
    print(f"H5 {result['status']}: {result['runs']} scenario runs")


if __name__ == "__main__":
    main()
