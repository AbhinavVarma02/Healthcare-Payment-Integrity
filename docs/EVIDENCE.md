# Claims and evidence

The public aggregate in `web/public/study.json` holds the protocol commit, source-output hashes and numeric displays used by the workspace. The CLI reproduces source outputs in ignored local storage. The release generator projects aggregate columns and checks public curve cells against disclosure thresholds.

| Claim family | Run and data | Evidence fields | Reproduction |
| --- | --- | --- | --- |
| Source coverage and 199,052 in-scope groups | Coverage, CERT 2018–2025, source digests in protocol | `artifacts/eda.json` and `cohorts[].claims` in the aggregate | `python -m payment_integrity.explore` |
| H1 intervals and performance | `H1-holdout`, CERT 2024–2025, lookup and xgb-4 | `artifacts/study/h1.json`, `models[].comparison`, scorecards and split in development manifest | `python -m payment_integrity.study select --freeze $freeze`, then `evaluate` |
| H2 weighted findings, capacity and burden | `H2-holdout`, same frozen claims and scorecard | `artifacts/study/h2.json`, `finance[].grid`, `finance[].primary` | `python -m payment_integrity.finance --freeze $freeze` |
| H3 yield, estimation, and Brier | `H3-sequential`, CERT 2022–2025, warm-start 2018–2020, 37301–37500 | `artifacts/replay/h3.json`, seed and selection hashes, `replay` in aggregate | `python -m payment_integrity.replay --freeze $freeze` |
| Model status and shift | Governance, activated lookup and measured holdouts | `artifacts/registry/<version>/validation.json`, `validation` in aggregate | `python -m payment_integrity.governance --freeze $freeze` |
| Engineering latency and throughput | Local run against real scorecard, 60 single and 40 batch requests | `artifacts/benchmark.json` | `python scripts/benchmark.py` |

Confirmatory reference commit `aab39fd` and protocol SHA-256 `23758de970e3ac9b833420315fdfa95c3336d56981f9d478fa37c114036d9e52`. [Reproduction commands](REPRODUCIBILITY.md)
