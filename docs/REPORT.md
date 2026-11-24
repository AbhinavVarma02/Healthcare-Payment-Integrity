# Claim review optimization under selective labels

## Abstract

We studied review yield, fictional value, and finite-cohort rate estimation using 199,052 published Part B and DME groups across CMS CERT reporting years 2018–2025. A temporal evaluation compared calibrated models to a hierarchical shrinkage baseline. A four-wave historical replay compared known-probability and deterministic strategies over 200 seeds. The boosted model missed predeclared practical improvement thresholds. The primary value ranking comparison was inconclusive. A hybrid exploration policy substantially reduced rate estimation error relative to greedy’s selected-only rate while retaining most of its yield. Uniform sampling had lower RMSE than the score-stratified alternative. These are historical results for the released CERT frame.

## Problem and methods

Risk-targeted reviews can find more cases at a fixed capacity, and their observed labels can distort estimates and later fitted models. The study follows the joint yield and estimation framing in Henderson et al. and treats regression under investigation selection as an empirical model-dependent question. [Research foundation](RESEARCH_FOUNDATION.md)

The endpoint is any disagreement on a group's published rows with recognized outcomes on all visible rows. The model uses claim part, provider category, and visible claim structure. CPT, procedure contents, actual payment and source review times are excluded. Training, calibration and selection used 107,161, 23,468 and 20,247 eligible claim groups respectively. We froze thresholds and data digests before holdout access. The 2025 national aggregates and approximate release sizes were already publicly known. [Protocol](research_protocol.md)

## H1 · Discrimination and calibration

| Year | Eligible / disagreements | Lookup AP / Brier | XGBoost AP / Brier | Precision at 5%, lookup / XGBoost |
| --- | --- | --- | --- | --- |
| 2024 | 27,996 / 6,378 | 0.28898 / 0.17384 | 0.28203 / 0.17483 | 560/1,400 (40.00%) / 565/1,400 (40.36%) |
| 2025 | 20,180 / 4,015 | 0.25365 / 0.16043 | 0.24868 / 0.16099 | 365/1,009 (36.17%) / 366/1,009 (36.27%) |

For 2025 the challenger AP difference was −0.00497 (97.5% paired interval [−0.00930, 0.00005]) and the precision difference was +0.10 percentage points (interval [−1.69, +2.28]). Both thresholds had to be exceeded. The AP evidence rules out the specified +0.01 minimum at this interval level. The 2024 AP difference was −0.00695 (interval [−0.01072, −0.00337]) and the precision difference was +0.36 points (interval [−1.86, +2.72]). The development-selected lookup remains the local scorecard. The paired claim intervals do not incorporate the original CERT cluster design or sampling weights.

## H2 · Matched review capacity

At the 2025 primary scenario's 1,009 slots, risk ranking found 365 disagreements and value ranking found 320. Their hypothetical exposure-weighted findings were 7,865,000 and 8,000,000 scenario cents. The relative difference was +1.72% (97.5% paired interval [−2.60%, +7.82%]). The burden difference was +0.389 nonfindings per finding (interval [0.178, 0.597]). The primary comparison was inconclusive at the declared +5% gain and +0.5 burden margins. In 2024 weighted gain was 0.12% (interval [−2.31%, +3.12%]), below the practical gain criterion. The 2025 constrained pilot used 100 exploration slots and a 757-per-part cap, filling all 1,009 slots and finding 351 disagreements. A 500-candidate time-budget test found the same scenario objective for greedy and the verified HiGHS solution in each holdout year. This does not guarantee greedy optimality for other minutes constraints.

## H3 · Historical selective-label replay

The simulation used four replay waves with 23,468, 20,247, 27,996 and 20,180 eligible groups. Warm-start statistics used 2018–2020. A simulated batch decision was made at each submission window end. The exact public vintage date gated learning, so the 2024 policy could use selected 2022 outcomes and the 2025 policy could also use selected 2023 outcomes. Activities unfold at cohort granularity. Simulated reviews and dates do not reproduce CMS workflow.

2025, 1,009 reviews per seed, unweighted learners, 200 seeds:

| Design | Yield | Naive RMSE | Design-aware RMSE | Design-aware coverage | Brier |
| --- | ---: | ---: | ---: | ---: | ---: |
| Greedy | 36.77% | 16.87 pp | Unavailable | Unavailable | 0.16695 |
| 10% exploration | 35.25% | 15.36 pp | 3.89 pp | 93.5% | 0.16692 |
| Uniform | 20.00% | 1.23 pp | 1.23 pp | 95.0% | 0.16729 |
| Score-stratified | 22.06% | 2.48 pp | 1.39 pp | 93.5% | 0.16711 |

The 10% hybrid preserved 95.9% of greedy’s yield. Its design-aware estimate was 12.98 percentage points lower in RMSE than greedy’s selected-only rate. Greedy has zero inclusion probability outside the reviewed group. At the same capacity, uniform had lower design-aware RMSE than the hybrid or score stratification. Hybrid effective sample size averaged 110.7 despite 1,009 reviews. Full IPW under the 10% hybrid increased Brier by 0.00390 (95% paired Monte Carlo interval [0.00353, 0.00427]). Clipped weights achieved Brier 0.16672. Interval coverage describes repeated simulated selections on fixed released cohorts. This is mixed support for H3. [Reproduction and exploratory interval checks](AUDIT_REPORT.md)

## Interpretation

The lookup remained competitive with a more complex model on the restricted features. Exploration buys measurable cohort information at some yield cost, while the size and allocation of the random sample determine estimate variance. These historical findings cannot establish operational lift, current national payment risk, provider fairness, actual review times or financial recoveries. Individual reimbursement remains a human decision beyond this prototype's scope. [Limitations](LIMITATIONS.md) · [Evidence ledger](EVIDENCE.md)
