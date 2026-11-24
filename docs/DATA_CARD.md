# Data card

**Cohort.** CMS CERT public use extracts, 2018–2025 reporting years. CMS draws a stratified random sample and reviews claims against Medicare coverage, coding and payment rules. The extract suppresses rare services and may also suppress services associated with a single provider or supplier. The study covers Part B and DME MAC claims.

**Unit.** A claim group is all public rows for the same control number inside one release. Some claims contain different decisions on different rows. The binary label is disagreement on at least one available row, provided all its observed decisions are legible. The category, provider-type composition and visible row count are public-extract features. Counts and composition inherit the upstream suppression filter.

**Intended use.** Local human-supervised research on review prioritization, finite-cohort estimation and modeled review workload. There are no national estimates, automatic determinations, provider profiling, reimbursement decisions or patient risk scores.

**Traceability.** The source manifest pins download and dictionary URLs, submission windows and catalog version dates. Downloads produce local checksums. Claim keys and model artifacts stay local. See [feasibility](DATA_FEASIBILITY.md) and [references](REFERENCES.md).
