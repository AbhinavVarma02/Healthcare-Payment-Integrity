from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from payment_integrity.api import MAX_BODY, create_app
from payment_integrity.model_io import save_scorecard
from payment_integrity.models import Sigmoid, fit_lookup
from payment_integrity.registry import Registry
from payment_integrity.storage import sha256


def test_endpoints_enforce_schema_and_preserve_scoring_parity(tmp_path: Path):
    registry = Registry(tmp_path / "registry")
    app = create_app(tmp_path, registry.root)
    row = {"part": "DME", "provider_type": "Synthetic",
           "visible_lines": 2, "provider_types": 1}
    with TestClient(app, base_url="http://localhost") as client:
        assert client.get("/health").status_code == 200
        assert client.get("/ready").status_code == 503
        model = fit_lookup(pd.DataFrame([row] * 40), [0, 1, 0, 0] * 10)
        curve = Sigmoid(-0.1, 0.9)
        source = tmp_path / "source"
        save_scorecard(source, model, curve)
        registry.install("fixture", source, sha256(source / "scorecard.json"),
                         {"scope": "synthetic"}, {"model_id": "fixture"})
        registry.activate("fixture")
        assert client.get("/ready").json()["status"] == "research-only"
        assert client.get("/v1/models").json()["versions"] == ["fixture"]
        single = client.post("/v1/score", json=row)
        assert single.status_code == 200
        expected = curve.predict(model.predict(pd.DataFrame([row])))[0]
        assert single.json()["calibrated_risk"] == expected
        assert single.json() == client.post("/v1/score/batch", json={"claims": [row, row]}).json()[
            "predictions"][0]
        assert client.post("/v1/score", json={**row, "visible_lines": "2"}).status_code == 422
        assert client.post("/v1/score", json={**row, "disagreement": 1}).status_code == 422
        assert client.post("/v1/score", content=b"x" * (MAX_BODY + 1)).status_code == 413
        assert client.get("/v1/validation/fixture").json()["scope"] == "synthetic"
        assert client.get("/v1/runs/missing").status_code == 404
        plan = client.post("/v1/audit-plan", json={"claims": [row, row], "capacity": 1})
        assert plan.status_code == 200
        assert plan.json()["selected_input_positions"] == [0]
        assert client.get("/health", headers={"host": "unexpected.invalid"}).status_code == 400
