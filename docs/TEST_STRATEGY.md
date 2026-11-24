# Release test strategy

The baseline consists of the 30 Python instances, two Vitest instances and five Edge workflows at `e81e2c6`. Preserve these regressions. Expanded cases are organized by the behavior they can independently falsify.

| Risk | Verification |
| --- | --- |
| Incorrect cohort, look-ahead or split leakage | Source and protocol hashes, point-in-time filtering, evaluator-only latent outcomes, correction maturity and deliberate leakage fault. |
| Incorrect policy probability or estimate | Exhaustive small-frame enumeration, selection budget and support checks, fixed-seed tests and independent finite-population calculations. |
| Incorrect cents or constrained plan | Independent integer/Decimal calculations, edge scenarios and exhaustive tiny optimization oracle. |
| Duplicate or inconsistent review state | Concurrent retry, conflicts, rejected transitions, transactional interruption, reopen, tamper and retained anchor. |
| Ungoverned scoring changes | Registry validation, corrupt artifacts, shadow independence, delayed feedback, stale approvals, promotion gates and rollback recovery. |
| Unsafe or unsupported analyst claim | Versioned independently specified scenario expectations for result, status, scope, tool and evidence provenance. |
| UI failure or misleading mode | Static and local workflows, keyboard and narrow layouts, screenshot review, request and console checks, accessibility checks. |
| Publication or supply-chain leak | Explicit tracked/export allowlists, dependency and license evidence, secret patterns, independent static builds, and local smoke checks. |

Python statement and branch measurement includes all owned modules under `src/payment_integrity`, including CLI entry logic and real-data paths that fixture tests may leave uncovered. It excludes test files, the standard library, and installed dependencies. Frontend decision coverage includes the owned calculation, data adapter and browser review state modules. Browser route interaction is reported separately.
