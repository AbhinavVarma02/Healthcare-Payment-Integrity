import subprocess

import pytest

from payment_integrity.protocol import FROZEN_PATHS, Freeze, load_freeze, verify_vintage
from payment_integrity.storage import sha256
from payment_integrity.study import verified_predictions


def test_freeze_requires_exact_committed_configuration(tmp_path):
    def git(*args):
        return subprocess.run(["git", *args], cwd=tmp_path, capture_output=True, check=True).stdout

    git("init")
    for filename in FROZEN_PATHS:
        path = tmp_path / filename
        path.parent.mkdir(exist_ok=True)
        path.write_text(
            '{"train":[2021],"calibration":2022,"development":2023,"holdout":[2024,2025]}',
            encoding="utf-8")
    git("add", "--", *FROZEN_PATHS)
    git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", "fixture")
    commit = git("rev-parse", "HEAD").decode().strip()
    assert len(load_freeze(tmp_path, commit).sha256) == 64
    (tmp_path / FROZEN_PATHS[0]).write_text("{}")
    with pytest.raises(ValueError, match="Frozen file differs"):
        load_freeze(tmp_path, commit)


def test_source_metadata_and_downstream_predictions_are_bound(tmp_path):
    source = {"version": "2024-01-04", "submission_end": "2022-06-30"}
    freeze = Freeze("commit", "digest", {"source_sha256": {"2023": "csv"}}, {"2023": source})
    manifest = {"reporting_year": 2023, "source_sha256": "csv", "source": source}
    verify_vintage(2023, manifest, freeze)
    with pytest.raises(ValueError, match="differs from frozen vintage"):
        verify_vintage(2023, {**manifest, "source": {**source, "version": "2022-01-01"}}, freeze)

    path = tmp_path / "predictions-2025.parquet"
    path.write_bytes(b"original snapshot")
    cohort = {"year": 2025, "predictions_sha256": sha256(path)}
    path.write_bytes(b"changed snapshot")
    with pytest.raises(ValueError, match="differs from the verified H1 run"):
        verified_predictions(tmp_path, cohort)
