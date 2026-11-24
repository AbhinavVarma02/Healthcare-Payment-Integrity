# v1.0.0 requirements traceability

This register reconciles the original research deliverables, internal closed-loop milestone and final release brief against the prior [research audit](AUDIT_REPORT.md) and [release audit](RELEASE_AUDIT.md). P0 gates protect scientific or operational validity. P1 gates support a usable, independently verifiable local release. Status applies to the evidence cited in each row.

| ID | Priority | Requirement | Status | Implementation and evidence |
| --- | --- | --- | --- | --- |
| FR-01 | P0 | Preserve audited H1–H3 protocol, cohorts, results, seed checkpoints and negative outcomes | Verified | Frozen protocol at `aab39fd`, baseline `d5bfc82`, aggregate digest in [evidence ledger](EVIDENCE.md). Rechecked 60 baseline fingerprints, 800 seed comparisons and the seven retained static files. |
| FR-02 | P0 | Validate source vintage, grouping, schema and restricted-data isolation | Verified | `cohorts.py`, `protocol.py`, `audit_research.py`, `test_cohorts.py`, `test_protocol.py`. Independent grouping and 51,200 seed records in [research audit](AUDIT_REPORT.md). |
| FR-03 | P0 | Ground champion, finance and selective-label findings with valid estimators | Verified | `study.py`, `finance.py`, `replay.py`, `sampling.py`. Paired intervals, estimator definitions and limitations in [research report](REPORT.md). |
| FR-04 | P0 | H4 equal-budget adaptive, uniform, fixed and greedy replay | Verified | `adaptive.py`, `stress_adaptive.py`, `test_adaptive.py`. Matched 200-seed historical rerun and 5,600 synthetic stress results in the [experiment report](EXPERIMENT_REPORT.md). |
| FR-05 | P0 | Event-driven review, delayed labels, correction, retries and receipts | Verified in synthetic workflow | `workflow.py`, `receipts.py`, `test_workflow.py`, local Edge workflow in `operations.spec.ts`. |
| FR-06 | P0 | H5 actual shadow, candidate integrity, approval, rejection and rollback | Verified in synthetic workflow | `lifecycle.py`, `lifecycle_study.py`, `test_lifecycle.py`, [model lifecycle](MODEL_LIFECYCLE.md) and [experiment report](EXPERIMENT_REPORT.md). |
| FR-07 | P0 | Local observability, controlled faults and persisted recovery | Verified on bounded local workload | `telemetry.py`, `simulate_workflow.py`, `benchmark.py`. Measured API scoring and restored 430-event simulation in [performance report](PERFORMANCE.md). |
| FR-08 | P0 | H6 deterministic tools verified against approved artifacts and independent answers | Verified | `assistant.py`, `evaluate_assistant.py`, `evaluate_release_analyst.py`. Registered 10/10 and expanded 50/50 in [test evidence](TEST_EVIDENCE.md). |
| FR-09 | P1 | Optional local generative model | Deferred | Installed Qwen2.5 1.5B timed out on all seven eligible requests in both evaluations. Deterministic operation remains available. |
| FR-10 | P1 | Responsive existing routes, guided review workflow, version/source metadata and accessible charts | Verified | React static and loopback modes in `web/src`, Edge and Firefox workflows and the [visual review](UI_DESIGN.md). |
| FR-11 | P0 | Risk-based regression suite, coverage and deliberate fault checks | Verified within documented scope | 137 Python and 39 frontend instances, target gaps and seven deliberately detected faults in [test evidence](TEST_EVIDENCE.md). |
| FR-12 | P0 | Clean independent exports, public allowlist, offline-capable static runtime and release manifest | Verified | `publication.py`, `audit_release.py`, `verify_clean_release.ps1` and `release_manifest.py`. The local release manifest records exact tree, clean build and export fingerprints. |
| FR-13 | P0 | Exact clean release commit and safe local integration | Local release | `codex/closed-loop` began at `e81e2c6` and `main` at `d5bfc82`. The manifest binds verified evidence to the integrated commit. |
| FR-14 | P1 | Prospective evaluation on a new untouched eligible cohort | Externally blocked | Cohorts already inspected are exploratory for new hypotheses. [Limitations](LIMITATIONS.md). |
| FR-15 | P1 | Static-only hosting | Externally blocked | External target authorization is pending. [Deployment](DEPLOYMENT.md). |
