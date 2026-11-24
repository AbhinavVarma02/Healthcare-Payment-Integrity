# Model validation and governance

The active local version is identified in the study aggregate. The registry holds two model families.

| Model | Provenance | Local decision |
| --- | --- | --- |
| Hierarchical beta-binomial lookup | Fit on 2018–2021, calibrated on 2022, selected on 2023. Part, provider and line-band hierarchies | Active for research |
| XGBoost depth 4 | Same splits and visible features, with train-only encoding | Research challenger. The practical H1 gates were not met |

The potentially high impact of operational reimbursement review justifies conservative research-only treatment. A human reviewer retains decision authority. A candidate merits further assessment only after demonstrating practical discrimination and yield improvement, acceptable Brier relative to lookup, stable features, fit/serve parity, and verified lifecycle controls. Neither model has operational approval.

## Monitoring and rollback

Use the 2022 calibration cohort as the reference and 2023 as a development comparison. Alert limits are 125% of the observed development distance, with explicit positive minimums. Measure score PSI, provider category Jensen–Shannon distance, unknown categories and missing categories. These shifts can be examined before labels. Report Brier, prevalence, discrimination and reliability when comparable decisions become available. Delayed-label performance estimation such as CBPE is outside the validated scope.

The lookup had no covariate alerts under these thresholds for 2024 or 2025. Its realized Brier scores were 0.17384 and 0.16043. Two holdout waves give limited evidence of drift detection performance. Synthetic adverse-shift tests verify alert logic and label masking.

Activation validates checksums, schema, model type and library versions before an atomic write. Rollback revalidates the previous artifacts before exchanging pointers. A corrupt or missing active model yields unavailable readiness. Cancel or finish worker jobs before moving a registry. See [operation and recovery](REPRODUCIBILITY.md).

| Reference | Practice and evidence | Scope |
| --- | --- | --- |
| NIST AI RMF 1.0 | Inventory, intended-use limits, shift measurement, error tests | Voluntary risk management reference |
| NAIC AI Model Bulletin | Record provenance, anticipated use, governance and human authority | Model insurance guidance reference. Application varies by jurisdiction |
| Interagency SR 26-2 | Risk-based inventory, outcomes analysis, challenger, validation and rollback | Banking supervision reference only |

Validation was completed by the developer. See [report](REPORT.md), [limitations](LIMITATIONS.md) and [primary sources](REFERENCES.md).
