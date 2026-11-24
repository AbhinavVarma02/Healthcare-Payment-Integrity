# Healthcare Payment Integrity release audit

## v1.0.1 public release

The refined workspace uses the same frozen study aggregate and research protocol as v1.0.0. The publication gate verifies the source and Git history against the explicit allowlist and scans for credentials in history and static assets. Two locked source archives reproduce the export. The deployment serves only that seven-file export through Cloudflare Pages. [Release notes](RELEASE_NOTES.md) · [Static deployment](DEPLOYMENT.md)

## v1.0.0 local release

The release is a local research prototype with a static, aggregate-only preview. It preserves the audited `d5bfc82` baseline and extends the closed-loop candidate at `e81e2c6`. The frozen protocol is pinned at `aab39fdc790597c2c476e0f4d79aaf8543e74b09`. The release manifest records exact tree, commit and static output fingerprints. [Requirements traceability](RELEASE_TRACEABILITY.md)

| Gate | Evidence and result |
| --- | --- |
| Frozen research | The independent audit rebuilt cohort counts and verified 51,200 replay records. The result matches the prior independent audit byte for byte. The public aggregate totals 199,052 eligible groups and remains pinned to SHA-256 `eaf69560201573458508a359471a70d5720226e8e37d75d77b500d10db222b32`. Baseline inventory matched 60 files, 800 seed comparisons and the seven retained export files. [Research audit](AUDIT_REPORT.md) |
| H1–H3 findings | H1 failed the practical improvement criteria. H2 remains inconclusive with a paired interval spanning zero. H3 remains mixed, including the more precise uniform reference and the negative full inverse-weight learning result. [Research report](REPORT.md) |
| H4–H6 extensions | H4 reproduced all 200 historical seed row digests after correcting the inclusive five-point trigger. Separate synthetic stress covered four populations and 5,600 policy results. H5 repeated 120 synthetic scenarios and matched prior decisions and metrics after excluding timing. The 50-case supplemental deterministic analyst suite passed. Optional local model selection missed its gate again. [Experiment report](EXPERIMENT_REPORT.md) |
| Review and lifecycle | The persisted SQLite queue handles matched intake, idempotence, delayed and corrected findings and integrity-checked decisions. Tests cover rejected and accepted promotion, shadow isolation and rollback with synthetic evidence. An isolated 430-event run restored from backup and verified its model-linked anchor. [Operations and recovery](OPERATIONS_RUNBOOK.md) |
| Engineering tests | The expanded suites cover 137 Python and 39 frontend instances, with seven scratch-copy faults detected. The initial clean archive exposed a Windows replay-manifest read race. The release uses bounded shared read/write retries and verifies that persistent permission failures still propagate. Package-wide Python coverage remains below the stretch targets. [Test evidence](TEST_EVIDENCE.md) |
| Product and browser QA | Edge and Firefox each passed all 14 workflows across the static export and local FastAPI/Vite workspace. The three-size route matrix and desktop axe checks passed. Curated screenshots depict the static workflow. [Workspace design](UI_DESIGN.md) |
| Load and recovery | A bounded local run measured 1.713 s cold readiness, 10.51 ms single-request p95, 40.29 ms batch p95 and 4,871 batch cases/s. The synthetic store restored and verified in 0.050 s. [Performance results](PERFORMANCE.md) |
| Publication | The static export contains the CSP and 404 configuration, entry point, frozen aggregate, JS/CSS and bundled-library notices. The build verifies the aggregate hash, each referenced asset, reviewed headers and the absence of local API references. The staged source and history use an explicit allowlist. [Publication policy](PUBLICATION_POLICY.md) |
| Dependencies and cost | npm and the Windows Python locked runtime advisory queries found zero known advisories in the accessed databases. Coverage.py, V8 coverage and axe-core are development tools. Bundled licenses ship in `THIRD_PARTY_NOTICES.txt`. Additional expenditure was $0. [Licensing](LICENSING.md) |

## Reproduce the release

Build the static preview from the reviewed aggregates, then validate two independent source archives with the locked dependency caches. The clean build gate concerns static packaging and fixture verification. The separate frozen-audit and experiment runs assess scientific reproducibility. [Reproduction commands](REPRODUCIBILITY.md)

The local benchmark, fixture inputs and reviewed cohort analyses support engineering and retrospective research claims. Real payer deployment would require representative operational data, prospective and external validation, a privacy and security assessment, and operational testing. The static export has no metered service dependency. [Limitations](LIMITATIONS.md) · [Deployment](DEPLOYMENT.md)

## Local release disposition

The local v1.0.0 candidate met the release gates for the declared research and static demo scope. Two independent locked source archives produced identical SHA-256 fingerprints for all seven export files. The release manifest records the exact integrated source tree, clean-archive proofs, browser report and experimental evidence. The historical baseline export remains independently fingerprinted.
