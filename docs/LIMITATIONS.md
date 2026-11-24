# Limitations

| Limit | Interpretation and control |
| --- | --- |
| Public suppression and no line identifiers | Only visible published rows support grouping, complexity and targets. Repeated rows are retained. Results may shift for unsuppressed operational inputs. |
| Outcome semantics | Partial and total discrepancies, documentation failures and appeal states can differ. Claim-level disagreement does not measure intent, direction or payment loss. |
| No public weights in this extract | Design-aware rates pertain to the finite eligible frame. No estimate weights to Medicare nationally. |
| Missing financial context | No actual dollars, unit, modifier, geographic match or review time. All financial and time inputs are scenarios. |
| Timing approximation | Catalog modification dates give conservative availability proxies. Historical dates and current-vintage features can differ from what an analyst would have seen at the time. |
| Subgroups | Claim part and available coarse categories support some reliability checks. No named-provider or demographic fairness conclusions. |
| Inference | Paired bootstrap omits CMS clusters, HT intervals use a normal approximation, and simulation quantiles and standard errors are conditional on the four realized waves. |
| Policy model | Lookup strength comes from warm training. IPW may amplify variance and shift the fitted target. It does not ensure transport or causal identification. |
| Engineering scope | Research-only, trusted workstation, bounded local jobs, no production or external independent validation. |
| Source horizon | CMS had a 2026 supplemental aggregate report at source review. The row-level catalog ended at 2025. |
