# Development cohorts

Reproduce with `python -m payment_integrity.explore` after cohort snapshot creation. The output reports a source digest for each cohort, published row counts and claim groups separately, and development disagreements by part and visible row band.

| Reporting year | Part B claims | Part B disagreement | DME claims | DME disagreement |
| --- | ---: | ---: | ---: | ---: |
| 2018 | 17,036 | 31.34% | 10,928 | 37.58% |
| 2019 | 16,993 | 23.27% | 10,954 | 32.27% |
| 2020 | 16,891 | 19.89% | 10,905 | 33.10% |
| 2021 | 14,260 | 18.05% | 9,194 | 33.33% |
| 2022 | 14,071 | 22.43% | 9,397 | 29.30% |
| 2023 | 11,999 | 22.28% | 8,248 | 25.11% |

Between 2018 and 2023 the observed disagreement fraction declined overall and the gap between the two parts narrowed. RY2021 and RY2022 cover different portions of the pandemic period and show different Part B rates. Review scope, submission mix, public suppression and policy timing are plausible contributors. The descriptive data cannot identify their separate effects.

Development decision values were recognized for every eligible group. There were 1,069 to 1,836 partially disagreeing claim groups per cohort. Provider type was present across eligible rows, with 1 to 13 mixed-provider Part B groups per year. DME had 48 to 55 provider categories and Part B 82 to 91. The median visible line count ranged from one to two and the 99th percentile ranged from eight to thirteen. Review performance outside the common portion of these distributions warrants caution.

The 2024 and 2025 feature snapshots contain 27,996 and 20,180 groups respectively. No row-level holdout outcomes were accessed to produce this document or its source artifact. [Data feasibility](DATA_FEASIBILITY.md)
