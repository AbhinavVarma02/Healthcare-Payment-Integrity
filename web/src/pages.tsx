import { useState } from "react";
import { ArrowDownToLine, ArrowRight } from "lucide-react";
import { Card, Empty, IntervalChart, Note, PageHeading, Plot, Select, Status, Table } from "./components";
import type { Series } from "./components";
import type { Part, Study } from "./contracts";
import { cents, interval, label, number, percent, points, scenarioNet } from "./numbers";

const capacities = [1, 2, 5, 10].map((value) => ({ value, text: `${value}% of claims` }));
const years = (values: { year: number }[]) => values.map(({ year }) => ({ value: year, text: String(year) })).reverse();
const categories = (values: string[]) => values.map((value) => ({ value, text: label(value) }));
function TradeOff({ study, year, budget, exploration = "hybrid-10" }: {
  study: Study; year: number; budget: number; exploration?: string;
}) {
  const rows = ["greedy", exploration, "uniform"].flatMap((strategy) =>
    study.replay.policies.filter((row) => row.year === year && row.budget_percent === budget &&
      row.weight === "unweighted" && row.strategy === strategy));
  const series: Series[] = rows.flatMap(({ strategy, metrics }) => {
    const error = strategy === "greedy" ? metrics.naive_rmse : metrics.ht_rmse;
    const yieldRate = metrics.yield_rate.mean;
    return error == null || yieldRate == null ? [] : [{
      name: strategy === "greedy" ? "Greedy · selected-only" : label(strategy),
      annotation: strategy === "greedy" ? "Greedy" : strategy === "uniform" ? "Uniform" : "Hybrid",
      annotationBelow: strategy === "greedy",
      points: [[error, yieldRate]],
      tone: strategy === exploration ? 0 : strategy === "greedy" ? 1 : 2,
    }];
  });
  return rows.length ? <div className="tradeoff">
    <Plot title={`${year} mean review yield and rate RMSE at ${budget}% capacity`} series={series}
      rangeX={[0, .25]} rangeY={[0, .5]} xTicks={[0, .05, .1, .15, .2, .25]}
      xLabels={(value) => points(value, 0)} xValue={points}
      xTitle="Rate estimation error (RMSE)" yTitle="Mean review yield" scatter compact />
    <div className="trade-head" aria-hidden="true"><span>Strategy</span><span>Mean review yield</span><span>Rate RMSE</span></div>
    <ul aria-label="Equal-budget review outcomes">{rows.map(({ strategy, metrics: m }) =>
      <li key={strategy} className={strategy === exploration ? "highlight" : undefined}>
        <span><strong>{label(strategy)}</strong><small>{strategy === "greedy" ? "Selected-only" : "Design-aware"}</small></span>
        <strong>{percent(m.yield_rate.mean, 2)}</strong>
        <strong>{points(strategy === "greedy" ? m.naive_rmse : m.ht_rmse)}</strong>
      </li>)}</ul>
  </div> : <Empty text="No historical policy result for this configuration." />;
}

export function Overview({ study }: { study: Study }) {
  const latest = study.models.at(-1)!;
  const latestFinance = study.finance.at(-1)!;
  const results = study.replay.conclusions.components;
  const claims = study.cohorts.reduce((n, cohort) => n + cohort.claims, 0);
  const firstYear = study.cohorts[0].year;
  const lastYear = latest.year;
  const reviews = study.replay.policies.find((row) => row.year === lastYear && row.budget_percent === 5 &&
    row.strategy === "hybrid-10" && row.weight === "unweighted")?.review_count;
  const metrics = [
    { title: "Claims in scope", metric: number(claims), detail: "Part B and DME claim groups" },
    { title: "Study window", metric: `${firstYear}–${lastYear}`, detail: "CMS CERT reporting years" },
    { title: "Replay seeds", metric: number(study.replay.seeds), detail: "Per study configuration" },
    { title: "Matched review budget", metric: number(reviews), detail: `${lastYear} · 5% capacity` },
  ];
  return <>
    <div className="overview-intro">
      <PageHeading eyebrow="Medicare fee-for-service · CMS CERT" title="Study overview"
        description="Prioritize claim reviews within a fixed audit budget. Compare how much each strategy finds and how well it estimates disagreement across the published cohort." />
      <div className="actions"><a className="button" href="#/planner">Plan an audit <ArrowRight size={16} aria-hidden="true" /></a>
        <a className="button secondary" href="#/methods">Study methods</a></div>
    </div>
    <dl className="metric-band">{metrics.map(({ title, metric, detail }) => <div key={title}>
      <dt>{title}</dt><dd><strong>{metric}</strong><small>{detail}</small></dd>
    </div>)}</dl>
    <div className="overview-grid">
      <Card title="The audit strategy trade-off" subtitle={`${lastYear} cohort · ${number(reviews)} reviews per strategy`}>
        <TradeOff study={study} year={lastYear} budget={5} />
        <p className="quiet">Review yield is the share of audited groups with a disagreement. Uniform sampling had the lowest cohort estimation error in this comparison.</p>
        <a className="text-action" href="#/replay">Inspect the replay and coverage <ArrowRight size={15} aria-hidden="true" /></a>
      </Card>
      <Card title="What the study found" subtitle={`Primary holdout · ${latest.year} · protocol ${study.protocol}`} className="findings-card">
        <div className="insight-stat"><strong>{percent(results.hybrid_vs_greedy.yield_ratio)}</strong>
          <p>of greedy review yield retained with 10% random exploration at 5% capacity.</p></div>
        <div className="finding"><div><h3>H1 · Risk scoring</h3><Status value={latest.comparison.status} /></div>
          <p>Boosted trees missed the practical thresholds. The hierarchical lookup remains active for research.</p></div>
        <div className="finding"><div><h3>H2 · Scenario value</h3><Status value={latestFinance.primary.status} /></div>
          <p>Fictional weighted findings changed {percent(latestFinance.primary.relative_weighted_gain, 2)}. The paired interval spans zero.</p></div>
        <div className="finding"><div><h3>H3 · Random exploration</h3><Status value={study.replay.conclusions.status} /></div>
          <p>Hybrid preserved much of greedy yield. Full inverse weighting worsened Brier loss.</p></div>
      </Card>
    </div>
    <Note>CMS suppresses some rows in the public extract. Rates and estimates apply to the eligible published cohort. Financial settings represent fictional scenarios.</Note>
    <nav className="workflow-links" aria-label="Guided study">
      <a href="#/planner"><strong>Choose an audit budget</strong><span>Compare reviews, burden and fictional exposure.</span></a>
      <a href="#/review"><strong>Inspect a decision receipt</strong><span>Follow a fictional review and correction.</span></a>
      <a href="#/validation"><strong>Review the champion decision</strong><span>See the active model and validation limits.</span></a>
    </nav>
  </>;
}

export function Explorer({ study }: { study: Study }) {
  const [part, setPart] = useState<Part | "All">("All");
  const [year, setYear] = useState("all");
  const cohorts = study.cohorts.filter((row) => year === "all" || row.year === Number(year));
  const claims = cohorts.reduce((total, row) => total + (part === "All" ? row.claims : row.parts[part].claims), 0);
  const sourceRows = cohorts.reduce((total, row) => total + (part === "All" ? row.rows : row.parts[part].visible_lines), 0);
  return <>
    <PageHeading eyebrow="Data explorer" title="Cohort coverage"
      description="Reconciled source rows, eligible claim groups, and public release vintages." />
    <div className="evidence-grid cohort-grid">
      <Card title="Cohort inventory" subtitle="Use the filters to inspect the reconciled counts."
        action={<a className="button secondary" href="./study.json" download><ArrowDownToLine size={15} aria-hidden="true" /> Study JSON</a>}>
        <div className="filters">
          <Select label="Reporting year" value={year} onChange={setYear} items={[{ value: "all", text: "All years" }, ...years(study.cohorts)]} />
          <Select label="Claim part" value={part} onChange={(value) => setPart(value as Part | "All")} items={categories(["All", "Part B", "DME"])} />
        </div>
        <Table caption="Cohort counts by reporting year" numeric={part === "All" ? [1, 2, 3, 4] : [1, 2, 3]}
          headings={part === "All" ? ["Year", "Source rows", "In-scope rows", "In-scope claims", "Disagreements", "Catalog vintage"]
                                    : ["Year", "Published rows", "Eligible claims", "Missing provider categories", "Catalog vintage"]}
          rows={cohorts.map((row) => {
            if (part === "Part B" || part === "DME") {
              const group = row.parts[part];
              return [row.year, number(group.visible_lines), number(group.claims), number(group.missing_provider), row.version];
            }
            return [row.year, number(row.rows), number(row.in_scope_rows), number(row.claims), number(row.disagreements), row.version];
          })} />
      </Card>
      <Card title="Filtered scope" subtitle={`${cohorts.length} reporting ${cohorts.length === 1 ? "year" : "years"} · ${part === "All" ? "Part B and DME" : part}`}>
        <dl className="details">
          <div><dt>{part === "All" ? "Source rows" : "Published part rows"}</dt><dd>{number(sourceRows)}</dd></div>
          <div><dt>Eligible claims</dt><dd>{number(claims)}</dd></div>
          <div><dt>Latest release</dt><dd>{study.cohorts.at(-1)!.year}</dd></div>
        </dl>
        <p className="quiet">The reporting year describes a submission window ending June 30 of the prior year.</p>
      </Card>
    </div>
    <Card title="Disagreement by reporting year" subtitle="Full study series across all parts.">
      <Plot title="Observed disagreement rate by CMS reporting year" series={[{ name: "Eligible public cohort",
        points: study.cohorts.map(({ year, disagreements, claims }) => [year, disagreements / claims]) }]}
        rangeX={[study.cohorts[0].year, study.cohorts.at(-1)!.year]} rangeY={[0, 0.4]}
        xTicks={study.cohorts.map((row) => row.year)} xLabels={String} yTitle="Observed disagreement" xTitle="CMS reporting year" />
    </Card>
    <Note>Reporting years represent submission windows that end on June 30 of the prior year. Grouping and decisions follow the rows available within each release.</Note>
  </>;
}

export function Models({ study }: { study: Study }) {
  const [year, setYear] = useState(study.models.at(-1)!.year);
  const [budget, setBudget] = useState(5);
  const cohort = study.models.find((row) => row.year === year)!;
  const charts = ["lookup", study.selection.challenger];
  return <>
    <PageHeading eyebrow="Risk models" title="Discrimination and calibration"
      description="Temporal holdout comparisons against a hierarchical shrinkage baseline." />
    <div className="filters">
      <Select label="Reporting year" value={year} onChange={(v) => setYear(+v)} items={years(study.models)} />
      <Select label="Review capacity" value={budget} onChange={(v) => setBudget(+v)} items={capacities} />
    </div>
    <div className="two-columns">
      <Card title="Precision–recall">
        <Plot title={`Precision–recall comparison for ${year}`}
          series={charts.map((name) => ({ name: label(name), points: cohort.models[name].pr_curve }))}
          rangeX={[0, 1]} rangeY={[0, 1]} xTitle="Recall" yTitle="Precision" />
      </Card>
      <Card title="Reliability">
        <Plot title={`Observed versus predicted disagreement for ${year}`}
          series={charts.map((name) => ({ name: label(name), points: cohort.models[name].calibration.map(
            (item) => [item.predicted, item.observed]), pointLabels: cohort.models[name].calibration.map(
            (item) => `Bin ${item.bin} · ${number(item.claims)} claims`) }))}
          rangeX={[0, .6]} rangeY={[0, .6]} diagonal xTitle="Mean calibrated risk" yTitle="Observed disagreement"
          legendNote="The dashed diagonal marks equal predicted and observed rates." />
      </Card>
    </div>
    <Card title="Holdout scorecards" subtitle={`${number(cohort.claims)} eligible claims · ${number(cohort.findings)} disagreements`}
      action={<Status value={cohort.comparison.status} />}>
      <Table caption="Risk model performance" numeric={[1, 2, 3, 4, 5]}
        headings={["Model", "Average precision", "AUROC", "Brier", "Precision", "Recall"]}
        rows={Object.entries(cohort.models).map(([name, row]) => [label(name), number(row.ap, 3),
          number(row.auroc, 3), number(row.brier, 3), percent(row.capacity[budget].precision),
          percent(row.capacity[budget].recall)])} />
    </Card>
    <Card title="Challenger acceptance criteria"
      subtitle={year === 2025 ? "Frozen H1 thresholds · 2025 primary holdout" : `Frozen H1 thresholds · ${year} secondary holdout`}>
      <div className="two-columns">
        <IntervalChart label="Average precision change" estimate={cohort.comparison.average_precision_delta}
          bounds={cohort.comparison.intervals.ap.bounds} format={(value) => number(value, 4)} />
        <IntervalChart label="Precision change at 5% capacity" estimate={cohort.comparison.precision_at_5_delta}
          bounds={cohort.comparison.intervals.precision_at_5.bounds} format={(value) => points(value, 2)} />
      </div>
      <Table caption="Observed challenger change and preregistered thresholds" headings={["Measure", "Observed change", "97.5% paired interval", "Required lower bound"]}
        rows={[
          ["Average precision", number(cohort.comparison.average_precision_delta, 5),
            interval(cohort.comparison.intervals.ap, (v) => number(v, 5)), "Above 0.01"],
          ["Precision at 5% capacity", points(cohort.comparison.precision_at_5_delta),
            interval(cohort.comparison.intervals.precision_at_5, points), "Above 2 pp"],
        ]} />
      <p className="quiet">Both lower interval bounds must clear their respective thresholds. The lookup remains the research champion.</p>
    </Card>
    <Note>Reliability plots omit cells below disclosure thresholds. The paired intervals describe variation within the eligible released cohort.</Note>
  </>;
}

export function Planner({ study }: { study: Study }) {
  const [year, setYear] = useState(study.finance.at(-1)!.year);
  const [budget, setBudget] = useState(5);
  const [exposure, setExposure] = useState(study.finance_primary.exposure);
  const [fraction, setFraction] = useState(study.finance_primary.relevant_percent);
  const [cost, setCost] = useState(study.finance_primary.review_cost_cents);
  const [exploration, setExploration] = useState("hybrid-10");
  const cohort = study.finance.find((row) => row.year === year)!;
  const chosen = cohort.grid.find((row) => row.budget_percent === budget && row.exposure === exposure &&
    row.relevant_percent === fraction && row.review_cost_cents === cost);
  return <>
    <PageHeading eyebrow="Audit planner" title="Review budget scenarios"
      description="Compare review strategies against the same historical cohort and capacity." />
    <div className="control-grid">
      <Card title="Study configuration" subtitle="Matched capacity within each study comparison" className="configuration"
        action={<button className="button secondary" onClick={() => {
          setYear(study.finance.at(-1)!.year); setBudget(5); setExploration("hybrid-10");
          setExposure(study.finance_primary.exposure); setFraction(study.finance_primary.relevant_percent);
          setCost(study.finance_primary.review_cost_cents);
        }}>Reset scenario</button>}>
        <div className="filters">
          <Select label="Reporting year" value={year} onChange={(v) => setYear(+v)} items={years(study.finance)} />
          <Select label="Review capacity" value={budget} onChange={(v) => setBudget(+v)} items={capacities} />
          <Select label="Hybrid exploration" value={exploration} onChange={setExploration} items={categories(["hybrid-5", "hybrid-10", "hybrid-20"])} />
        </div>
        <details className="financial-settings">
          <summary>Fictional financial assumptions</summary>
          <div className="filters">
            <Select label="Exposure scenario" value={exposure} onChange={setExposure}
              items={categories(["DME higher", "Part B higher", "Uniform"])} />
            <Select label="Relevant fraction" value={fraction} onChange={(v) => setFraction(+v)}
              items={[15, 35, 60].map((value) => ({ value, text: `${value}%` }))} />
            <Select label="Cost per review" value={cost} onChange={(v) => setCost(+v)}
              items={[1500, 3000, 6000].map((value) => ({ value, text: cents(value) }))} />
          </div>
        </details>
      </Card>
      <Card title="Review design comparison" subtitle={`${year} cohort · ${budget}% capacity · H3 historical replay`}>
        <TradeOff study={study} year={year} budget={budget} exploration={exploration} />
        <a className="text-action" href="#/replay">See interval coverage and learning results <ArrowRight size={15} aria-hidden="true" /></a>
      </Card>
    </div>
    <Card title="Fictional financial scenario comparison"
      subtitle={`${number(cohort.eligible)} eligible claims · ${exposure} · ${fraction}% relevant · ${cents(cost)} per review`}>
      {chosen ? <Table caption="Matched audit budget strategy comparison" numeric={[1, 2, 3, 4, 5, 6]}
        headings={["Strategy", "Reviewed", "Findings", "Yield", "Nonfindings / finding", "Expected scenario net", "DME share"]}
        rows={Object.entries(chosen.plans).map(([name, plan]) => [label(name), number(plan.reviews),
          number(plan.findings), percent(plan.yield_rate), number(plan.nonfinding_per_finding, 2),
          cents(plan.expected_scenario_net_cents), percent(plan.review_share.DME)])} />
        : <Empty text="This combination has no measured result." />}
    </Card>
    <Note>The primary 5% scenario also tested a part cap and reserved {number(cohort.primary.constrained.exploratory_reviews)} reviews for exploration. See Policy replay for estimates under known selection probabilities.</Note>
  </>;
}

export function Replay({ study }: { study: Study }) {
  const [year, setYear] = useState(study.replay.timeline.at(-1)!.year);
  const [capacity, setCapacity] = useState(5);
  const [weight, setWeight] = useState("unweighted");
  const [strategy, setStrategy] = useState("hybrid-10");
  const rows = study.replay.policies.filter((row) => row.year === year && row.budget_percent === capacity && row.weight === weight);
  const selected = rows.find((row) => row.strategy === strategy);
  const designs = ["uniform", "greedy", "hybrid-5", "hybrid-10", "hybrid-20", "stratified"];
  const policyChart: Series[] = designs.flatMap((key, tone) => {
    const measures = study.replay.policies.filter(
      (row) => row.year === year && row.strategy === key && row.weight === weight,
    ).sort((a, b) => a.budget_percent - b.budget_percent);
    const observed = measures.filter((row) => row.metrics.yield_rate.mean !== null);
    return observed.length ? [{
      name: label(key), tone,
      points: observed.map((row) => [row.budget_percent / 100, row.metrics.yield_rate.mean!]),
      spread: key === strategy ? observed.map(({ metrics }) => {
        const quantiles = metrics.yield_rate.quantiles;
        return quantiles ? [quantiles[0], quantiles[2]] : null;
      }) : undefined,
    }] : [];
  });
  return <>
    <PageHeading eyebrow="Policy replay" title="Exploration and cohort estimation"
      description="Historical CERT outcomes, simulated review choices, and delayed feedback." />
    <div className="filters">
      <Select label="Reporting year" value={year} onChange={(v) => setYear(+v)} items={years(study.replay.timeline)} />
      <Select label="Review capacity" value={capacity} onChange={(v) => setCapacity(+v)} items={capacities} />
      <Select label="Learning weights" value={weight} onChange={setWeight} items={categories(["unweighted", "ipw", "clipped"])} />
      <Select label="Strategy details" value={strategy} onChange={setStrategy}
        items={categories(["uniform", "greedy", "hybrid-5", "hybrid-10", "hybrid-20", "stratified"])} />
    </div>
    <Card title="Review yield by capacity" subtitle={`${year} · ${label(weight)} · ${study.replay.seeds} replay seeds`}>
      <Plot title={`Replay mean yield across the four capacities for ${year}`}
        series={policyChart} rangeX={[0.01, 0.1]} rangeY={[0, 0.5]}
        xTicks={[0.01, 0.02, 0.05, 0.1]} xTitle="Share of eligible claims reviewed" yTitle="Mean review yield"
        legendNote={selected ? `Whiskers show the 2.5th–97.5th percentiles across replay seeds for ${label(strategy)}.` : undefined} />
    </Card>
    <Card title="Yield and estimation trade-off" subtitle={`${capacity}% capacity · Precomputed across ${study.replay.seeds} seeds`}>
      <Table caption="Replay strategy comparison" numeric={[1, 2, 3, 4, 5, 6]}
        headings={["Strategy", "Reviews per seed", "Mean yield", "Selected-only RMSE", "Design-aware RMSE", "95% interval coverage", "Brier"]}
        rows={rows.map((row) => [label(row.strategy), number(row.review_count), percent(row.metrics.yield_rate.mean),
          points(row.metrics.naive_rmse), points(row.metrics.ht_rmse), percent(row.metrics.coverage.mean),
          number(row.metrics.brier.mean, 4)])} />
    </Card>
    <div className="evidence-grid">
      <Card title="Selected strategy" subtitle={label(strategy)}>
        {selected ? <Table caption="Selected strategy simulation diagnostics"
          headings={["Metric", "Mean", "Monte Carlo SE"]}
          rows={[
            ["Cumulative findings", number(selected.metrics.cumulative_findings.mean, 1), number(selected.metrics.cumulative_findings.mcse, 2)],
            ["Effective sample size", number(selected.metrics.ess.mean, 1), number(selected.metrics.ess.mcse, 2)],
            ["Design-aware bias", points(selected.metrics.ht_bias.mean), points(selected.metrics.ht_bias.mcse)],
            ["Expected calibration error", points(selected.metrics.ece.mean), points(selected.metrics.ece.mcse)],
          ]} /> : <Empty text="This weighting and strategy combination has no measured result." />}
      </Card>
      <Card title="Outcome timeline" subtitle="Public catalog vintage proxies for label availability">
        <Table caption="Simulated decision and outcome availability dates"
          headings={["Year", "Decision", "Available"]} rows={study.replay.timeline.map((row) => [
            row.year, row.decision, row.label_available])} />
      </Card>
    </div>
    <Note>Greedy leaves some claims with zero inclusion probability. Its selected-only rate describes the reviewed claims. Design-aware intervals measure repeated review selections within a fixed released cohort. Uniform random is the matched-capacity reference for estimation precision.</Note>
  </>;
}

export function Finance({ study }: { study: Study }) {
  const result = study.finance.at(-1)!;
  const [risk, setRisk] = useState(30);
  const [exposure, setExposure] = useState(25000);
  const [fraction, setFraction] = useState(35);
  const [cost, setCost] = useState(3000);
  const net = scenarioNet(risk, exposure, fraction, cost);
  const sensitivity = Array.from({ length: 11 }, (_, i): [number, number] =>
    [i / 10, scenarioNet(i * 10, exposure, fraction, cost) ?? 0]);
  const rangeMin = Math.min(0, sensitivity[0][1]);
  const rangeMax = Math.max(0, sensitivity.at(-1)![1]);
  const scale = Math.max(100, (rangeMax - rangeMin) / 4);
  const order = 10 ** Math.floor(Math.log10(scale));
  const step = Math.ceil(scale / order) * order;
  const lower = Math.floor(rangeMin / step) * step;
  const upper = Math.max(step, Math.ceil(rangeMax / step) * step);
  const ticks = Array.from({ length: (upper - lower) / step + 1 }, (_, i) => lower + i * step);
  const currencyAxis = new Intl.NumberFormat("en-US", {
    style: "currency", currency: "USD", notation: "compact", maximumFractionDigits: 1,
  });
  const values = [
    { title: "Predicted disagreement (%)", value: risk, setter: setRisk, max: 100 },
    { title: "Fictional exposure (cents)", value: exposure, setter: setExposure, max: 10000000 },
    { title: "Relevant fraction (%)", value: fraction, setter: setFraction, max: 100 },
    { title: "Review cost (cents)", value: cost, setter: setCost, max: 10000000 },
  ];
  return <>
    <PageHeading eyebrow="Financial analysis" title="Fictional value sensitivity"
      description="Explore how review assumptions change the modeled value of reviewing one claim." />
    <div className="control-grid">
      <Card title="Scenario calculator" subtitle="Calculated in the browser from your inputs">
        <div className="calculator">{values.map((item) => <label key={item.title} className="control">
          <span>{item.title}</span><input type="number" min={0} max={item.max} step="1" value={Number.isNaN(item.value) ? "" : item.value}
            onChange={(event) => item.setter(event.target.valueAsNumber)} />
        </label>)}</div>
        <label className="control slider-control"><span>Adjust predicted disagreement <strong aria-hidden="true">{Number.isFinite(risk) ? `${risk}%` : "—"}</strong></span>
          <input type="range" min={0} max={100} value={Number.isFinite(risk) ? risk : 0}
            aria-valuetext={`${Number.isFinite(risk) ? risk : 0}%`} onChange={(event) => setRisk(event.target.valueAsNumber)} /></label>
        <div className="result-block"><span>Expected scenario net per review</span>
          <output aria-live="polite">{cents(net)}</output>
        </div>
      </Card>
      <Card title="Net value by predicted disagreement" subtitle="Fictional inputs · USD per review">
        {net === null ? <Empty text="Enter whole numbers within the displayed input limits to view the sensitivity." />
          : <Plot title="Fictional net value as predicted disagreement changes"
            series={[{ name: "Scenario net", points: sensitivity },
              { name: "Current inputs", tone: 3, points: [[risk / 100, net]] }]}
            rangeX={[0, 1]} rangeY={[lower, upper]} yTicks={ticks} referenceY={0}
            yLabel={(value) => currencyAxis.format(value / 100)} yValue={cents}
            xTitle="Predicted disagreement" yTitle="Scenario net per review" />}
      </Card>
    </div>
      <Card title="Primary study comparison" subtitle={`${result.year} · 5% review capacity · 97.5% paired bootstrap intervals`}
        action={<Status value={result.primary.status} />}>
        <div className="two-columns">
          <IntervalChart label="Scenario-weighted findings" estimate={result.primary.relative_weighted_gain}
            bounds={result.primary.intervals.weighted_gain.bounds} format={(value) => percent(value, 2)} />
          <IntervalChart label="Nonfindings per finding" estimate={result.primary.burden_delta}
            bounds={result.primary.intervals.burden_delta.bounds} format={(value) => number(value, 2)} />
        </div>
        <Table caption="Financial comparison with paired intervals" numeric={[1, 2]} headings={["Measure", "Difference", "97.5% interval"]}
          rows={[
            ["Scenario-weighted findings", percent(result.primary.relative_weighted_gain),
              interval(result.primary.intervals.weighted_gain)],
            ["Nonfindings per finding", number(result.primary.burden_delta, 2),
              interval(result.primary.intervals.burden_delta, (v) => number(v, 2))],
          ]} />
      </Card>
    <Note>Expected scenario net equals risk × exposure × relevant fraction, less review cost. CERT does not supply the actual payment or recoverable amount needed to validate savings.</Note>
  </>;
}

export function Validation({ study }: { study: Study }) {
  return <>
    <PageHeading eyebrow="Model governance" title="Validation and monitoring"
      description="Research scorecard status, data-shift diagnostics, and measured outcomes." />
    <div className="evidence-grid">
      <Card title="Research model registry" action={<Status value={study.validation.status} />}>
        <dl className="details"><div><dt>Active version</dt><dd>{study.validation.active}</dd></div>
          <div><dt>Operational promotion</dt><dd>{study.validation.promotion}</dd></div>
          <div><dt>Fit process</dt><dd>{number(study.split.train)} training and {number(study.split.calibration)} calibration groups</dd></div>
        </dl>
      </Card>
      <Card title="Drift thresholds" subtitle="Set from calibration and development cohorts">
        <dl className="details">{Object.entries(study.validation.thresholds).map(([key, value]) =>
          <div key={key}><dt>{label(key)}</dt><dd>{number(value, 3)}</dd></div>)}</dl>
      </Card>
    </div>
    <Card title="Holdout monitoring" subtitle="Review covariate alerts alongside outcome-based performance for each released cohort.">
      <Table caption="Annual feature shift and realized model performance" numeric={[1, 2, 4, 5, 6]}
        headings={["Year", "Score PSI", "Provider distance", "Covariate alerts", "Labelled claims", "Observed rate", "Brier"]}
        rows={study.validation.cohorts.map((row) => [row.year, number(row.drift.score_psi, 3),
          number(row.drift.category_js_distance, 3), row.covariate_alerts.map(label).join(", ") || "None",
          number(row.labelled_claims), percent(row.observed_rate), number(row.brier, 3)])} />
    </Card>
    <Note>Covariate alerts use features and scores. Brier and the observed rate become available only after outcome release. The validation is developer-authored.</Note>
  </>;
}

export function Methods({ study }: { study: Study }) {
  return <>
    <PageHeading eyebrow="Study records" title="Methodology and runs"
      description="Research design, frozen settings, and fingerprints of the source results behind this workspace." />
    <div className="evidence-grid">
      <Card title="Study design" subtitle={`Protocol ${study.protocol}`}>
        <dl className="details">
          <div><dt>Decision unit</dt><dd>One reporting-year control-number group in the published Part B or DME sample</dd></div>
          <div><dt>Outcome</dt><dd>At least one published disagreement among groups with recognized outcomes</dd></div>
          <div><dt>Uncertainty</dt><dd>Paired claim bootstrap for H1/H2 and conditional finite-population inference for H3</dd></div>
          <div><dt>Protocol commit</dt><dd><code>{study.freeze_commit}</code></dd></div>
        </dl>
      </Card>
      <Card title="References"><ul className="reference-list">
        <li><a href="https://data.cms.gov/provider-compliance/fee-for-service-error-rate-improper-payment/medicare-fee-for-service-comprehensive-error-rate-testing">CMS CERT catalog and documentation</a></li>
        <li><a href="https://ojs.aaai.org/index.php/AAAI/article/view/25637">Henderson et al. · audit selection and population estimation</a></li>
        <li><a href="https://arxiv.org/abs/2509.18739">Revelas, Boldea and Werker · selection strategy consistency</a></li>
      </ul></Card>
    </div>
    <Card title="Result ledger">
      <Table caption="Run IDs and exact source digests" headings={["Run", "SHA-256"]} rows={study.ledger.map((item) =>
        [item.run, <code key={item.run}>{item.sha256}</code>])} />
    </Card>
  </>;
}
