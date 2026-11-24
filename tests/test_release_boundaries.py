"""Validate source, serving and export boundaries using isolated fixtures."""

from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from payment_integrity.api import LOG, create_app
from payment_integrity.cohorts import (
    SCHEMA,
    development_outcomes,
    feature_snapshot,
    project_csv,
    write_parquet,
)
from payment_integrity.publication import FAVICON, HEADERS, audit_paths
from payment_integrity.storage import sha256, write_json

CLAIM = {"part": "DME", "provider_type": "Pharmacy", "visible_lines": 2, "provider_types": 1}


@pytest.mark.parametrize("content", ["", "Claim,Part,Outcome\n"], ids=["empty", "unknown-header"])
def test_source_rejects_schema_drift_before_projecting(tmp_path, content):
    source = tmp_path / "study.csv"
    source.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match="unrecognized source schema"):
        project_csv(source, 2025, False)


@pytest.mark.parametrize("table,read", [("features", feature_snapshot), ("development-outcomes", development_outcomes)])
def test_transplanted_snapshot_is_rejected_even_with_matching_content_hash(tmp_path, table, read):
    folder = tmp_path / "ry=2023"
    path = folder / f"{table}.parquet"
    write_parquet(path, pd.DataFrame({"claim_key": ["synthetic"]}))
    write_json(folder / "manifest.json", {"schema": SCHEMA, "reporting_year": 2022, "tables": {table: sha256(path)}})
    with pytest.raises(ValueError, match="reporting year"):
        read(tmp_path, 2023)


def test_hash_attestation_cannot_hide_outcome_column_in_features(tmp_path):
    folder = tmp_path / "ry=2024"
    path = folder / "features.parquet"
    write_parquet(path, pd.DataFrame([{"claim_key": "synthetic", **CLAIM, "disagreement": 1}]))
    write_json(folder / "manifest.json", {"schema": SCHEMA, "reporting_year": 2024, "tables": {"features": sha256(path)}})
    with pytest.raises(ValueError, match="Unexpected feature columns"):
        feature_snapshot(tmp_path, 2024)


def test_snapshot_refuses_valid_parquet_with_wrong_hash(tmp_path):
    folder = tmp_path / "ry=2023"
    path = folder / "features.parquet"
    write_parquet(path, pd.DataFrame([{"claim_key": "synthetic", **CLAIM}]))
    write_json(folder / "manifest.json", {"schema": SCHEMA, "reporting_year": 2023, "tables": {"features": "0" * 64}})
    with pytest.raises(ValueError, match="Corrupt or incompatible"):
        feature_snapshot(tmp_path, 2023)


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path), base_url="http://localhost") as client:
        yield client


@pytest.mark.parametrize("changes", [
    {"part": "Part A"}, {"visible_lines": 0}, {"visible_lines": 251}, {"visible_lines": 1.5},
    {"provider_types": 3}, {"provider_types": True}, {"provider_type": " "}, {"provider_type": "P" * 161},
], ids=["part", "zero-lines", "line-bound", "fractional-lines", "category-count", "boolean-count",
        "missing-provider", "provider-bound"])
def test_invalid_score_schema_returns_redacted_error(client, changes):
    response = client.post("/v1/score", json=CLAIM | changes)
    assert response.status_code == 422
    assert response.json()["error"] == {"code": "invalid_input",
                                        "message": "Input did not match the required request schema."}


@pytest.mark.parametrize("path,body,code", [
    ("/v1/audit-plan", {"claims": [CLAIM], "capacity": 2}, "invalid_input"),
    ("/v1/audit-plan", {"claims": [CLAIM], "capacity": 1, "exploration_count": 2}, "invalid_input"),
    ("/v1/audit-plan", {"claims": [CLAIM], "capacity": 1, "strategy": "time"}, "invalid_input"),
    ("/v1/audit-plan", {"claims": [CLAIM], "capacity": 1, "strategy": "time", "minute_budget": 0,
                        "group_cap": 1}, "invalid_input"),
    ("/v1/operations/events/nonexistent?role=analyst", {"event_id": "a", "idempotency_key": "a",
      "run_id": "r", "event_tick": 0, "advance_to": 1}, "command_mismatch"),
], ids=["capacity", "reserve", "missing-minute-budget", "time-with-count-cap", "operation-schema"])
def test_infeasible_api_requests_fail_before_state_changes(client, path, body, code):
    response = client.post(path, json=body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == code


def test_nonfinite_json_does_not_return_a_raw_validation_trace(client):
    response = client.post("/v1/score", content=b'{"visible_lines":NaN}', headers={"content-type": "application/json"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_input"
    assert "NaN" not in response.text


def test_missing_registry_has_safe_error_and_no_raw_input_in_application_log(client, caplog):
    caplog.set_level("INFO", logger=LOG.name)
    response = client.post("/v1/score", json=CLAIM | {"provider_type": "Synthetic Sentinel"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "model_unavailable"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-request-id"]
    assert "Synthetic Sentinel" not in caplog.text + response.text
    assert "/v1/score" in caplog.text


def test_loopback_cors_preflight_keeps_browser_scope_local(client):
    request = {"access-control-request-method": "POST", "access-control-request-headers": "content-type"}
    allowed = client.options("/v1/score", headers=request | {"origin": "http://127.0.0.1:5173"})
    denied = client.options("/v1/score", headers=request | {"origin": "https://outside.invalid"})
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
    assert denied.status_code == 400
    assert "access-control-allow-origin" not in denied.headers


@pytest.fixture
def static_export(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text('<script src="./assets/ui.js"></script>', encoding="utf-8")
    (tmp_path / "assets" / "ui.js").write_text('console.log("synthetic")', encoding="utf-8")
    for name in ("404.html", "THIRD_PARTY_NOTICES.txt"):
        (tmp_path / name).write_text("test fixture", encoding="utf-8")
    (tmp_path / "_headers").write_text(HEADERS, encoding="utf-8")
    (tmp_path / "study.json").write_bytes(Path("web/public/study.json").read_bytes())
    return tmp_path


def test_publication_accepts_pinned_reviewed_aggregate_with_referenced_assets(static_export):
    entry = static_export / "index.html"
    entry.write_text(f'{entry.read_text(encoding="utf-8")}<link rel="icon" href="{FAVICON}">', encoding="utf-8")
    result = audit_paths(static_export)
    assert len(result) == 6
    assert result["study.json"] == "eaf69560201573458508a359471a70d5720226e8e37d75d77b500d10db222b32"


@pytest.mark.parametrize("name,value,reason", [
    ("assets/unlinked.js", b"", "entry-point references"),
    ("assets/ui.js", b"const api = 'http://127.0.0.1:8000';", "Local API reference"),
    ("assets/ui.js", b'const column = "claim_key";', "Restricted source token"),
    ("artifact.json", b"{}", "outside the static allowlist"),
    ("index.html", b'<script src="./assets/ui.js"></script><script src="https://cdn.invalid/ui.js"></script>',
     "entry-point references"),
    ("index.html", b'<script src="./assets/ui.js"></script><link rel="icon" href="data:image/svg+xml,other">',
     "entry-point references"),
    ("_headers", b"", "reviewed policy"),
], ids=["orphaned-asset", "loopback-in-build", "raw-identifier-schema", "unreviewed-output", "remote-script",
        "unreviewed-icon", "changed-csp"])
def test_publication_rejects_invalid_export_paths_and_contents(static_export, name, value, reason):
    (static_export / name).write_bytes(value)
    with pytest.raises(ValueError, match=reason):
        audit_paths(static_export)


def test_publication_rejects_parseable_but_unreviewed_aggregate(static_export):
    path = static_export / "study.json"
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="reviewed aggregate"):
        audit_paths(static_export)
