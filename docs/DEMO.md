# Three-minute demo

**0:00–0:35.** Open the static Overview. Explain the audit-budget problem and show 199,052 public Part B/DME claim groups across eight years. Describe the endpoint as any disagreement among the published rows of a claim group.

**0:35–1:15.** Open Risk models. Compare calibrated lookup and XGBoost on the 2025 holdout. Point out the challenger AP delta and its practical threshold. The lookup remains the active local research scorecard.

**1:15–2:00.** Set Policy replay to 2025, 5% capacity and unweighted. Show the drop in cohort estimation RMSE from 16.87 to 3.89 percentage points with 10% exploration and the retained 95.9% of greedy yield. Compare it with the lower-RMSE, lower-yield uniform design.

**2:00–2:35.** Open Financial analysis and move the fictional cost per review. Explain that the comparison changes scenario-weighted findings and workload while observed disagreement counts remain grounded in CERT.

**2:35–3:00.** In local mode score a fictional claim, show model version and fallback explanation, and start the one-seed replay. Close on the protocol commit and result digests.

## Portfolio statements

- Built a local research platform with 199,052 public CMS CERT claim groups and compared calibrated models against a hierarchical baseline on two temporal holdouts.
- Implemented a 200-seed delayed-label replay. At 5% review capacity, 10% exploration retained 95.9% of greedy yield and reduced cohort-rate estimation RMSE from 16.87 to 3.89 percentage points in the 2025 public cohort.
- Exposed a versioned research scorecard and audit planning through FastAPI and built a static analyst workspace backed by audited aggregate results.
