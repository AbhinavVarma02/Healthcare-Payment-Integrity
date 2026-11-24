# Experiment report

## H4 · Adaptive review allocation

The retrospective grid covers 2022–2025, four capacities, seven policies and 200 paired seeds. All 22,400 policy, capacity, cohort and seed records completed. The rule reused the replay's initial learner with no updates. It chose 10% exploration in all four waves, so its selections and results matched fixed 10% and the matched schedule in every seed. The primary comparison did not support an adaptive improvement. This result is conditional on the four observed cohort mixtures and the prespecified five-percentage-point DME threshold.

In 2025 the 5% capacity was 1,009 of 20,180 eligible groups. RMSE estimates refer to the public cohort disagreement rate. MCSE uses variation across the simulation seeds.

| Policy | Mean findings | Review yield | Design-aware RMSE ± MCSE | Exact interval coverage | Mean review minutes |
| --- | ---: | ---: | ---: | ---: | ---: |
| Uniform | 200.80 | 19.90% | 1.21 ± 0.06 pp | 95.0% | 22,574 |
| Greedy | 341.00 | 33.80% | Unavailable | Unavailable | 27,330 |
| Fixed 5% | 336.41 | 33.34% | 4.94 ± 0.25 pp | 96.5% | 27,082 |
| Fixed 10%, adaptive and matched fixed | 334.24 | 33.13% | 3.44 ± 0.15 pp | 97.5% | 26,821 |
| Fixed 20% | 320.05 | 31.72% | 2.79 ± 0.14 pp | 94.0% | 26,748 |

Adaptive retained 98.02% of greedy yield and tied the matched schedule on estimation error. Uniform had the lowest RMSE among identifiable designs. Greedy's selected-only rate describes reviewed cases. It has zero tail inclusion probability. Hypergeometric intervals report finite-cohort uncertainty when all selected outcomes are available. Review minutes are scenario assumptions. H4's learner and interval method differ from H3's frozen study. [Frozen study](REPORT.md) · [Registered extension protocol](RESEARCH_PROTOCOL_EXTENSIONS.md)

## H5 · Simulated model updates

The declared grid ran 120 synthetic scenarios across 20 seeds, three drift settings and two feedback delays. Each scenario used eight waves of 500 cases with 100 feedback reviews per wave. The candidate arms made 60 simulated approvals and rejected or failed to fit on 1,020 other eligible attempts. Approval in the study used an in-memory candidate. Separate operational tests exercised serialization, artifact integrity, explicit approval and rollback.

For a prevalence increase and one-wave delay, gated recalibration reduced post-shift Brier loss by 0.01101 versus the static reference (paired MCSE 0.00175, 20 seeds). With two-wave delay the reduction was 0.00393 (MCSE 0.00120). One-wave recalibration reached the recovery criterion in 16 of 20 seeds. With two waves it reached the criterion in eight. Under stationarity the mean Brier changes were +0.00021 and +0.00007 for one- and two-wave delays. Fixed-capacity yield for the recalibration arm was unchanged because its fitted transform is monotonic. The calibrated historical lookup remains the research reference. The synthetic results characterize this generator and approval policy.

The isolated operational run trained on 120 mature synthetic findings, calibrated on 60 and validated on 30. The fitted challenger scored in shadow. Its promotion failed the uncertainty gate. A separate passing fixture demonstrated explicit activation and rollback back to the reference. [Model lifecycle](MODEL_LIFECYCLE.md)

## H6 · Analyst tools

All ten deterministic scenarios passed, including exact integer cents, receipt attribution, access rejection, unavailable evidence and abstention on unsupported actions. The installed Qwen2.5 1.5B model timed out on seven permitted attempts under the eight-second request budget. The six-match gate was unmet. Deterministic fallback supplied allowed answers and zero critical failures were observed across the tested scenarios. The release runs the deterministic interface. [Structured outputs](https://docs.ollama.com/capabilities/structured-outputs) · [Local model card](https://ollama.com/library/qwen2.5:1.5b)

## Reproduction

Run from the project root with the audited data and registry available. Use a new local output directory to preserve prior evidence.

```powershell
$env:PYTHONPATH = 'src'
$freeze = git rev-parse aab39fd
.venv/Scripts/python.exe -m payment_integrity.adaptive --freeze $freeze --seeds 3 --output artifacts/adaptive-preview
.venv/Scripts/python.exe -m payment_integrity.adaptive --freeze $freeze --output artifacts/adaptive-complete
.venv/Scripts/python.exe -m payment_integrity.lifecycle_study --development --output artifacts/lifecycle-dev
.venv/Scripts/python.exe -m payment_integrity.lifecycle_study --output artifacts/lifecycle-final
.venv/Scripts/python.exe scripts/evaluate_assistant.py --output artifacts/assistant/deterministic.json
.venv/Scripts/python.exe scripts/evaluate_assistant.py --model qwen2.5:1.5b --output artifacts/assistant/h6.json
.venv/Scripts/python.exe scripts/project_extensions.py --check
```

The optional Qwen evaluation uses an already installed local Ollama model at the fixed loopback endpoint. The H4 selection checkpoints use deterministic hashes. H5 uses wall-clock gates and records inference timing, so compare decisions and metrics separately from elapsed time. The H6 run and the aggregate include runtime-linked digests. Exact release reproduction uses the tracked aggregate projection. [Evidence ledger](EVIDENCE.md)
