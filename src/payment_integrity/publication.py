"""Build a reviewed aggregate-only study and an allowlisted local static export."""

import argparse
import re
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from .storage import read_json, sha256, write_json

ASSET = re.compile(r"assets/[A-Za-z0-9_-]+\.(?:js|css)")
PRIVATE_PATH = re.compile(r"(^|/)(\.project|\.agents|\.codex|\.venv|data|artifacts|logs|node_modules)(/|$)")
PRIVATE_TOKENS = (b"BEGIN PRIVATE KEY", b"BEGIN RSA PRIVATE KEY", b"claim_key",
                  b"holdout-exposure/", b"data/raw/", b"development-outcomes.parquet")
HEADERS = """/*
  X-Content-Type-Options: nosniff
  Referrer-Policy: no-referrer
  X-Frame-Options: DENY
  Content-Security-Policy: default-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'
"""
NOT_FOUND = """<!doctype html><html lang="en"><meta charset="utf-8">
<title>Page unavailable</title><h1>Page unavailable</h1><p><a href="/">Return to the study</a></p>
</html>
"""
WEB_LIBRARIES = ("react", "react-dom", "scheduler", "lucide-react")


def public_model(value):
    result = {key: value[key] for key in ("ap", "auroc", "brier", "ece", "calibration_intercept",
                                         "calibration_slope", "capacity")}
    result["calibration"] = [
        row for row in value.get("calibration", [])
        if row["claims"] >= 25 and min(row["observed"], 1 - row["observed"]) * row["claims"] >= 10
    ]
    total_positive = value.get("findings", 0)
    result["pr_curve"] = [
        [recall, precision] for recall, precision in value.get("pr_curve", [])
        if precision > 0 and recall * total_positive >= 10
        and recall * total_positive * ((1 - precision) / precision) >= 10
        and recall * total_positive / precision >= 25
    ]
    return result


def collect(workspace: Path):
    root = workspace / "artifacts"
    study = root / "study"
    h1, h2, h3 = (read_json(path) for path in
                  (study / "h1.json", study / "h2.json", root / "replay" / "h3.json"))
    if (not h1["complete"] or not h3["complete"] or h2["source_h1_sha256"] != sha256(study / "h1.json")
            or [row["year"] for row in h2["cohorts"]] != [row["year"] for row in h1["cohorts"]]
            or len({item["freeze_sha256"] for item in (h1, h2, h3)}) != 1):
        raise ValueError("Only completed, protocol-matched research can be exported.")
    eda = read_json(root / "eda.json")
    dev = read_json(study / "development.json")
    governance = read_json(study / "governance.json")
    validation = read_json(root / "registry" / governance["active"] / "validation.json")
    expected = {"h1": sha256(study / "h1.json"), "h2": sha256(study / "h2.json"),
                "h3": sha256(root / "replay" / "h3.json")}
    if validation["evidence"] != expected or dev["freeze_sha256"] != h1["freeze_sha256"]:
        raise ValueError("Governance or development evidence differs from the exported study.")
    rows = []
    for cohort in eda["cohorts"]:
        result = {
            "year": cohort["year"], "version": cohort["version"],
            "rows": cohort["counts"]["rows"], "claims": cohort["counts"]["feature_groups"],
            "in_scope_rows": cohort["counts"]["in_scope_rows"], "parts": {},
        }
        for part, part_row in cohort["parts"].items():
            result["parts"][part] = {key: part_row[key] for key in ("claims", "visible_lines")}
            missing = part_row["missing_provider"]
            result["parts"][part]["missing_provider"] = missing if missing == 0 or missing >= 10 else None
        if "disagreement_groups" in cohort["counts"]:
            result["disagreements"] = cohort["counts"]["disagreement_groups"]
        else:
            measured = next(x for x in h1["cohorts"] if x["year"] == cohort["year"])
            result["disagreements"] = measured["findings"]
        rows.append(result)
    models = [{
        "year": cohort["year"], "claims": cohort["claims"], "findings": cohort["findings"],
        "excluded_unknown": cohort["excluded_unknown"], "comparison": cohort["comparison"],
        "models": {name: public_model(value) for name, value in cohort["models"].items()},
    } for cohort in h1["cohorts"]]
    monitor = []
    for row in validation["monitoring"]:
        shift = row["before_label_release"]
        measured = row["after_label_release"]["measured_performance"]
        monitor.append({"year": row["year"], "drift": shift["drift"],
                        "covariate_alerts": shift["covariate_alerts"],
                        "brier": measured["brier"], "observed_rate": measured["outcome_rate"],
                        "labelled_claims": measured["labelled_claims"]})
    sources = {
        "Coverage": root / "eda.json", "Development": study / "development.json",
        "H1-holdout": study / "h1.json", "H2-holdout": study / "h2.json",
        "H3-sequential": root / "replay" / "h3.json",
        "Governance": root / "registry" / governance["active"] / "validation.json",
    }
    return {
        "schema": 1, "protocol": "cert-v1", "freeze_commit": h1["freeze_commit"],
        "freeze_sha256": h1["freeze_sha256"], "cohorts": rows, "models": models,
        "selection": h1["selection"], "split": dev["split"],
        "finance": h2["cohorts"], "finance_primary": h2["primary"],
        "replay": {"seeds": h3["seeds"], "timeline": [
            {k: v for k, v in row.items() if k != "features_sha256"} for row in h3["timeline"]
        ], "conclusions": h3["conclusions"], "policies": h3["policy_results"]},
        "validation": {"active": governance["active"], "status": validation["status"],
                       "promotion": validation["operations_promotion"], "cohorts": monitor,
                       "thresholds": validation["threshold_reference"]["thresholds"]},
        "ledger": [{"run": name, "sha256": sha256(path)} for name, path in sources.items()],
    }


def audit_paths(root: Path, *, require_notices=True):
    entries = list(root.rglob("*"))
    if (root.is_symlink() or root.is_junction()
            or any(path.is_symlink() or path.is_junction() for path in entries)):
        raise ValueError("Static export contains a filesystem link.")
    files = {file.relative_to(root).as_posix() for file in entries if file.is_file()}
    mandatory = {"index.html", "404.html", "study.json", "_headers"}
    notices = "THIRD_PARTY_NOTICES.txt"
    if require_notices:
        mandatory.add(notices)
    if not mandatory <= files or not any(path.endswith(".js") for path in files):
        raise ValueError("The expected static export is incomplete.")
    fingerprints = {}
    for name in sorted(files):
        path = root / name
        if ((name not in mandatory and name != notices and not ASSET.fullmatch(name)) or path.is_symlink()
                or PRIVATE_PATH.search(name)):
            raise ValueError(f"Path outside the static allowlist: {name}")
        value = path.read_bytes()
        if any(token in value for token in PRIVATE_TOKENS):
            raise ValueError(f"Restricted source token in {name}")
        if require_notices and b"127.0.0.1:8000" in value:
            raise ValueError(f"Local API reference present in the static export: {name}")
        fingerprints[name] = sha256(path)
    study = read_json(root / "study.json")
    if study["schema"] != 1 or study["replay"]["seeds"] != 200:
        raise ValueError("Unsupported or partial study export.")
    if any(row["claims"] < 25 for row in study["cohorts"]):
        raise ValueError("Cohort below the disclosure guard.")
    return fingerprints


def export(build: Path, root: Path):
    if sha256(build / "study.json") != sha256(build.parent / "public" / "study.json"):
        raise ValueError("The build aggregate differs from the reviewed source file.")
    if root.exists() and any(root.iterdir()):
        previous = audit_paths(root, require_notices=False)
    else:
        previous = {}
    root.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=root.parent) as folder:
        stage = Path(folder) / "static"
        stage.mkdir()
        (stage / "assets").mkdir()
        for name in ("index.html", "study.json"):
            shutil.copyfile(build / name, stage / name)
        for asset in (build / "assets").iterdir():
            name = f"assets/{asset.name}"
            if not asset.is_file() or asset.is_symlink() or not ASSET.fullmatch(name):
                raise ValueError(f"Unexpected build artifact: {name}")
            shutil.copyfile(asset, stage / name)
        (stage / "_headers").write_text(HEADERS, encoding="utf-8")
        (stage / "404.html").write_text(NOT_FOUND, encoding="utf-8")
        modules = build.parent / "node_modules"
        licenses = [
            f"{name}\n\n{(modules / name / 'LICENSE').read_text(encoding='utf-8').strip()}\n"
            for name in WEB_LIBRARIES
        ]
        (stage / "THIRD_PARTY_NOTICES.txt").write_text("\n".join(licenses), encoding="utf-8")
        hashes = audit_paths(stage)
        root.mkdir(exist_ok=True)
        # Replace the complete files atomically, placing entry points after assets.
        (root / "assets").mkdir(exist_ok=True)
        for name in sorted(hashes, key=lambda name: name in {"index.html", "404.html"}):
            (stage / name).replace(root / name)
        for name in previous.keys() - hashes.keys():
            (root / name).unlink()
    if audit_paths(root) != hashes:
        raise ValueError("Export changed during verification.")
    return hashes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=["aggregate", "check", "export"])
    args = parser.parse_args()
    if args.step == "aggregate":
        output = Path("web/public/study.json")
        write_json(output, collect(Path.cwd()))
        print(output, sha256(output))
    elif args.step == "check":
        source = Path("web/public/study.json")
        expected = collect(Path.cwd())
        if read_json(source) != expected:
            raise ValueError("The public study differs from the current reviewed result projection.")
        fingerprints = audit_paths(Path("release/static"))
        if fingerprints["study.json"] != sha256(source):
            raise ValueError("The static export differs from the tracked aggregate.")
        print("Reviewed aggregate and static export agree.", fingerprints["study.json"])
    else:
        audit = export(Path("web/dist"), Path("release/static"))
        write_json(Path("artifacts/release-audit.json"), audit)
        extensions = Path("web/src/research-evidence.json")
        if extensions.is_file():
            write_json(Path("release/v1.0.0-manifest.json"), {
                "schema_version": 1, "release": "v1.0.0", "files": audit,
                "frozen_study_sha256": audit["study.json"],
                "research_extensions_sha256": sha256(extensions),
            })
        print(audit)


if __name__ == "__main__":
    main()
