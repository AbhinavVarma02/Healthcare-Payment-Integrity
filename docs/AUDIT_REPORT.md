# Healthcare Payment Integrity repository audit

November 24, 2026 · Local scientific, statistical, architectural, security and engineering review

## Release decision

**Ready for local research use and for review of the aggregate-only static release.** The frozen research results reproduced. The API and active lookup remain research-only. Operational payer use, national inference, actual financial recovery and prospective performance remain unvalidated. External deployment and publication were unevaluated on a live target and remain unauthorized. The audit incurred $0 additional project expenditure using local compute, official source pages and public dependency advisory queries.

The work started from `b9ec6cc` and used the original `cert-v1` freeze at `aab39fdc790597c2c476e0f4d79aaf8543e74b09`. The original protocol files, H1/H2/H3 result files and tracked public aggregate retained their SHA-256 values. Reproductions and post-freeze analyses used separate ignored directories. A second implementation independently regrouped the released rows and recomputed design estimates from saved selections. This was an independent-style repository review in the same workspace, with no external validation or independent data collection. [Frozen protocol](research_protocol.md) · [Reproduction](REPRODUCIBILITY.md)

## Data and temporal validity

The audit checked all eight pinned CSV hashes, reconstructed the exact entry order and feature values for 199,052 eligible Part B/DME groups, and reconciled the recognized outcomes. No eligible groups had an unknown decision. Agreement and disagreement coexist on individual groups, so row-level agreement is insufficient to classify a group. The endpoint is at least one disagreement among the published rows. Published rows retain legitimate repeats and omit procedure content from all modeling and public outputs. The labels do not capture suppressed lines, complete submitted claims, adjudicated recoveries or provider intent. CMS uses a separate stratified design and expenditure weights for national improper payment estimation. [CMS CERT methodology](https://data.cms.gov/sites/default/files/2026-01/CERT%20Methodology.pdf) · [CMS 2025 Supplemental Report, Appendix N](https://www.cms.gov/files/document/2025-medicare-fee-service-supplemental-improper-payment-data-report.pdf)

| Reporting year | Source rows | Eligible claim groups | Groups with a disagreement | Mixed Agree/Disagree |
| --- | ---: | ---: | ---: | ---: |
| 2018 | 194,311 | 27,964 | 9,446 | 1,836 |
| 2019 | 191,140 | 27,947 | 7,490 | 1,686 |
| 2020 | 191,701 | 27,796 | 6,969 | 1,561 |
| 2021 | 164,962 | 23,454 | 5,638 | 1,125 |
| 2022 | 158,250 | 23,468 | 5,909 | 1,444 |
| 2023 | 163,472 | 20,247 | 4,744 | 1,069 |
| 2024 | 185,349 | 27,996 | 6,378 | 1,570 |
| 2025 | 163,940 | 20,180 | 4,015 | 998 |

H1 used 107,161 training, 23,468 calibration and 20,247 development groups. The challenger and lookup were selected using development results. The curated holdout partitions hold feature files without outcome tables. The holdout evaluator checks the committed data digest and source metadata, logs exposure, and now verifies the entire projected feature frame against the pinned raw CSV before returning labels. The freeze preceded the retained initial evaluator access records. Local Git and exposure logs supply corroboration within one workspace. They cannot establish independent preregistration or exclude unlogged prior access. Known aggregate context was documented before evaluation.

H3 uses submission window ends as simulated decisions and exact catalog vintage dates as availability bounds. The warm-start vintages were available before the first decision. The 2022 and 2023 waves learned from no previous replay outcomes, the 2024 wave learned from selected 2022 outcomes, and 2025 used selected 2022 and 2023 outcomes. The audited policy interface receives only matured batches. All waves still use retrospectively assembled released features. The public extract lacks the prospective claim stream and actual review timing, which limits deployment claims for H1–H3. [Data feasibility](DATA_FEASIBILITY.md) · [Data card](DATA_CARD.md)

## Frozen results and inference

| Hypothesis | Primary 2025 audit result |
| --- | --- |
| H1 · Boosted trees vs shrunken lookup | Practical improvement unsupported. AP difference −0.00497, paired 97.5% interval [−0.00930, +0.00005]. Precision difference +0.10 percentage points, interval [−1.69, +2.28]. Precision was 366/1,009 versus 365/1,009 and Brier was 0.16099 versus 0.16043. |
| H2 · Value versus risk at common capacity | Inconclusive. Fictional weighted findings changed by +1.72%, paired 97.5% interval [−2.60%, +7.82%]. Nonfindings per finding increased by 0.389, interval [0.178, 0.597]. The value policy found 320 and the risk policy 365 in 1,009 reviews. |
| H3 · Exploration, estimation and learning | Mixed. The 10% hybrid with HT improved over greedy's selected-only estimate by 12.98 percentage points of RMSE and retained 95.88% of yield. Uniform had lower RMSE than the frozen score-stratified allocation. Full IPW increased Brier by 0.003898, paired 95% Monte Carlo interval [+0.003529, +0.004268]. |

The H1 and H2 intervals are refit-free, paired claim bootstrap intervals using 400 draws and frozen 97.5% marginal confidence. Their outer tails have limited simulation resolution. Re-ranking duplicate bootstrap draws retains the original stable key order. Cluster identifiers and original CERT weights are absent. These intervals omit cluster and national design uncertainty, training variability and unobserved cohort shifts. In 2024, H1 challenger AP changed by −0.00695 and H2's weighted gain was +0.12%, with interval [−2.31%, +3.12%]. [Full frozen results](REPORT.md) · [Evidence ledger](EVIDENCE.md)

### H3 design and fairness of the comparisons

The audit verified 51,200 policy, wave and seed records using the 200 original archives. It checked each archive digest, exact review budget, uniqueness and range of selections, frozen stratum sizes, findings, Horvitz–Thompson (HT) estimates, finite-population variance, interval and effective sample size (ESS). It also confirmed identical selected training records for each design's weighting rules in 2022 and 2023, the only replay waves mature for 2025. Two fresh 200-seed reruns reproduced all 400 per-seed JSON and NPZ files byte for byte. H3's aggregate metrics were identical after excluding elapsed time.

| Policy at 5% capacity, 2025 | Design facts | Mean review yield | Rate RMSE | 95% Wald coverage |
| --- | --- | ---: | ---: | ---: |
| Greedy | 1,009 certainty selections. Remaining inclusion probabilities are zero | 36.77% | 16.87 pp, selected-only | Unavailable |
| 10% hybrid | 908 certainty selections and SRS of 101 from 19,272. Tail inclusion probability 0.005241 | 35.25% | 3.89 pp, HT | 93.5% |
| Uniform | SRS of 1,009 from 20,180. Inclusion probability 0.05 | 20.00% | 1.23 pp, HT | 95.0% |
| Score-stratified | SRS of 505 from the top 4,036 and 504 from the remaining 16,144 | 22.06% | 1.39 pp, HT | 93.5% |

The hybrid's headline combines a change in selection policy and a change from a selected-only rate to an estimator for the full released cohort. Greedy's selected-only rate answers a reviewed-case question. Greedy has no design-identifiable full-cohort rate at partial capacity. A matched-budget precision comparison among designs with positive inclusion probabilities favors uniform over this hybrid. The hybrid buys more findings at the cost of wider uncertainty. Its mean estimation ESS was 110.7. Score stratification improved yield over uniform with this allocation and missed its predeclared RMSE gate.

Within each random stratum the code uses marginal inclusion probability `n_h / N_h`, and HT weights sampled outcomes by its reciprocal. The variance of the rate is `sum((N_h / N)^2 * (1 - n_h/N_h) * s_h^2 / n_h)`. Certainty strata contribute zero variance. A non-census stratum with one draw leaves the variance unavailable. The exact toy enumeration verifies expectation and finite-population variance. The simulated propensities address replay selection within the published frame. Dataset suppression, CMS sample selection, provider-level burden and demographic fairness remain outside identification by this design.

For learning, full IPW restores the scale of eligible claim counts in expectation under the simulated design. It can amplify noise and affect the smoothing and minimum-count behavior. Clipping at 20 trades bias for stability. The frozen replay learner updates shrinkage statistics independently per policy and evaluates Brier, ECE and AP on later waves. It does not fit a separate replay calibration map. H1's scorecard uses separate sigmoid calibration. The H3 learning result applies to the tested learner and weighting rules, with only two later waves receiving replay feedback. [Research foundation](RESEARCH_FOUNDATION.md)

### Post-freeze exploratory diagnostics

These analyses reuse the already exposed fixed cohorts and the original decisions. They carry no new confirmatory status. A paired bootstrap of 4,000 resamples of the 200 seeds gave a 95% Monte Carlo interval of **12.56–13.40 pp** for hybrid versus greedy RMSE improvement and **95.72–96.03%** for greedy yield retained. For uniform minus stratified RMSE the interval was **−0.333 to +0.010 pp**, with the point estimate favoring uniform. This measures precision of the simulation summaries for the fixed 2025 frame.

Equal-tailed hypergeometric inversion by stratum, with Bonferroni allocation for the two random strata, gave 94.0% empirical coverage for the 10% hybrid, 94.0% for uniform, and 100.0% for score-stratified across the 200 original draws. Mean widths were 15.16, 4.90 and 7.88 pp respectively, compared with frozen Wald widths of 14.43, 4.81 and 5.51 pp. For 5% exploration, inverted intervals covered in 99.0% and averaged 21.71 pp in width. Discrete intervals can be conservative, and the coverage estimates have Monte Carlo error. Rare-event or tiny-stratum Wald intervals can collapse or be unavailable. The original confirmatory rule continues to use its specified Wald intervals. The aggregate-only diagnostics are reproducible with `python scripts/audit_research.py --freeze $freeze`. The audit also exhaustively tested the inversion on a small population.

## Financial interpretation and model governance

Scenario arithmetic uses integer cents and half-up rounding. The primary assumptions are 10,000 fictional cents for Part B exposure, 25,000 for DME, 35% financially relevant and 3,000 cents per review. The release contains 108 fixed-count configurations per holdout year, covering three exposure patterns, three relevant shares, three review costs and four capacities. A common per-review cost changes estimated net value while largely leaving fixed-count value ordering intact. Value-per-minute and positive-value time planning can respond differently. The constrained pilot used 100 exploration slots and a 757-per-part cap in 2025, filled 1,009 slots and found 351 disagreements. Both the expected and realized fictional net of that pilot were negative at primary assumptions. A separate bounded 500-candidate time example matched the solver objective in both holdouts with recorded zero gap. This sample supplies a solver check, with limited evidence for other instances.

The active lookup and XGBoost challenger passed scorecard loading and provenance checks. XGBoost missed the H1 practical gate. Model packages are versioned, checked before native model loading and excluded from static output. The two holdout monitoring waves distinguish covariate alerts from outcome-backed calibration and discrimination. No validated delayed performance estimator is used. Registry activation and rollback are local research controls. The cited frameworks are voluntary project references with their own institutional scope. [Model validation](MODEL_VALIDATION.md) · [Federal Reserve SR 26-2](https://www.federalreserve.gov/supervisionreg/srletters/sr2602.htm)

## Master requirement crosswalk

| Area | Acceptance evidence and remaining limits |
| --- | --- |
| Boot and recovery | Single Windows toolchain, on-disk specification digest, verified revision, Git state, writer lease, bounded checkpoints and updated evidence ledgers. Git and local hashes supply cooperative recovery evidence. |
| Spend, privacy and publication | Local-only artifacts, explicit Git and export path scopes, history/blob checks, trusted local model boundary, private-path exclusion, repeatable static archive. No paid service, deployment or external CI activation. |
| P0 source feasibility | Eight official vintages and data dictionaries, raw hashes, independently reconciled decision unit, observed outcome semantics, source lag, restricted-column exclusion, source rights register. Procedure or price joins, national weights and prospective dates are unavailable within the scoped sources. |
| P1 ingestion and storage | Bounded official HTTPS acquisition, manifests, quarantine, row and claim accounting, Parquet features and separate outcomes, deterministic sample rebuild, strict schema and no inferred Hive column, retained original hashes. No resumable partial HTTP transfer is needed for bounded files. Raw records remain local. |
| P2 development and freeze | Development-only EDA, downsampled plot outputs, formal split, feature allowlist, primary years, financial grid, seed and inference rules, Git freeze and evaluator access record. Historical aggregate context and already-exposed cohorts limit fresh confirmation. |
| P3 modeling | Global, historical, lookup, logistic, boosted tree and random reference, train-only feature transforms, separate calibration, unknown backoff, grouped splits, count ablation and maintenance comparison. AP, AUROC, Brier, calibration, budget metrics, supported strata and paired intervals produced. Public subgroups lack original cluster uncertainty. |
| P4 decision and finance | Fixed-capacity comparisons of random, risk, value and value/minute, scenario grid, exact units, constraint and solver checks, burden and observed weighted findings. Time and exposures are assumed. Aggregate differences do not establish provider impact or ROI. |
| P5 sampling and replay | Six strategies, four capacities, 200 seeds and four waves, finite-frame probabilities, conditional HT and variance, coverage, ESS, delayed isolated learning, weight clipping, inaccessible oracle, resumable evidence and full reproduction. Separate calibration sensitivity remains exploratory work if pursued. |
| P6 governance | Calibrated lookup champion for research, rejected operational promotion, challenger and monitoring evidence, development-set shift thresholds, artifact verification, synthetic adverse shifts and rollback. Two historical holdouts and no external model validation. |
| P7 serving | Health/readiness, version registry, single/batch score, count/time planning, bounded persistent replay with resume and cancel, validation lookup, structured logs, schema and transport bounds, benchmark. Service is loopback and assumes trusted workstation users and files. |
| P8 analyst workspace | Static and local modes, data coverage, PR/reliability, financial scenarios, replay, drift and provenance, loading/error states, bounded input controls, keyboard and mobile checks, real local replay and reload recovery. Live controls require the local API and the release bundles only aggregate views. |
| P9 QA and security | Locked dependency install, fixtures, scientific and operational regressions, lint/type checks, browser tests, advisory queries, hash comparison and repository/static scans. Linux workflow defined for manual use. Portability evidence is Windows. Advisory databases are a point-in-time control. |
| P10 delivery | Report, traceable ledger, methodology, sources, licensing, governance, threat model, startup and operation commands, demo and portfolio text, static headers and verified local routing. Cloudflare documentation supports static-only asset delivery. Live routing and billing depend on an authorized target. |

## Resolved implementation findings

- Bound vintage metadata and the holdout feature frame to the pinned source. Corrected DuckDB partition-column inference and reject unexpected snapshot schemas. H2 and governance now verify the H1 prediction file digest and result linkage before use.
- Separate unavailable labels from the policy interface. Enforce a writer lock per replay output and prevent a partial rerun from overwriting a larger replay. Incomplete studies receive an inconclusive status in the research CLI and a preview label in the local API.
- Verify the exact model bytes consumed by JSON and XGBoost loading. Reject invalid calibration and model parameters. Test lookup and boosted scorecard parity, corrupt artifacts and rollback.
- Enforce the local browser-origin policy on POST requests, apply a whole-body read deadline, preserve job interruption status, and refuse filesystem links in static export. Check indexed and historical Git blobs with secret patterns and verify all expected private paths are ignored. These controls operate within a trusted local filesystem.
- Add local exploration, time and financial planning controls and recent run history. Keep the preview ID across browser reloads, allow retry of failed status polling, and explain the scope of greedy and design-aware estimates in the analyst workspace.

## Final verification

| Check | Observed result |
| --- | --- |
| Independent `scripts/audit_research.py --freeze $freeze` | 8 source cohorts and 51,200 replay records reconciled. 2022–2023 selection evidence was identical across weight rules within each design and capacity. |
| `python -m payment_integrity.cohorts` to a fresh output root | All 8 manifests and 14 Parquet files reproduced byte for byte. Development EDA regenerated with the original digest. |
| `uv sync --offline --locked`, fixture smoke, `pytest -q`, Ruff and mypy | Clean Windows archive installed offline, synthetic smoke passed, 22 pytest tests passed, lint and type checks passed. The Starlette TestClient deprecation remains a tooling warning. |
| `npm ci --offline --ignore-scripts`, `npm run test`, `npm run build` | Clean Windows archive passed with 2 unit tests. All seven release file hashes matched the workspace build. The trained models and CMS records were absent from the archive. |
| `npm --prefix web run test:browser` | 3 Edge tests passed. Desktop and mobile static views, keyboard skip, missing asset handling, same-origin-only static requests, local inference, time planning, replay and history recovery were checked. |
| `npm audit` and `pip-audit` | No known findings in the queried locked npm dependencies and Windows Python runtime. |
| `python scripts/audit_release.py` and `python -m payment_integrity.publication check` | Git allowlist, contents and private exclusions passed. The static study digest matched the original reviewed aggregate. |
| `python scripts/benchmark.py --output …` | Intel Core i9-14900HX, 32 logical cores, 34.05 GB RAM, Windows 11 and Python 3.13.2. Cold readiness 2.25 s, single p50/p95 12.63/19.20 ms, batch p50/p95 50.14/73.09 ms with four clients of 32 claims, peak process tree RSS 199.77 MB. The measured run met all stated ceilings. |

Start the static export from the project root with `.venv/Scripts/python.exe scripts/serve_static.py`. For real-data reproduction and loopback API startup, use the documented commands. [Runbook](REPRODUCIBILITY.md) · [Performance targets](PERFORMANCE.md)

The historical notebook-free experiment and static aggregate validate the scoped research prototype. Remaining structural limits include original CMS weights and suppression, complete claim outcomes, row-level timestamps, provider and demographic identifiers, real costs or recoveries, a prospective holdout and independent operational validation. The public release excludes models and record-level data. [Limitations](LIMITATIONS.md) · [Threat model](THREAT_MODEL.md) · [Static release](DEPLOYMENT.md)
