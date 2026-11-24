"""Verify committed research settings and isolate confirmatory outcome access."""

import hashlib
import re
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from .cohorts import HOLDOUT, development_outcomes, feature_snapshot, project_csv
from .storage import read_json, sha256, write_json

FROZEN_PATHS = (
    "configs/protocol.json",
    "configs/cms_sources.json",
    "configs/hypotheses.yaml",
    "configs/experiment_registry.yaml",
    "docs/research_protocol.md",
)


@dataclass(frozen=True)
class Freeze:
    commit: str
    sha256: str
    config: dict
    sources: dict


def git(root: Path, *commands: str) -> bytes:
    result = subprocess.run(["git", *commands], cwd=root, capture_output=True, check=True)
    return result.stdout


def load_freeze(root: Path, commit: str) -> Freeze:
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Provide the full commit SHA for the frozen protocol.")
    git(root, "merge-base", "--is-ancestor", commit, "HEAD")
    combined = hashlib.sha256()
    for name in FROZEN_PATHS:
        committed = git(root, "show", f"{commit}:{name}")
        working = (root / name).read_bytes().replace(b"\r\n", b"\n")
        if working != committed:
            raise ValueError(f"Frozen file differs from {commit[:12]}: {name}")
        combined.update(name.encode() + b"\x00" + hashlib.sha256(committed).digest())
    config = read_json(root / FROZEN_PATHS[0])
    if config["holdout"] != list(HOLDOUT) or max(config["train"]) >= config["calibration"]:
        raise ValueError("Invalid frozen year boundaries.")
    if not config["calibration"] < config["development"] < min(config["holdout"]):
        raise ValueError("Calibration, development and holdout periods must be disjoint.")
    return Freeze(commit, combined.hexdigest(), config, read_json(root / FROZEN_PATHS[1]))


def verify_vintage(year: int, manifest: dict, freeze: Freeze) -> None:
    if (manifest["source_sha256"] != freeze.config["source_sha256"][str(year)]
            or manifest["reporting_year"] != year or manifest["source"] != freeze.sources[str(year)]):
        raise ValueError(f"{year}: source differs from frozen vintage.")


class Evaluator:
    """Only the evaluator can join the holdout labels to an attested feature snapshot."""

    def __init__(self, workspace: Path, freeze_id: str):
        self.workspace = workspace
        self.freeze = load_freeze(workspace, freeze_id)

    def outcomes(self, year: int, keys, purpose: str) -> np.ndarray:
        if purpose not in {"H1-H2", "H3", "H4", "governance"}:
            raise ValueError("Purpose is outside the frozen evaluator contract.")
        root = self.workspace / "data" / "curated"
        features, manifest = feature_snapshot(root, year)
        verify_vintage(year, manifest, self.freeze)
        if list(keys) != features["claim_key"].tolist():
            raise ValueError("Outcome request differs from the frozen feature frame.")
        if year in HOLDOUT:
            source = self.workspace / "data" / "raw" / f"{year}.csv"
            if sha256(source) != manifest["source_sha256"]:
                raise ValueError("Raw source no longer matches the frozen feature snapshot.")
            exposure = self.workspace / "artifacts" / "holdout-exposure" / f"{purpose}-{year}.json"
            if exposure.is_file():
                record = read_json(exposure)
                if record["freeze"] != self.freeze.sha256 or record["source"] != sha256(source):
                    raise ValueError("Prior exposure exists under a different protocol or vintage.")
            else:
                write_json(exposure, {
                    "year": year, "purpose": purpose, "freeze": self.freeze.sha256,
                    "commit": self.freeze.commit, "source": manifest["source_sha256"],
                    "first_access_attempt_utc": datetime.now(UTC).isoformat(timespec="seconds"),
                })
            projected, labels, _, _ = project_csv(source, year, True)
            if list(projected.itertuples(index=False, name=None)) != list(
                    features.itertuples(index=False, name=None)):
                raise ValueError("Holdout features differ from the independently reprojected frozen source.")
        else:
            labels = development_outcomes(root, year)
        return labels.set_index("claim_key").loc[keys, "disagreement"].to_numpy(
            dtype=float, na_value=np.nan)
