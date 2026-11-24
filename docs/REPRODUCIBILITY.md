# Reproduction and recovery

Start in the repository root. Use native PowerShell, Python 3.13 and Node 24. The reference workstation had 32 logical and 24 physical CPU cores, 34.05 GB of RAM and 124.86 GB of free disk at initial inspection. The eight CSVs are approximately 120 MB. Allow 3 GB for the local virtual environment, caches, data and report artifacts. The reference replay took 213 seconds using one research worker. Dependency retrieval needs network access to PyPI, npm and the official CMS catalog endpoint for refreshes.

```powershell
$env:UV_CACHE_DIR = '.cache/uv'
uv sync --locked
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe scripts/fixture_smoke.py
New-Item -ItemType Directory -Force .cache | Out-Null
.venv/Scripts/python.exe -m pytest -q --basetemp .cache/pytest
.venv/Scripts/ruff.exe check src scripts tests
.venv/Scripts/mypy.exe --ignore-missing-imports --explicit-package-bases src/payment_integrity scripts
npm --prefix web ci --ignore-scripts
npm --prefix web run test
```

For line and branch evidence use the locked coverage tools.

```powershell
.venv/Scripts/python.exe -m coverage run --branch --source=payment_integrity -m pytest -q --basetemp .cache/pytest
.venv/Scripts/python.exe -m coverage json -o artifacts/python-coverage.json
npm --prefix web run test:coverage
```

The fixture smoke uses generated fictional rows and never opens CMS data. For the reference experiment use the full ID of the frozen commit. The commands preserve interrupted seed checkpoints. Run from a clean checkout or use fresh local output roots for a new evidence series.

```powershell
$freeze = git rev-parse aab39fd
.venv/Scripts/python.exe -m payment_integrity.download 2018 2019 2020 2021 2022 2023 2024 2025
.venv/Scripts/python.exe -m payment_integrity.cohorts 2018 2019 2020 2021 2022 2023 2024 2025
.venv/Scripts/python.exe -m payment_integrity.explore
.venv/Scripts/python.exe -m payment_integrity.study select --freeze $freeze
.venv/Scripts/python.exe -m payment_integrity.study evaluate --freeze $freeze
.venv/Scripts/python.exe -m payment_integrity.finance --freeze $freeze
.venv/Scripts/python.exe -m payment_integrity.replay --freeze $freeze
.venv/Scripts/python.exe -m payment_integrity.governance --freeze $freeze
.venv/Scripts/python.exe scripts/benchmark.py
```

Each module provides `--help`. Stop on a nonzero exit. If a CMS file is revised or a cached download fails verification, inspect the provenance. Use `download --refresh --root data/raw-review` to inspect a fresh copy while retaining the pinned source. An updated source requires a new protocol decision. `cohorts --rebuild` recreates the partitions while keeping holdout outcomes sealed from the ingestion reader. On replay restart, use the same exact freeze and output directory. Completed seeds are reloaded only after verifying the selection archive digest. Use a new directory for partial previews.

Preserve any existing confirmatory series by using an alternate directory for each rerun. Original H1 runs predating prediction-file digests are still retained as historical evidence. Run `study evaluate` under the current code in the alternate study directory before using it for H2 or governance.

```powershell
$study = 'artifacts/audit/verified-study'
$replay = 'artifacts/audit/verified-replay'
.venv/Scripts/python.exe -m payment_integrity.study select --freeze $freeze --output $study
.venv/Scripts/python.exe -m payment_integrity.study evaluate --freeze $freeze --output $study
.venv/Scripts/python.exe -m payment_integrity.finance --freeze $freeze --output $study
.venv/Scripts/python.exe -m payment_integrity.replay --freeze $freeze --output $replay
.venv/Scripts/python.exe -m payment_integrity.governance --freeze $freeze --study $study --replay $replay --registry artifacts/audit/verified-registry
.venv/Scripts/python.exe scripts/audit_research.py --freeze $freeze --replay $replay
```

The last command independently reconstructs cohort counts and replay estimates and emits aggregate exploratory interval diagnostics. Keep its output with research audit evidence. The static export uses the reviewed aggregate in `web/public/study.json`.

Governance writes immutable registry versions. If you intentionally rerun the study and the resulting validation digest changes, build into an alternate `--registry` path for review before replacing the local model version from a stopped service. Inspect `/v1/models/active` and `/ready` after activation. To roll back, use Python with `from payment_integrity.registry import Registry` and call `Registry(Path("artifacts/registry")).rollback()`. A prior version must exist.

```powershell
.venv/Scripts/python.exe -m payment_integrity.publication aggregate
npm --prefix web run build
.venv/Scripts/python.exe -m payment_integrity.publication export
.venv/Scripts/python.exe scripts/serve_static.py
```

For browser verification, run the loopback API, Vite dev server and static server on ports 8000, 5173 and 4173, then use `npm --prefix web run test:browser` with system Edge. For Firefox, set `PLAYWRIGHT_BROWSERS_PATH` to a project-local absolute cache directory and run `node web/node_modules/@playwright/test/cli.js install firefox`. From the web directory use `node node_modules/@playwright/test/cli.js test --project=firefox`. Screenshot outputs live in ignored browser test results. Windows sandbox restrictions may require approved local loopback execution.

An offline clean archive can run the fixture and build gates with a populated uv and npm cache. The tracked historical and extension aggregates are sufficient for the static build. Reproducing H4–H6 uses the audited data or local reference registry as described in the experiment report. The receipt verifier can check a SQLite backup against a separate anchor and the retained model versions. [Extended experiments](EXPERIMENT_REPORT.md) · [Operations runbook](OPERATIONS_RUNBOOK.md)

```powershell
scripts/verify_clean_release.ps1 -Label release-a -Ref HEAD
scripts/verify_clean_release.ps1 -Label release-b -Ref HEAD
```

Use new archive labels for repeat runs. Each archive installs the locked dependencies offline from the existing caches, runs the fixture/test/coverage gates and produces its own static fingerprint file. The two fingerprints must match the root export. This gate covers deterministic static packaging. Raw acquisition and research recomputation have separate evidence.
