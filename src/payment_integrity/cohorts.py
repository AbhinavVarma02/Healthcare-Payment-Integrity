"""Build claim-group snapshots from an explicitly projected CERT schema."""

import argparse
import csv
import hashlib
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory

import duckdb
import pandas as pd

from .storage import read_json, sha256, write_json

HEADER = ("claim_control_number", "Part", "DRG", "HCPCS Procedure Code", "Provider Type",
          "Type of Bill", "Review Decision", "Error Code")
PARTS = {"1. Part B": "Part B", "2. DME MAC": "DME"}
OTHER_PARTS = {"3. Part A(Excluding Inpatient Hospital PPS)", "4. Part A(Inpatient Hospital PPS)"}
FEATURES = ("part", "provider_type", "visible_lines", "provider_types")
OUTCOMES = {"Agree": 0, "Disagree": 1}
DEVELOPMENT = tuple(range(2018, 2024))
HOLDOUT = (2024, 2025)
SCHEMA = "cert-claim-v1"


@dataclass
class ClaimGroup:
    part: str
    count: int = 0
    providers: Counter = field(default_factory=Counter)
    results: Counter = field(default_factory=Counter)
    invalid: bool = False


def project_csv(path: Path, year: int, include_outcomes: bool):
    groups: dict[str, ClaimGroup] = {}
    counts = Counter()
    quarantine = []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream, strict=True)
        if tuple(next(reader)) != HEADER:
            raise ValueError(f"{year}: unrecognized source schema")
        for row_number, row in enumerate(reader, 2):
            counts["rows"] += 1
            if len(row) != len(HEADER) or not row[0].strip():
                counts["malformed_rows"] += 1
                quarantine.append({"row": row_number, "reason": "width_or_key"})
                if row and row[0].strip():
                    groups.setdefault(row[0].strip(), ClaimGroup("")).invalid = True
                continue
            key, part = row[0].strip(), row[1].strip()
            group = groups.setdefault(key, ClaimGroup(part))
            group.count += 1
            if group.part != part or part not in (set(PARTS) | OTHER_PARTS):
                group.invalid = True
            if part in PARTS:
                counts["in_scope_rows"] += 1
                group.providers[row[4].strip() or "Missing"] += 1
                if include_outcomes:
                    group.results[OUTCOMES.get(row[6].strip())] += 1
            elif part in OTHER_PARTS:
                counts["out_of_scope_rows"] += 1
            else:
                counts["unrecognized_part_rows"] += 1
    features, outcomes = [], []
    counts["claim_groups"] = len(groups)
    for key, group in sorted(groups.items()):
        if group.invalid:
            counts["quarantined_groups"] += 1
            continue
        if group.part not in PARTS:
            counts["out_of_scope_groups"] += 1
            continue
        claim_key = hashlib.sha256(f"{year}:{key}".encode()).hexdigest()
        primary = min(group.providers, key=lambda value: (-group.providers[value], value))
        features.append((claim_key, PARTS[group.part], primary, group.count, len(group.providers)))
        counts["feature_groups"] += 1
        counts["feature_rows"] += group.count
        if include_outcomes:
            target = None if group.results[None] else int(group.results[1] > 0)
            outcomes.append((claim_key, target))
            counts["unknown_outcomes"] += int(target is None)
            counts["mixed_outcomes"] += int(bool(group.results[0] and group.results[1]))
            counts["disagreement_groups"] += int(target == 1)
    feature_frame = pd.DataFrame(features, columns=("claim_key", *FEATURES)).astype(
        {"visible_lines": "int64", "provider_types": "int64"})
    label_frame = None
    if include_outcomes:
        label_frame = pd.DataFrame(outcomes, columns=("claim_key", "disagreement")).astype(
            {"disagreement": "Int8"})
    return feature_frame, label_frame, dict(counts), quarantine


def write_parquet(path: Path, frame: pd.DataFrame):
    path.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=path.parent) as temporary:
        pending = Path(temporary) / "table.parquet"
        with duckdb.connect(config={"threads": 1}) as connection:
            connection.register("snapshot", frame)
            connection.execute("COPY snapshot TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(pending)])
        pending.replace(path)


def read_parquet(path: Path) -> pd.DataFrame:
    with duckdb.connect(config={"threads": 1}) as connection:
        return connection.execute("SELECT * FROM read_parquet(?)", [str(path)]).fetchdf()


def partition(root: Path, year: int) -> Path:
    return root / f"ry={year}"


def check_partition(folder: Path, manifest: dict, kind: str) -> Path:
    path = folder / f"{kind}.parquet"
    expected = manifest["tables"][kind]
    if manifest["schema"] != SCHEMA or sha256(path) != expected:
        raise ValueError(f"Corrupt or incompatible {kind} snapshot in {folder.name}.")
    return path


def build_year(raw: Path, root: Path, sources: dict, year: int, rebuild: bool = False):
    """Project the sealed years without interpreting their review decision column."""
    source = raw / f"{year}.csv"
    acquisition = read_json(raw / f"{year}.csv.json")
    version = sources[str(year)]
    source_hash = sha256(source)
    if acquisition["sha256"] != source_hash or acquisition["url"] != version["csv"]:
        raise ValueError(f"{year}: source manifest failed")
    folder = partition(root, year)
    output = folder / "manifest.json"
    include_outcomes = year in DEVELOPMENT
    if output.is_file() and not rebuild:
        cached = read_json(output)
        if cached["source_sha256"] == source_hash and cached["source"] == version:
            for kind in cached["tables"]:
                check_partition(folder, cached, kind)
            return cached
    features, labels, counts, quarantine = project_csv(source, year, include_outcomes)
    tables = {"features": features}
    if labels is not None:
        tables["development-outcomes"] = labels
    checksums = {}
    for name, frame in tables.items():
        path = folder / f"{name}.parquet"
        write_parquet(path, frame)
        checksums[name] = sha256(path)
    manifest = {"schema": SCHEMA, "reporting_year": year, "source": version, "source_sha256": source_hash,
                    "source_bytes": acquisition["bytes"], "retrieved_utc": acquisition["retrieved_utc"],
                    "counts": counts, "tables": checksums}
    if quarantine:
        write_json(folder / "quarantine.json", quarantine)
    write_json(output, manifest)
    return manifest


def feature_snapshot(root: Path, year: int) -> tuple[pd.DataFrame, dict]:
    folder = partition(root, year)
    manifest = read_json(folder / "manifest.json")
    return read_parquet(check_partition(folder, manifest, "features")), manifest


def development_outcomes(root: Path, year: int) -> pd.DataFrame:
    if year not in DEVELOPMENT:
        raise ValueError("This interface provides development outcomes only.")
    folder = partition(root, year)
    manifest = read_json(folder / "manifest.json")
    return read_parquet(check_partition(folder, manifest, "development-outcomes"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("years", type=int, nargs="+", choices=DEVELOPMENT + HOLDOUT)
    parser.add_argument("--raw", type=Path, default=Path("data/raw"))
    parser.add_argument("--root", type=Path, default=Path("data/curated"))
    parser.add_argument("--sources", type=Path, default=Path("configs/cms_sources.json"))
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    sources = read_json(args.sources)
    for year in sorted(set(args.years)):
        result = build_year(args.raw, args.root, sources, year, args.rebuild)
        print(year, result["counts"], flush=True)


if __name__ == "__main__":
    main()
