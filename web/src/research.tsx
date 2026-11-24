import { useState } from "react";
import { Figures, PageHeading, Section, Segmented, Status, Table } from "./components";
import { Plot, styleFor } from "./charts";
import type { Series } from "./charts";
import { number, percent, points } from "./numbers";
import evidence from "./research-evidence.json";

const policyLabels: Record<string, string> = {
  uniform: "Uniform", greedy: "Greedy", "fixed-5": "Fixed 5%", "fixed-10": "Fixed 10%",
  "fixed-20": "Fixed 20%", adaptive: "Adaptive", matched: "Matched fixed",
};
const scenarioLabels: Record<string, string> = { stationary: "Stationary", prevalence: "Prevalence shift", subgroup: "Subgroup shift" };
const percentValue = (value: number | null) => value === null ? "Unavailable" : percent(value, 2);
const signed = (value: number | null, digits = 4) => value === null ? "Unavailable"
  : `${value > 0 ? "+" : ""}${number(value, digits)}`;
const niceStep = (span: number) => [.0025, .005, .01, .02, .025, .05].find((step) => span / step <= 6) ?? .1;

export function ResearchExtensions() {
  const [year, setYear] = useState(2025);
  const [budget, setBudget] = useState(5);
  const { adaptive, lifecycle, assistant } = evidence;
  const rows = adaptive.policy_results.filter((row) => row.year === year && row.capacity_percent === budget);
  const size = adaptive.cohorts.find((cohort) => cohort.year === year)?.claims;
  const combined = new Map<string, { names: string[]; policies: string[]; point: [number, number] }>();
  for (const row of rows) {
    if (row.cohort_rmse.value === null || row.yield.mean === null) continue;
    const point: [number, number] = [row.cohort_rmse.value, row.yield.mean];
    const key = point.join(",");
    const entry = combined.get(key) ?? { names: [], policies: [], point };
    entry.names.push(policyLabels[row.policy]);
    entry.policies.push(row.policy);
    combined.set(key, entry);
  }
  const plot: Series[] = [...combined.values()].map(({ names, policies, point }) => {
    const style = styleFor(policies.includes("adaptive") ? "fixed-10" : policies[0]);
    return { name: names.join(", "), points: [point], ...style, line: false, emphasis: policies.includes("adaptive") ? "strong" : undefined,
      label: policies.includes("adaptive") ? "Adaptive" : names.length === 1 ? names[0] : undefined, labelAt: "above" };
  });
  const maxX = Math.max(.01, ...plot.map((row) => row.points[0][0]));
  const stepX = niceStep(maxX);
  const topX = Math.ceil(maxX / stepX - 1e-9) * stepX;
  const maxY = Math.ceil(Math.max(.3, ...plot.map((row) => row.points[0][1])) * 10 - 1e-9) / 10;
  return <>
    <PageHeading title="Review policy and model updates"
      description="Three extensions registered after the frozen study: adaptive allocation, controlled model updates and analyst tools. H4 reuses cohorts that had already been examined and H5 uses synthetic data, so these results are exploratory." />
    <Section title="H4 · Adaptive allocation"
      meta={`${adaptive.seeds} paired seeds · ${number(adaptive.rows)} policy evaluations · retrospective`}
      actions={<Status value={adaptive.primary.status} />}>
      <div className="controls" style={{ marginBottom: 22 }}>
        <Segmented label="Reporting year" value={year} items={adaptive.cohorts.map((row) => ({ value: row.year, text: String(row.year) }))}
          onChange={(value) => setYear(Number(value))} />
        <Segmented label="Review capacity" value={budget} items={[2, 5, 10, 20].map((n) => ({ value: n, text: `${n}%` }))}
          onChange={(value) => setBudget(Number(value))} />
      </div>
      <div className="columns wide-left">
        <Plot title="Estimation error and review yield by policy" series={plot}
          rangeX={[0, topX]} rangeY={[0, maxY]} xTicks={Array.from({ length: Math.round(topX / stepX) + 1 }, (_, i) => i * stepX)}
          yTicks={Array.from({ length: Math.round(maxY * 10) + 1 }, (_, i) => i / 10)}
          xFormat={(value) => points(value, stepX < .01 ? 1 : 0)} xValue={points} xTitle="Cohort rate RMSE, percentage points"
          yTitle="Review yield" xName="Rate RMSE" yName="Yield" caption="Policies with identical results share a marker. Greedy has no design-aware estimate, so it is not plotted." />
        <div>
          <Figures compact vertical label="H4 primary comparison" items={[
            { title: "Matched exploration share", value: `${adaptive.primary.matched_resource_percent}%`, detail: "Used by both the adaptive and the fixed rule" },
            { title: "Greedy yield retained", value: percent(adaptive.primary.greedy_yield_retained), detail: "Adaptive rule, primary configuration" },
            { title: "Paired RMSE difference", value: points(adaptive.primary.matched_rmse_difference), detail: "Adaptive minus matched fixed rule" },
          ]} />
          <p className="quiet" style={{ marginTop: 18 }}>In every evaluated wave the adaptive rule chose the same exploration share as its
            matched fixed rule, so the comparison could not show an advantage. {number(size ?? 0)} eligible claim groups in {year}.</p>
        </div>
      </div>
      <div style={{ marginTop: 24 }}>
        <Table caption="Adaptive allocation evidence" numeric={[1, 2, 3, 4, 5, 6]}
          highlight={(i) => rows[i]?.policy === "adaptive"}
          headings={["Policy", "Reviews", "Yield", "Cohort RMSE", "Coverage", "Exploration reviews", "Review minutes"]}
          rows={rows.map((row) => [policyLabels[row.policy], number(row.reviews), percentValue(row.yield.mean),
            points(row.cohort_rmse.value), percentValue(row.coverage.mean), number(row.exploration.mean ?? 0),
            number(row.minutes.mean ?? 0)])} />
      </div>
      <details className="disclosure" style={{ marginTop: 14 }}><summary>Monte Carlo error and provenance</summary>
        <div>
          <Table caption="Adaptive allocation Monte Carlo standard errors" numeric={[1, 2, 3]}
            headings={["Policy", "Yield MCSE", "RMSE MCSE", "Selected-only RMSE"]}
            rows={rows.map((row) => [policyLabels[row.policy], percentValue(row.yield.mcse),
              points(row.cohort_rmse.mcse), points(row.selected_only_rmse.value)])} />
          <p className="quiet" style={{ marginTop: 10 }}>Run {adaptive.evidence.run} · result SHA-256 <span className="digest">{adaptive.evidence.sha256}</span></p>
        </div>
      </details>
    </Section>
    <div className="columns wide-left">
      <Section title="H5 · Controlled learning"
        meta={`${lifecycle.scenarios} synthetic scenario runs · ${lifecycle.waves} waves of ${lifecycle.cases_per_wave} cases`}>
        <Table caption="Simulated delayed feedback evidence" numeric={[1, 3, 4, 5, 6]}
          headings={["Scenario", "Delay", "Update", "Approved", "Rejected", "Brier change", "Yield change"]}
          rows={lifecycle.updates.map((row) => [scenarioLabels[row.scenario] ?? row.scenario,
            `${row.delay} ${row.delay === 1 ? "wave" : "waves"}`, row.mode === "recalibrate" ? "Recalibrate" : "Retrain",
            row.promoted, row.rejected, `${signed(row.brier.mean)} ± ${number(row.brier.mcse, 4)}`, points(row.yield.mean)])} />
        <p className="footnote">Paired differences against the static reference over {lifecycle.updates[0]?.paired_seeds} seeds per row, with
          Monte Carlo standard errors. Negative Brier change means better calibrated predictions. Synthetic data only.</p>
        <p className="quiet" style={{ marginTop: 8 }}>Run {lifecycle.evidence.run} · <span className="digest">{lifecycle.evidence.sha256}</span></p>
      </Section>
      <Section title="H6 · Analyst tools" meta="Prespecified local test suite">
        <Figures compact items={[
          { title: "Deterministic mode", value: `${assistant.deterministic_passes} of 10 passed`, detail: `${assistant.critical_failures} critical failures` },
          { title: "Local language model", value: `${assistant.model_matches} of ${assistant.model_attempts} matched`,
            detail: `${assistant.local_model} · gate ${assistant.model_gate}` },
        ]} />
        <p className="prose" style={{ marginTop: 16, fontSize: ".8125rem" }}>The deterministic tools passed every scenario. The optional
          local model timed out on all eligible requests and failed its gate, so the release ships deterministic mode only.</p>
        <p className="quiet" style={{ marginTop: 10 }}>Run {assistant.evidence.run} · <span className="digest">{assistant.evidence.sha256}</span></p>
      </Section>
    </div>
  </>;
}
