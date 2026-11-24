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
| Audit reconstruction and exploratory interval sensitivity | Original frozen source and seed selection evidence, 2025 primary budget | `policy_wave_seed_rows_verified` and `exploratory_2025_at_5_percent_capacity` from the audit CLI | `python scripts/audit_research.py --freeze $freeze` |

Confirmatory reference commit `aab39fd` and protocol SHA-256 `23758de970e3ac9b833420315fdfa95c3336d56981f9d478fa37c114036d9e52`. [Reproduction commands](REPRODUCIBILITY.md)

## Extended research and workflow evidence

The static lab uses the reviewed field projection in `web/src/research-evidence.json`. Each run identifies its protocol or config digest and source artifact. The full local results include seed checkpoints and denominators. [Experiment reproduction](EXPERIMENT_REPORT.md)

| Claim | Local run and SHA-256 |
| --- | --- |
| H4 completed 200 seeds and matched the fixed allocation under the chosen rule. | `adaptive-complete/h4.json` · `25bc3be3ba10a22b6686b8b486e0675191cda917e360eab61342969492124e66` |
| H5 completed 120 synthetic scenarios under delayed feedback. | `lifecycle-final/h5.json` · `c106886e74249fbf773b4d20347c963a698ab9a96784241770b4287d04c62beb` |
| H6 passed ten deterministic cases and the local model missed its gate. | `assistant/h6.json` · `517a5f41aef12fdc650e0b650ba45de0298b3f3505d0c4ce02a8aa9187482ea0` |
| The synthetic operations run recovered all 430 accepted events from backup. | `workflow-final/scenario.json` · `b77dcfca315e676c57c6324f444316139a8f8f331f939b5cee7c3ec63d0788e9` |
