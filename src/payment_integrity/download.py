"""Acquire the allowlisted CMS files, with bounded verified local caching."""

import argparse
import csv
import os
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from .storage import read_json, sha256, write_json

MAX_BYTES = 20_000_000


def fetch(url: str, path: Path, kind: str, refresh: bool = False) -> dict:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.netloc != "data.cms.gov" or parsed.fragment:
        raise ValueError("Expected an official HTTPS data.cms.gov URL.")
    manifest = path.with_suffix(path.suffix + ".json")
    if path.is_file() and manifest.is_file() and not refresh:
        previous = read_json(manifest)
        if previous["url"] == url and previous["sha256"] == sha256(path):
            return previous
        raise ValueError(f"Cache integrity failed for {path.name}. Repair with --refresh.")
    path.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(path.parent).free < 2 * MAX_BYTES:
        raise OSError("Insufficient disk for bounded acquisition.")
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".download-")
    os.close(descriptor)
    pending = Path(temporary)
    try:
        result = subprocess.run(
            ["curl", "--fail", "--silent", "--show-error", "--proto", "=https",
             "--connect-timeout", "10", "--max-time", "25", "--retry", "2",
             "--retry-max-time", "45", "--max-filesize", str(MAX_BYTES),
             "--output", str(pending), url],
            check=True, timeout=55
        )
        size = pending.stat().st_size
        if not 0 < size <= MAX_BYTES:
            raise ValueError("Unexpected source size.")
        if kind == "csv":
            with pending.open(encoding="utf-8-sig", newline="") as stream:
                if len(next(csv.reader(stream))) < 5:
                    raise ValueError("The resource did not return a CSV header.")
        else:
            read_json(pending)
        record = dict(url=url, sha256=sha256(pending), bytes=size, exit_code=result.returncode,
                      retrieved_utc=datetime.now(UTC).isoformat(timespec="seconds"))
        pending.replace(path)
        write_json(manifest, record)
        return record
    finally:
        pending.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("years", type=int, nargs="+")
    parser.add_argument("--root", type=Path, default=Path("data/raw"))
    parser.add_argument("--sources", type=Path, default=Path("configs/cms_sources.json"))
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    sources = read_json(args.sources)
    for year in sorted(set(args.years)):
        source = sources[str(year)]
        for key, extension in (("dictionary", "json"), ("csv", "csv")):
            name = f"{year}-dictionary.json" if key == "dictionary" else f"{year}.{extension}"
            evidence = fetch(source[key], args.root / name, key, args.refresh)
            print(year, key, evidence["bytes"], evidence["sha256"], flush=True)


if __name__ == "__main__":
    main()
