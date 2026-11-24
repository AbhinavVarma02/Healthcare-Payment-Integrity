# Workspace design

The workspace uses a navy navigation shell, warm white analysis surfaces and teal for primary actions and the selected hybrid policy. Display numbers use tabular figures. The workspace uses the system font stack and bundled Lucide icons. One theme covers both modes.

| Workflow | Interaction and source |
| --- | --- |
| Executive overview | Answers the fixed-budget question with the frozen 2025 yield and estimation results. Shows greedy selected-only error beside hybrid and uniform design-aware error. |
| Cohorts | Filter by reporting year and claim part. Download the approved study JSON. A reporting-year chart summarizes the published cohorts. |
| Validation | Inspect precision–recall and reliability, holdout scorecards, preregistered acceptance criteria, active model and monitoring thresholds. |
| Planning and replay | Change capacity, exploration and fictional cost assumptions. Compare matched historical results and reset to the registered defaults. Inspect coverage and Monte Carlo uncertainty in replay. |
| Investigation | The static mode walks through a fictional browser scenario. The local mode uses the persisted SQLite queue, filters, case actions, delayed findings and receipt verification. |
| Operations | Local status, event latency and recent issues come from the API. Candidate controls require local synthetic evidence and explicit approvals. The research lab presents recorded scenario evidence in both modes. |
| Analyst and evidence | Run structured deterministic queries with run IDs and source links. Static mode uses the reviewed aggregate and browser arithmetic. Local mode calls the read-only API. |

Narrow layouts collapse navigation into a menu. Escape restores focus to the toggle. Hash navigation focuses the main landmark. Data tables scroll in named regions and keep their headers visible. Charts expose tabular values via keyboard-operable disclosures. Controls use visible focus rings and honor reduced-motion settings. Static results, fictional scenarios and live local simulation are labeled in context.

## Visual evidence

The desktop overview, planner and mobile overview are actual static export captures. Browser QA covered 11 static and 13 local routes at 1440×900, 768×950 and 390×844, including an aggregate-load error and retry. Edge screenshot contact sheets showed a gap above short pages at narrow widths. Constraining the navigation grid to its content removed the gap, and a browser assertion now checks the sidebar-to-header position. Data tables can still scroll horizontally at narrow widths. [Desktop overview](images/overview.png) · [Desktop planner](images/planner.png) · [Mobile overview](images/overview-mobile.png)

Each engine captured 72 route and viewport combinations plus the planner workflow and an error state. The desktop axe scans across 48 browser, mode and route combinations reported zero violations under the configured WCAG 2.0 and 2.1 A/AA rules. The browser suite checks keyboard focus, reloads, data and form interactions, unexpected requests and console errors. These are scoped checks of the captured application states. [Test evidence](TEST_EVIDENCE.md)

The reviewed build contains 326.16 kB of JavaScript and 12.03 kB of CSS before compression. Vite reports 94.39 kB and 3.66 kB gzip sizes. The frozen JSON is 1.66 MB before compression. In the tested desktop loopback navigations, the static overview heading was ready within 128 ms and the Vite development overview within 239 ms. These are single navigation observations for each engine on the test machine.
