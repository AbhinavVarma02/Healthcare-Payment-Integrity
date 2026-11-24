"""Audit the staged Git tree, history and reviewed aggregate on the local filesystem."""

import argparse
import re
import subprocess
from pathlib import Path

ALLOWLIST = Path("configs/release_allowlist.txt")
SECRETS = (
    re.compile(rb"(?m)^-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----\r?\n[A-Za-z0-9+/]"),
    re.compile(rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    re.compile(rb"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    re.compile(rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{28,}\b"),
)


def git(*arguments: str) -> bytes:
    return subprocess.run(["git", *arguments], check=True, capture_output=True).stdout


def audit(require_exact=True):
    allowed = set(ALLOWLIST.read_text(encoding="utf-8").splitlines())
    indexed = {name.decode() for name in git("ls-files", "-z").split(b"\0") if name}
    historical = set(git("log", "--all", "--format=", "--name-only").decode().splitlines()) - {""}
    unexpected = (indexed | historical) - allowed
    if unexpected:
        raise ValueError(f"Paths missing from release allowlist: {sorted(unexpected)}")
    if require_exact and allowed - indexed:
        raise ValueError(f"Approved paths absent from index: {sorted(allowed - indexed)}")
    blobs = {}
    for entry in git("ls-files", "--stage", "-z").split(b"\0"):
        if entry:
            metadata, name = entry.split(b"\t", 1)
            mode, digest, stage = metadata.split()
            if mode not in {b"100644", b"100755"} or stage != b"0":
                raise ValueError(f"Unexpected mode or merge stage in indexed path: {name.decode()}")
            blobs[digest] = name
    for commit in git("rev-list", "--all").decode().splitlines():
        for entry in git("ls-tree", "-rz", commit).split(b"\0"):
            if entry:
                metadata, name = entry.split(b"\t", 1)
                mode, object_type, digest = metadata.split()
                if mode not in {b"100644", b"100755"} or object_type != b"blob":
                    raise ValueError(f"Unexpected mode in historical path: {name.decode()}")
                blobs[digest] = name
    for digest, name in blobs.items():
        blob = git("cat-file", "blob", digest.decode())
        if any(pattern.search(blob) for pattern in SECRETS):
            raise ValueError(f"Suspected credential material in Git path: {name.decode()}")
    if git("ls-files", "--", ".project", "AGENTS.md", "CLAUDE.md", "data", "artifacts", "release"):
        raise ValueError("Local-only project files are tracked.")
    private_checks = {".project/STATE.json", "AGENTS.md", "CLAUDE.md", "data/raw/sample.csv",
                      "artifacts/registry/sample.json", "release/static/study.json"}
    correctly_ignored = set(git("check-ignore", "--", *sorted(private_checks)).decode().splitlines())
    if correctly_ignored != private_checks:
        raise ValueError("A required local-only path lacks an ignore rule.")
    print(f"Reviewed {len(indexed)} indexed files, {len(historical)} historical paths and {len(blobs)} blobs.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-subset", action="store_true")
    args = parser.parse_args()
    audit(not args.allow_subset)


if __name__ == "__main__":
    main()
