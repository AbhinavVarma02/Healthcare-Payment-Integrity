"""Versioned local scorecards with integrity checks and atomic activation."""

import importlib.metadata
import re
import shutil
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from filelock import FileLock

from .cohorts import FEATURES, SCHEMA
from .model_io import load_scorecard
from .storage import read_json, sha256, write_json

VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
LIBRARIES = ("numpy", "pandas", "scikit-learn", "xgboost")


def valid_version(version):
    if not VERSION.fullmatch(version):
        raise ValueError("Invalid registered model version.")
    return version


def library_versions():
    return {name: importlib.metadata.version(name) for name in LIBRARIES}


class Registry:
    def __init__(self, root: Path):
        self.root = root

    @contextmanager
    def writer(self):
        self.root.mkdir(parents=True, exist_ok=True)
        with FileLock(self.root / ".write-lock", timeout=0):
            yield

    @property
    def pointer(self):
        return self.root / "active.json"

    def versions(self):
        if not self.root.exists():
            return []
        return [child.name for child in sorted(self.root.iterdir())
                if child.is_dir() and VERSION.fullmatch(child.name) and (child / "manifest.json").is_file()]

    def manifest(self, version):
        folder = self.root / valid_version(version)
        result = read_json(folder / "manifest.json")
        if (result["schema"] != 1 or result["feature_schema"] != SCHEMA
                or result["features"] != list(FEATURES) or result["version"] != version
                or result["status"] != "research-only"):
            raise ValueError("Model manifest is incompatible.")
        return result

    def load(self, version):
        metadata = self.manifest(version)
        if metadata["libraries"] != library_versions():
            raise ValueError("Model library versions differ from the current environment.")
        model, curve = load_scorecard(self.root / version, metadata["scorecard_sha256"])
        if sha256(self.root / version / "validation.json") != metadata["validation_sha256"]:
            raise ValueError("Model validation artifact integrity verification failed.")
        return model, curve, metadata

    def install(self, version, source, scorecard_hash, validation, provenance):
        dest = self.root / valid_version(version)
        # Verify source before copying and verify again after copying to a private staging directory.
        load_scorecard(source, scorecard_hash)
        with self.writer():
            with TemporaryDirectory(dir=self.root) as temporary:
                staging = Path(temporary) / version
                staging.mkdir()
                for name in ("scorecard.json", "booster.json"):
                    if (source / name).is_file():
                        shutil.copyfile(source / name, staging / name)
                load_scorecard(staging, scorecard_hash)
                write_json(staging / "validation.json", validation)
                manifest = {
                    "schema": 1, "version": version, "feature_schema": SCHEMA,
                    "features": list(FEATURES), "status": "research-only", "provenance": provenance,
                    "libraries": library_versions(), "scorecard_sha256": scorecard_hash,
                    "validation_sha256": sha256(staging / "validation.json"),
                    "created_utc": datetime.now(UTC).isoformat(timespec="seconds"),
                }
                if dest.exists():
                    existing = self.manifest(version)
                    if any(existing[key] != manifest[key] for key in manifest if key != "created_utc"):
                        raise ValueError("An immutable model version already exists with different contents.")
                    self.load(version)
                else:
                    write_json(staging / "manifest.json", manifest)
                    staging.rename(dest)

    def active(self):
        return self.load(read_json(self.pointer)["active"])

    def activate(self, version):
        with self.writer():
            self.load(version)
            current = read_json(self.pointer) if self.pointer.exists() else {}
            if current.get("active") != version:
                write_json(self.pointer, {"active": version, "previous": current.get("active")})

    def rollback(self):
        with self.writer():
            current = read_json(self.pointer)
            prior = current.get("previous")
            if not prior:
                raise ValueError("No prior verified model is available for rollback.")
            self.load(prior)
            write_json(self.pointer, {"active": prior, "previous": current["active"]})
            return prior
