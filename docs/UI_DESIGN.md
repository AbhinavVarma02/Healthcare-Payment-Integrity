# Workspace design

The workspace is designed as a research instrument rather than a dashboard. A warm stone frame holds the navigation, and each page sits on a plain reading sheet. Page titles use a serif (Sitka on Windows, with Iowan Old Style, Charter and Georgia fallbacks) and everything else uses the system sans (Segoe UI Variable, San Francisco or the platform default) with tabular figures. The static release policy blocks font downloads, so every face is a local system font. One cobalt accent, matched to the pinned favicon, marks actions, links and the highlighted strategy. Sections are separated by a thin ink rule and a heading instead of boxed cards. Shaded panels are reserved for controls, receipts and the walkthrough footer.

Colors are tokens defined with `light-dark()`. Body and secondary text reach at least 5.4:1 contrast on every surface in both themes, control outlines at least 3:1 and every chart series at least 3.9:1. The theme follows the device setting until the user changes it in the masthead, where the choice is saved for that browser.

## Reading the numbers

- Each strategy keeps one color, marker and dash pattern on every chart: 10% exploration is cobalt circles, greedy graphite squares, uniform verdigris diamonds, 5% and 20% exploration cerulean and violet triangles, and score stratification ochre.
- Greedy is drawn with a hollow marker because its rate comes from a selected-only estimator, not a design-aware one.
- Percentage points carry a smaller `pp` unit so they never read as percentages.
- Fictional money is labeled as fictional, and planner amounts carry a dagger with a footnote.
- Interval charts show the frozen decision threshold beside each paired interval, so a rejected challenger or an inconclusive comparison is visible at a glance.

## Pages

| Page | Purpose |
| --- | --- |
| Overview | Problem, data scope, the yield and estimation trade-off at 5% capacity, the three frozen hypotheses with their status, a four-step walkthrough and the scope limits. |
| Data explorer | Release inventory by reporting year and claim part, the filtered selection and the observed disagreement rate. |
| Risk models | Precision and recall, reliability, the holdout scorecard and the challenger acceptance intervals against the frozen H1 thresholds. |
| Validation | Registry status, drift against thresholds for each holdout year and realized monitoring. |
| Audit planner | Capacity, exploration share and fictional assumptions, with the matched comparison recomputed for every choice. |
| Policy replay | Mean yield by capacity with seed percentiles, estimator comparison, strategy diagnostics, outcome availability delays and the H3 component criteria. |
| Financial scenarios | A whole-cent calculator for one fictional review and the H2 intervals against their criteria. |
| Review simulation | A browser-only fictional review from selection to a recorded correction, with its receipt. |
| Analyst | Deterministic evidence queries with source runs. The language model is disabled and labeled as such. |
| Research extensions | H4 adaptive allocation, H5 controlled learning and H6 analyst tools, all marked exploratory. |
| Methods | Design, pipeline, references and the SHA-256 ledger of source results. |
| Operations and Scoring and replay | Local mode only. The persisted review queue, receipts, lifecycle controls, live scoring, planning and bounded replay jobs. |

## Interaction and accessibility

Small option sets are native radio groups styled as segmented controls, so arrow keys move the selection. Longer lists stay native selects. Every chart has an accessible name, distinct markers and dash patterns, hover values and a "Chart values" table. The two headline charts also state their result in a sentence above the plot. Keyboard users can skip to content, close the narrow navigation with Escape and follow each review action with focus kept on the next step. Wide tables scroll inside named regions. Motion is limited to short color transitions and respects the reduced-motion setting.

Sections are plain `section` elements with headings rather than named landmark regions. Besides keeping landmark navigation short, this removed an intermittent Firefox page crash that occurred while axe evaluated the Overview with labelled section regions.

## Visual verification

Actual browser captures of the static workspace: [Light overview](images/overview.png) · [Dark overview](images/overview-dark.png) · [Mobile overview](images/overview-mobile.png) · [Audit planner](images/planner.png)

The route matrix opens 11 static and 13 local routes at 1440×900, 768×950 and 390×844 in both themes, in Edge and Firefox. It checks horizontal overflow, runtime and console errors and unexpected requests, saves a capture of every route, and runs the axe WCAG 2.0 and 2.1 A and AA rules on desktop. Workflow tests cover the guided planner, chart values, financial sensitivity, review transitions, keyboard navigation, load recovery, theme persistence, deterministic queries, local scoring, replay jobs and receipt verification.

The seven-file static export keeps the pinned favicon and the reviewed study JSON. Vite reports 361.37 kB of JavaScript and 35.08 kB of CSS before compression, or 105.16 kB and 7.70 kB gzip.
