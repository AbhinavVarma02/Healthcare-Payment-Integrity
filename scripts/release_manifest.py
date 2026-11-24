"""Attest an exact clean local release and its independent static builds."""

import argparse
import platform
import subprocess
from pathlib import Path
from xml.etree import ElementTree

from payment_integrity.publication import audit_paths
from payment_integrity.storage import read_json, sha256, write_json

EVIDENCE = (
    "artifacts/final-frozen-research-audit.json",
    "artifacts/adaptive-final-boundary/h4.json",
    "artifacts/final-h4-stress.json",
    "artifacts/lifecycle-release/h5.json",
    "artifacts/assistant/release-v1.json",
    "artifacts/assistant/release-model/h6.json",
    "artifacts/assistant/release-model/profile.json",
    "artifacts/final-benchmark.json",
    "artifacts/workflow-release/scenario.json",
    "artifacts/final-mutations.json",
    "artifacts/final-browser.json",
    "artifacts/final-npm-audit.json",
    "artifacts/final-python-audit.json",
)


def command(*args):
    return subprocess.check_output(args, text=True).strip()


def build_proof(folder, tree, expected):
    path = folder / "artifacts/clean-build.json"
    proof = read_json(path)
    if proof["tree"] != tree or proof["files"] != expected:
        raise ValueError("Clean archive differs from the current release tree or export.")
    tests = folder / "artifacts/pytest.xml"
    suite = ElementTree.parse(tests).getroot().find("testsuite")
    if suite is None or not int(suite.attrib["tests"]) or any(int(suite.attrib[key]) for key in ("errors", "failures")):
        raise ValueError("Clean archive test evidence did not pass.")
    return {"files_sha256": sha256(path), "python_test_results_sha256": sha256(tests),
            "python_coverage_sha256": sha256(folder / "artifacts/python-coverage.json"),
            "frontend_coverage_sha256": sha256(folder / "web/test-results/coverage/coverage-summary.json")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("clean_first", type=Path)
    parser.add_argument("clean_second", type=Path)
    args = parser.parse_args()
    if args.clean_first.resolve() == args.clean_second.resolve():
        parser.error("Two independent source archives are required.")
    if command("git", "status", "--porcelain"):
        parser.error("Release manifest requires a clean tracked tree.")

    tree = command("git", "rev-parse", "HEAD^{tree}")
    release = Path("release/static")
    files = audit_paths(release)
    builds = [build_proof(folder, tree, files) for folder in (args.clean_first, args.clean_second)]
    browser = read_json(Path("artifacts/final-browser.json"))["stats"]
    if browser["unexpected"] or browser["flaky"] or browser["skipped"] or not browser["expected"]:
        raise ValueError("Browser evidence contains unfinished, failing or flaky cases.")
    analyst = read_json(Path("artifacts/assistant/release-v1.json"))
    if analyst["critical_failures"] or analyst["passed"] != len(analyst["scenarios"]):
        raise ValueError("Deterministic analyst evidence did not pass.")
    version = read_json(Path("web/package.json"))["version"]
    result = {
        "schema_version": 2, "release": f"v{version}",
        "commit": command("git", "rev-parse", "HEAD"), "tree": tree,
        "branch": command("git", "branch", "--show-current"),
        "release_scope": "local research candidate and reviewed static export",
        "deployment": "undeployed", "static_root": release.as_posix(),
        "toolchain": {"python": platform.python_version(), "node": command("node", "--version"),
                      "uv": command("uv", "--version"), "npm": command("npm.cmd", "--version")},
        "files": files, "clean_builds": builds,
        "tracked_allowlist_sha256": sha256(Path("configs/release_allowlist.txt")),
        "research_extensions_sha256": sha256(Path("web/src/research-evidence.json")),
        "evidence": {name: sha256(Path(name)) for name in EVIDENCE},
    }
    output = Path(f"release/v{version}-manifest.json")
    write_json(output, result)
    print(f"{output} {sha256(output)}")


if __name__ == "__main__":
    main()
