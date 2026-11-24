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

Each module provides `--help`. Stop on a nonzero exit. If a CMS file is revised or a cached download fails verification, inspect the provenance. `--refresh` retrieves a fresh copy without changing pinned study digests. An updated source requires a new protocol decision. `cohorts --rebuild` recreates the partitions while keeping holdout outcomes sealed from the ingestion reader. On replay restart, use the same exact freeze and output directory. Completed seeds are reloaded only after verifying the selection archive digest. Use a new directory for partial previews.

Governance writes immutable registry versions. If you intentionally rerun the study and the resulting validation digest changes, build into an alternate `--registry` path for review before replacing the local model version from a stopped service. Inspect `/v1/models/active` and `/ready` after activation. To roll back, use Python with `from payment_integrity.registry import Registry` and call `Registry(Path("artifacts/registry")).rollback()`. A prior version must exist.

```powershell
.venv/Scripts/python.exe -m payment_integrity.publication aggregate
npm --prefix web run build
.venv/Scripts/python.exe -m payment_integrity.publication export
.venv/Scripts/python.exe scripts/serve_static.py
```

For browser verification, run the loopback API, Vite dev server and static server on ports 8000, 5173 and 4173, then use `npm --prefix web run test:browser`. The configuration uses installed Microsoft Edge. If your Windows sandbox blocks loopback socket creation, run those commands in an approved local shell. Screenshot outputs live in ignored browser test results.
