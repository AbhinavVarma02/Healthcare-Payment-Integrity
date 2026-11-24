from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import pytest

from payment_integrity.model_io import save_scorecard
from payment_integrity.models import Sigmoid, fit_lookup
from payment_integrity.monitoring import assess, development_thresholds
from payment_integrity.registry import Registry
from payment_integrity.storage import sha256


@pytest.fixture
def synthetic_model(tmp_path):
    frame = pd.DataFrame({"part": ["Part B", "DME"] * 30, "provider_type": ["Lab", "Equipment"] * 30,
                          "visible_lines": [1, 2] * 30, "provider_types": [1, 1] * 30})
    y = np.array([0, 1] * 30)
    model = fit_lookup(frame, y)
    source = tmp_path / "source"
    curve = Sigmoid(-0.1, 1.1)
    save_scorecard(source, model, curve)
    registry = Registry(tmp_path / "registry")
    for name in ("first", "second"):
        registry.install(name, source, sha256(source / "scorecard.json"),
                         {"schema": 1, "version": name}, {"model_id": "synthetic"})
    registry.activate("first")
    return registry, frame, model, curve


def test_atomic_activation_corruption_and_rollback(synthetic_model):
    registry, frame, expected, expected_curve = synthetic_model
    model, curve, metadata = registry.active()
    assert metadata["version"] == "first"
    np.testing.assert_allclose(curve.predict(model.predict(frame)),
                               expected_curve.predict(expected.predict(frame)))
    registry.activate("second")
    with ThreadPoolExecutor(max_workers=3) as pool:
        assert set(pool.map(lambda _: registry.active()[2]["version"], range(12))) == {"second"}
    (registry.root / "second" / "scorecard.json").write_text("{}")
    with pytest.raises(ValueError, match="integrity verification failed"):
        registry.active()
    assert registry.rollback() == "first"
    assert registry.active()[2]["version"] == "first"
    with pytest.raises(ValueError, match="Invalid registered"):
        registry.manifest("../second")


def test_drift_alerts_and_label_availability():
    base = {"count": 100, "categories": [99, 0, 1],
            "score_histogram": [100, 0], "unknown_rate": 0.01, "missing_rate": 0.0}
    adverse = {"count": 100, "categories": [1, 10, 89],
               "score_histogram": [0, 100], "unknown_rate": 0.89, "missing_rate": 0.1}
    thresholds = development_thresholds(base, base)
    report = assess(base, adverse, thresholds)
    assert len(report["covariate_alerts"]) == 4
    assert report["measured_performance"] is None
    measured = assess(base, adverse, thresholds, np.array([1, np.nan]), np.array([0.5, 0.8]))
    assert measured["measured_performance"]["brier"] == 0.25
