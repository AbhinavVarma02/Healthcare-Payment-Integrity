# Data feasibility

The official CMS open data catalog provides annual CSV releases for reporting years 2018 through 2025. The 2026 report is available as an aggregate publication. The catalog checked November 24, 2026 still designates 2025 as the latest row-level release. Report publication dates and the catalog modification dates for the downloaded CSV vintages differ. Use the latter as conservative public availability proxies for this run. Each reporting year covers submissions from July 1 two years earlier through June 30 one year earlier.

| Reporting year | Submission start | Submission end | CSV metadata version | Source rows | Control-number groups |
| --- | --- | --- | --- | ---: | ---: |
| 2018 | 2016-07-01 | 2017-06-30 | 2021-05-20 | 194,311 | 49,943 |
| 2019 | 2017-07-01 | 2018-06-30 | 2021-05-20 | 191,140 | 49,943 |
| 2020 | 2018-07-01 | 2019-06-30 | 2021-05-20 | 191,701 | 49,796 |
| 2021 | 2019-07-01 | 2020-06-30 | 2022-01-13 | 164,962 | 41,962 |
| 2022 | 2020-07-01 | 2021-06-30 | 2023-03-06 | 158,250 | 41,996 |
| 2023 | 2021-07-01 | 2022-06-30 | 2024-01-04 | 163,472 | 37,506 |
| 2024 | 2022-07-01 | 2023-06-30 | 2025-10-28 | 185,349 | 50,002 |
| 2025 | 2023-07-01 | 2024-06-30 | 2026-02-03 | 163,940 | 37,581 |

All eight files have the same headers and dictionaries. Structural scans found no blank control numbers or mixed claim parts inside a year and control-number group. The analysis uses the Part B and DME MAC categories. Part A is outside scope. Several thousand development groups have both review decisions on different published rows. Preserve repeated rows because the release lacks a line identifier and repeated values can describe separate services. Claim grouping is by release reporting year and control number. Cross-release identity is unverified.

The target is any disagreement on the published rows of a claim group with recognized decisions on every observed row. Any unrecognized or empty observed decision excludes the group from labeled evaluation. The public extract can suppress entire rows or claims. Coverage and the target therefore refer to the released sample. A truly complete claim outcome and the original number of submitted lines are unavailable. Observed counts, category and provider-type composition can support retrospective prediction from the extract, with a limitation on prospective transport. Exclude procedure contents, DRG, bill type, error codes, identifiers and dates from the feature matrix.

The public schema contains no source review timestamp, submission day, payment amounts, submitted units, modifiers, geography, named provider identifiers or CERT weights. National improper-payment amounts and rates use CMS sampling and expenditure weights. This study targets the finite eligible public cohort. Disagreement may include documentation failures, underlying coding errors, payment direction and different appeal states.

## Feasibility decision

Proceed on the public CMS governmental fields and claim groups. Use explicit, fictional values for financial sensitivity because the candidate aggregate schedules require procedure and context matching the permitted feature contract cannot support. Exclude any year with schema incompatibility or irreconcilable keys pending verification. If a future release changes outcome semantics, preserve the existing cohort and version the study before incorporating it.

See the [references](REFERENCES.md), [rights register](LICENSING.md) and [source manifest](../configs/cms_sources.json).
