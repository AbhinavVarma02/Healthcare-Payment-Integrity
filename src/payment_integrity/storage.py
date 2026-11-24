"""Small, atomic local artifact operations."""

import hashlib
import json
import os
import tempfile
import time
from collections.abc import Callable
from pathlib import Path


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _retry_sharing_violation[T](operation: Callable[[], T]) -> T:
    # Windows can briefly deny either side of an atomic file replacement.
    for attempt in range(1, 8):
        try:
            return operation()
        except PermissionError:
            if os.name != "nt":
                raise
            time.sleep(0.01 * attempt)
    return operation()


def atomic_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".pending-")
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        _retry_sharing_violation(lambda: os.replace(temporary, path))
    finally:
        Path(temporary).unlink(missing_ok=True)


def write_json(path: Path, value) -> None:
    atomic_bytes(path, (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode())


def read_json(path: Path):
    return json.loads(_retry_sharing_violation(lambda: path.read_text(encoding="utf-8")))
