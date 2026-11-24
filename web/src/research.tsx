import { useState } from "react";
import { Card, Note, PageHeading, Plot, Select, Status, Table } from "./components";
import { number, percent, points } from "./numbers";
import evidence from "./research-evidence.json";

const policyLabels: Record<string, string> = {
  uniform: "Uniform", greedy: "Greedy", "fixed-5": "Fixed 5%", "fixed-10": "Fixed 10%",
  "fixed-20": "Fixed 20%", adaptive: "Adaptive", matched: "Matched fixed",
};
const percentValue = (value: number | null) => value === null ? "Unavailable" : percent(value, 2);
const decimal = (value: number | null) => value === null ? "Unavailable" : number(value, 4);

export function ResearchExtensions() {
  const [year, setYear] = useState(2025);
  const [budget, setBudget] = useState(5);
  const { adaptive, lifecycle, assistant } = evidence;
  const rows = adaptive.policy_results.filter((row) => row.year === year && row.capacity_percent === budget);
  const size = adaptive.cohorts.find((cohort) => cohort.year === year)?.claims;
  const combined = new Map<string, { name: string; points: [number, number][] }>();
  for (const row of rows) {
    if (row.cohort_rmse.value === null || row.yield.mean === null) continue;
    const point: [number, number] = [row.cohort_rmse.value, row.yield.mean];
    const key = point.join(",");
    const other = combined.get(key);
    combined.set(key, { name: other ? `${other.name} / ${policyLabels[row.policy]}` : policyLabels[row.policy], points: [point] });
  }
  const plot = [...combined.values()];
  return <>
    <PageHeading eyebrow="Research evidence" title="Review policy and model updates"
      description="Explore adaptive allocation on historical CERT cohorts and controlled model updates under simulated feedback delays." />
    <Card title="Adaptive allocation" subtitle={`H4 · ${adaptive.seeds} paired seeds · Retrospective exploratory analysis`}>
      <div className="filters">
        <Select label="Reporting year" value={year} items={adaptive.cohorts.map((row) => ({ value: row.year, text: String(row.year) }))}
          onChange={(value) => setYear(Number(value))} />
        <Select label="Review capacity" value={budget} items={[2, 5, 10, 20].map((n) => ({ value: n, text: `${n}%` }))}
          onChange={(value) => setBudget(Number(value))} />
        <Status value={adaptive.primary.status} />
      </div>
      <Note>{number(size ?? 0)} eligible claim groups. The adaptive rule selected the same exploration resource as the matched
        { ` ${adaptive.primary.matched_resource_percent}% ` }fixed allocation in every evaluated wave.</Note>
      <Plot title="Estimation error and review yield by policy" series={plot}
        rangeX={[0, Math.max(0.02, ...plot.map((row) => row.points[0][0])) * 1.1]}
        rangeY={[0, Math.max(0.4, ...plot.map((row) => row.points[0][1])) * 1.05]}
        xLabels={(value) => points(value, 1)} xTitle="Cohort rate RMSE" yTitle="Review yield" />
      <Table caption="Adaptive allocation evidence" headings={["Policy", "Reviews", "Yield", "Cohort RMSE", "Coverage", "Exploration", "Review minutes"]}
        rows={rows.map((row) => [policyLabels[row.policy], number(row.reviews), percentValue(row.yield.mean),
          points(row.cohort_rmse.value), percentValue(row.coverage.mean), number(row.exploration.mean ?? 0),
          number(row.minutes.mean ?? 0)])} />
      <details className="provenance"><summary>H4 uncertainty and provenance</summary>
        <p>Monte Carlo standard errors use the paired-seed grid. The interval reports uncertainty for the released cohort rate.</p>
        <Table caption="Adaptive allocation Monte Carlo standard errors" headings={["Policy", "Yield MCSE", "RMSE MCSE", "Selected-only RMSE"]}
          rows={rows.map((row) => [policyLabels[row.policy], percentValue(row.yield.mcse),
            points(row.cohort_rmse.mcse), points(row.selected_only_rmse.value)])} />
        <p className="digest">{adaptive.evidence.sha256}</p>
      </details>
    </Card>
    <Card title="Controlled learning" subtitle={`H5 · ${lifecycle.scenarios} synthetic scenario runs · ${lifecycle.cases_per_wave} cases per wave`}>
      <Table caption="Simulated delayed feedback evidence"
        headings={["Scenario", "Delay (waves)", "Update", "Approvals", "Rejected", "Brier Δ ± MCSE", "Yield Δ"]}
        rows={lifecycle.updates.map((row) => [row.scenario, row.delay, row.mode, row.promoted, row.rejected,
          `${decimal(row.brier.mean)} ± ${decimal(row.brier.mcse)}`, percentValue(row.yield.mean)])} />
      <p className="provenance">Paired differences compare post-shift waves with the static reference. Each row covers
        { ` ${lifecycle.updates[0]?.paired_seeds} ` }seeds. [H5] <span className="digest">{lifecycle.evidence.sha256}</span></p>
    </Card>
    <Card title="Analyst tool evaluation" subtitle="H6 · Prespecified local test suite">
      <p>{assistant.deterministic_passes}/10 deterministic scenarios passed with {assistant.critical_failures} critical failures.</p>
      {assistant.local_model && <p>Local model selection matched in {assistant.model_matches}/{assistant.model_attempts} attempts.
        Evaluation gate {assistant.model_gate}.</p>}
      <p className="provenance digest">{assistant.evidence.sha256}</p>
    </Card>
  </>;
}
