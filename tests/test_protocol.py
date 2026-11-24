import subprocess

import pytest

from payment_integrity.protocol import FROZEN_PATHS, load_freeze


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
