# Release test evidence

## Automated results

| Suite | Passed instances | Distinct definitions | Parameterized instances | Failures / skipped |
| --- | ---: | ---: | ---: | ---: |
| Baseline Python regressions | 30 | 29 | 2 | 0 / 0 |
| Windows replay manifest read recovery | 3 | 1 | 3 | 0 / 0 |
| Release scientific, money and governance invariants | 64 | 20 | 53 | 0 / 0 |
| Source, API and publication boundaries | 30 | 12 | 23 | 0 / 0 |
| Lifecycle and receipt regressions | 10 | 5 | 6 | 0 / 0 |
| **All Python** | **137** | **67** | **87** | **0 / 0** |
| Frontend unit and adapter tests | 39 | 17 | 26 | 0 / 0 |

Python took 7.70 seconds in the workspace coverage run. One upstream Starlette TestClient deprecation warning remains. Vitest took 0.57 seconds in the workspace V8 coverage run. One source test may define several cases with different inputs and independently specified expectations. Test reruns, research seeds and input rows are excluded from the totals.

## Coverage

The fixture suite covers 1858/3127 (59.4%) statements and 345/804 (42.9%) branches across all owned Python product modules. The union with separate fixture smoke, deterministic analyst and H4 stress commands covers 1927/3127 (61.6%) statements and 371/804 (46.1%) branches. The product-wide engineering targets remain unmet.

| High-risk Python module | Statements | Branches |
| --- | ---: | ---: |
| `sampling.py` | 80/82 (97.6%) | 24/26 (92.3%) |
| `planning.py` | 69/85 (81.2%) | 20/32 (62.5%) |
| `workflow.py` | 281/290 (96.9%) | 65/74 (87.8%) |
| `receipts.py` | 51/81 (63.0%) | 12/22 (54.5%) |
| `lifecycle.py` | 111/140 (79.3%) | 14/22 (63.6%) |
| `protocol.py` | 39/66 (59.1%) | 9/26 (34.6%) |
| `replay.py` | 132/286 (46.2%) | 23/80 (28.8%) |
| `publication.py` | 62/159 (39.0%) | 23/68 (33.8%) |

The selected Python sampling module meets the 90% branch target. Workflow transitions approach that target. Remaining gaps include alternative ranking and solver failures, degraded registry handling, receipt/CLI paths, and data and replay orchestration branches. Frozen research and synthetic stress runs exercise parts of the latter paths separately. The test scope includes the full owned package and excludes tests and dependencies.

V8 covers 27 of 27 lines and 61 of 61 branches in the configured frontend calculation, data adapter and browser review state modules. React rendering and the local workflow components are assessed by browser workflows and excluded from this line/branch percentage. [Test strategy](TEST_STRATEGY.md)

## Analyst evaluation

The release corpus passed 50 of 50, with zero critical failures. It includes 14 fictional-cent calculations, six approved-evidence queries, three workflow-evidence queries, six unavailable-evidence cases, ten abstentions, nine invalid inputs and two role boundary cases. Expectations check exact numbers, correct tool and source, declared scope and data suppression. The registered deterministic evaluation separately passed 10 of 10. The optional local-model retry returned zero correct structured matches in seven eligible requests and fell back deterministically seven times. [Corpus](../tests/fixtures/analyst-release-v1.json) · [Experiment report](EXPERIMENT_REPORT.md)

## Deliberate fault checks

Seven controlled mutations were applied to independent temporary source copies. Each caused its selected regression to fail with pytest exit 1. The same checks passed in the unmodified full suite.

| Mutation | Detected by |
| --- | --- |
| Bypass both delayed-feedback gates | Poisoned future outcomes across six policies |
| Skip positivity enforcement | Greedy IPW rejection |
| Round ties to even cents | Exact monetary cases |
| Pass outcome columns into model features | Feature allowlist check |
| Treat truthy values as passed lifecycle gates | Strict promotion-gate checks |
| Ignore the saved allocation digest | Receipt tamper rejection |
| Accept altered bytes in the public study | Reviewed aggregate digest check |

The mutations demonstrate behavior on the chosen faults. Mutation evidence is scoped to these faults.

## Browser and publication

The browser gate exercises both loopback and static workflows, including chart and planner controls, deterministic analyst queries, delayed review, case action history, event-chain verification, responsive routes, keyboard focus and load recovery. Screenshots and desktop accessibility checks cover the route matrix. [Workspace design and screenshots](UI_DESIGN.md)

Fourteen workflows passed in Edge and fourteen in Firefox, with zero failures, skips or retries in the passing run. Browser execution took about 62 seconds across both engines. An earlier Firefox run reported cancelled study requests as failures. The network trace confirmed navigation cancellations, and the release skips the unneeded aggregate request on local-only routes. The browser gate still fails on other request errors.

Clean archive inputs and output hashes are recorded in the local release manifest. The prior seven-file static baseline remains available for comparison. The release audit describes the scope of package and publication checks. [Release audit](RELEASE_AUDIT.md)
