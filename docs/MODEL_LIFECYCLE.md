# Model lifecycle

The frozen calibrated CERT lookup remains the research reference. Simulated candidate versions live in a separate local registry. A candidate records the feature schema, verified scorecard and validation digests, code, fit cutoff, feedback digest, weighting and reference model. Active and shadow pointers for the simulator use one atomically replaced state file guarded by a local writer lock.

## From feedback to validation

The operator explicitly requests recalibration or retraining. Training uses the latest revealed correction at the requested simulation cutoff. Earlier intake periods supply fitting rows, the penultimate period supplies calibration, and the last mature period supplies validation. Each split needs at least 30 findings and calibration and validation need both classes. The review history is an observed, selection-conditioned synthetic sample. The H5 research generator supplied separate uniform feedback. [Experiment report](EXPERIMENT_REPORT.md)

Validation compares Brier, paired Brier uncertainty, average precision, yield at the same review capacity, subgroup rate error and inference latency. Review minutes and calibration error are reported diagnostics. The candidate artifact is loaded through the existing typed JSON registry and checked against the manifest. The validation report exposes each gate independently.

## Shadow, approval and rollback

1. The operator places a version in shadow with its scorecard and report digests.
2. Intake records both scores while the current reference or synthetic active version controls allocation. Corrupt or unavailable shadow evidence yields a marked shadow failure and the active scoring path continues.
3. The supervisor sends the current lifecycle generation and matching digests to approve a candidate in shadow. Approval requires every gate and a verified workflow receipt chain. Stale or incomplete evidence rejects the request.
4. The supervisor can roll back to the previous verified version or the reference. If a previously activated artifact is unavailable, intake tries the previous verified synthetic version and the frozen reference.

An event receipt and the lifecycle history supply local traceability. Simulator scores support review demonstrations. A human chooses the simulated finding and retains decision authority. [Architecture](ARCHITECTURE.md) · [Threat model](THREAT_MODEL.md)
