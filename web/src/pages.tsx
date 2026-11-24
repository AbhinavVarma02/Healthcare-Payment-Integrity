import { useState } from "react";
import { ArrowDownToLine, ArrowRight, RotateCcw, Scale, ShieldCheck, Sigma, WalletCards } from "lucide-react";
import {
  Empty, Figures, NextStep, Note, PageHeading, Panel, Section, Segmented, Select, Status, Table, Value, tour,
} from "./components";
import { DelayTimeline, IntervalPlot, LegendKey, Plot, ThresholdBar, styleFor } from "./charts";
import type { Series } from "./charts";
import type { Part, Policy, Study } from "./contracts";
import { cents, interval, label, number, percent, points, scenarioNet } from "./numbers";

const capacityOptions = [1, 2, 5, 10].map((value) => ({ value, text: `${value}%` }));
const yearOptions = (values: { year: number }[]) => values.map(({ year }) => ({ value: year, text: String(year) }));
const sum = (values: number[]) => values.reduce((total, value) => total + value, 0);
const policiesAt = (study: Study, year: number, budget: number, weight = "unweighted") =>
  study.replay.policies.filter((row) => row.year === year && row.budget_percent === budget && row.weight === weight);
const errorOf = (row: Policy) => row.strategy === "greedy" ? row.metrics.naive_rmse : row.metrics.ht_rmse;
const ceilTo = (value: number, step: number) => Math.max(step, Math.ceil(value / step - 1e-9) * step);

/** Yield against estimation error for the exploration family at one matched capacity. */
function Frontier({ rows, highlight, title, lead }: {
  rows: Policy[]; highlight: string; title: string; lead?: React.ReactNode;
}) {
  const order = ["greedy", "hybrid-5", "hybrid-10", "hybrid-20", "uniform"];
  const measured = order.flatMap((strategy) => {
    const row = rows.find((item) => item.strategy === strategy);
    const error = row && errorOf(row);
    return row && error != null && row.metrics.yield_rate.mean != null ? [{ strategy, error, yield: row.metrics.yield_rate.mean }] : [];
  });
  if (!measured.length) return <Empty text="No historical policy result for this configuration." />;
  const headline = new Set(["greedy", "uniform", highlight]);
  const series: Series[] = measured.map(({ strategy, error, yield: rate }) => {
    const style = styleFor(strategy);
    const greedy = strategy === "greedy";
    return {
      name: greedy ? "Greedy (selected-only rate)" : label(strategy), points: [[error, rate]], ...style,
      hollow: greedy, emphasis: headline.has(strategy) ? "strong" : "muted",
      label: headline.has(strategy) ? (greedy ? "Greedy" : strategy === "uniform" ? "Uniform" : label(strategy)) : undefined,
      labelAt: strategy === "uniform" ? "right" : strategy === highlight ? "below" : "above",
      details: [greedy ? "Selected-only estimator" : "Design-aware estimator"],
    };
  });
  const path = measured.filter(({ strategy }) => strategy !== "greedy").sort((a, b) => b.error - a.error)
    .map(({ error, yield: rate }): [number, number] => [error, rate]);
  const maxX = ceilTo(Math.max(...measured.map((row) => row.error)) * 100, 5) / 100;
  const maxY = ceilTo(Math.max(...measured.map((row) => row.yield)) * 10, 1) / 10;
  return <Plot title={title} series={series} guides={[{ points: path }]}
    rangeX={[0, maxX]} rangeY={[0, maxY]}
    xTicks={Array.from({ length: Math.round(maxX * 20) + 1 }, (_, i) => i * .05)}
    yTicks={Array.from({ length: Math.round(maxY * 10) + 1 }, (_, i) => i / 10)}
    xFormat={(value) => points(value, 0)} xValue={points} xTitle="Cohort rate RMSE, percentage points (lower is better)"
    yTitle="Mean review yield (higher is better)" xName="Rate RMSE" yName="Mean yield" lead={lead} height={290} />;
}

function StrategyList({ rows, highlight }: { rows: Policy[]; highlight: string }) {
  const shown = ["greedy", highlight, "uniform"].flatMap((strategy) => rows.filter((row) => row.strategy === strategy));
  return <>
    <div className="strategy-head" aria-hidden="true">
      <span>Strategy</span><span>Mean yield</span><span>Rate RMSE</span>
    </div>
    <ul className="strategy-list" aria-label="Equal-budget review outcomes">{shown.map((row) => {
      const style = styleFor(row.strategy);
      return <li key={row.strategy} className={row.strategy === highlight ? "highlight" : undefined}>
        <span className="strategy-name"><LegendKey size={4.6} series={{ ...style, line: false, hollow: row.strategy === "greedy" }} />
          <span><strong>{label(row.strategy)}</strong>
            <small>{row.strategy === "greedy" ? "Selected-only estimate" : "Design-aware estimate"}</small></span></span>
        <strong>{percent(row.metrics.yield_rate.mean, 2)}</strong>
        <strong><Value text={points(errorOf(row))} /></strong>
      </li>;
    })}</ul>
  </>;
}

function headlineSentence(rows: Policy[], strategy: string) {
  const greedy = rows.find((row) => row.strategy === "greedy");
  const chosen = rows.find((row) => row.strategy === strategy);
  const uniform = rows.find((row) => row.strategy === "uniform");
  const ratio = greedy?.metrics.yield_rate.mean && chosen?.metrics.yield_rate.mean != null
    ? chosen.metrics.yield_rate.mean / greedy.metrics.yield_rate.mean : null;
  if (!greedy || !chosen || !uniform || ratio === null) return undefined;
  return <>{label(strategy)} kept <strong>{percent(ratio)}</strong> of greedy yield, with a design-aware rate RMSE
    of <strong><Value text={points(chosen.metrics.ht_rmse)} /></strong>. Greedy’s selected-only rate had
    an RMSE of <Value text={points(greedy.metrics.naive_rmse)} />. Uniform sampling was the most precise
    at <Value text={points(uniform.metrics.ht_rmse)} />.</>;
}

export function Overview({ study }: { study: Study }) {
  const year = study.models.at(-1)!.year;
  const model = study.models.at(-1)!;
  const finance = study.finance.at(-1)!;
  const primary = study.finance_primary;
  const components = study.replay.conclusions.components;
  const rows = policiesAt(study, year, 5);
  const reviews = rows.find((row) => row.strategy === "hybrid-10")?.review_count;
  const plans = finance.grid.find((row) => row.budget_percent === 5 && row.exposure === primary.exposure &&
    row.relevant_percent === primary.relevant_percent && row.review_cost_cents === primary.review_cost_cents)?.plans;
  const missed = [!components.stratified_vs_uniform.supported && "score stratification",
    !components.ipw_vs_unweighted.supported && "inverse weighting"].filter(Boolean);
  const first = study.cohorts[0].year, last = study.cohorts.at(-1)!.year;
  return <>
    <PageHeading kicker={`Medicare fee-for-service · CMS CERT ${first}–${last}`} title="Study overview"
      description="Review teams can examine only a small share of claims. This study replays eight years of published CERT review outcomes to compare how much each selection strategy finds with how accurately it measures the disagreement rate across the cohort."
      aside={<><a className="button" href="#/planner">Plan an audit<ArrowRight size={15} aria-hidden="true" /></a>
        <a className="button secondary" href="#/methods">Read the methods</a></>} />
    <Figures compact label="Study scope" items={[
      { title: "Source", value: `${study.cohorts.length} CERT releases`, detail: `Reporting years ${first}–${last}` },
      { title: "Decision unit", value: `${number(sum(study.cohorts.map((row) => row.claims)))} claim groups`, detail: "Part B and DME" },
      { title: "Replay", value: `${number(study.replay.seeds)} seeds`, detail: "Per strategy and capacity" },
      { title: "Protocol", value: study.protocol, detail: "Frozen before the holdout was read" },
    ]} />
    <div className="columns wide-left" style={{ marginTop: "var(--space)" }}>
      <Section title="Review yield and estimation error"
        meta={`${year} holdout · 5% capacity · ${number(reviews)} reviews per strategy · ${study.replay.seeds} seeds`}>
        <Frontier rows={rows} highlight="hybrid-10" title={`${year} mean review yield and cohort rate RMSE at 5% capacity`}
          lead={headlineSentence(rows, "hybrid-10")} />
        <StrategyList rows={rows} highlight="hybrid-10" />
        <a className="text-link" href="#/replay">Seed percentiles, coverage and learning results<ArrowRight size={14} aria-hidden="true" /></a>
      </Section>
      <Section title="Frozen hypotheses" meta={`Protocol ${study.protocol} · ${year} primary holdout`}>
        <div className="verdicts">
          <article className="verdict">
            <div className="verdict-head"><h3><span>H1</span>Risk model</h3><Status value={model.comparison.status} /></div>
            <p>The boosted challenger did not clear the frozen practical thresholds. Average precision changed
              by {number(model.comparison.average_precision_delta, 3)} (97.5% interval {interval(model.comparison.intervals.ap, (v) => number(v, 3))}).
              The hierarchical lookup stays active for research.</p>
            <a href="#/models">Model comparison</a>
          </article>
          <article className="verdict">
            <div className="verdict-head"><h3><span>H2</span>Fictional value ranking</h3><Status value={finance.primary.status} /></div>
            <p>{plans ? <>At {number(plans.value.reviews)} reviews, value ranking found {number(plans.value.findings)} disagreements
              against {number(plans.risk.findings)} for risk ranking. </> : null}Fictional weighted findings changed
              by {percent(finance.primary.relative_weighted_gain, 2)} (97.5% interval {interval(finance.primary.intervals.weighted_gain, (v) => percent(v, 2))}).</p>
            <a href="#/finance">Scenario intervals</a>
          </article>
          <article className="verdict">
            <div className="verdict-head"><h3><span>H3</span>Exploration and estimation</h3><Status value={study.replay.conclusions.status} /></div>
            <p>Ten percent exploration kept {percent(components.hybrid_vs_greedy.yield_ratio)} of greedy yield
              {components.hybrid_vs_greedy.supported ? ", meeting its criterion" : ""}.
              {missed.length ? ` ${missed.join(" and ").replace(/^./, (c) => c.toUpperCase())} missed ${missed.length > 1 ? "their" : "its"} criteria.` : ""}</p>
            <a href="#/replay">Replay results</a>
          </article>
        </div>
      </Section>
    </div>
    <Section title="Guided walkthrough" meta="Four steps, about three minutes">
      <ol className="steps" style={{ "--count": tour.length } as React.CSSProperties}>
        {tour.map((step) => <li key={step.key}><a href={`#/${step.key}`}>
          <strong>{step.title}</strong><span>{step.text}</span></a></li>)}
      </ol>
    </Section>
    <Section title="Scope and limits">
      <dl className="limits" style={{ "--count": 4 } as React.CSSProperties}>
        <div><dt><Sigma size={15} aria-hidden="true" />Published sample only</dt>
          <dd>Results describe the eligible claims released after CMS suppression. They are not national improper payment rates.</dd></div>
        <div><dt><Scale size={15} aria-hidden="true" />Review outcomes</dt>
          <dd>A disagreement is a CERT review decision. It is not evidence of fraud, intent or recoverable loss.</dd></div>
        <div><dt><WalletCards size={15} aria-hidden="true" />Fictional finance</dt>
          <dd>Dollar amounts are scenario inputs. The study claims no savings or recoveries.</dd></div>
        <div><dt><ShieldCheck size={15} aria-hidden="true" />Research-only model</dt>
          <dd>No model is approved for operational use. Human reviewers keep every decision.</dd></div>
      </dl>
    </Section>
  </>;
}

export function Explorer({ study }: { study: Study }) {
  const [part, setPart] = useState<Part | "All">("All");
  const [year, setYear] = useState("all");
  const cohorts = study.cohorts.filter((row) => year === "all" || row.year === Number(year));
  const claims = sum(cohorts.map((row) => part === "All" ? row.claims : row.parts[part].claims));
  const sourceRows = sum(cohorts.map((row) => part === "All" ? row.rows : row.parts[part].visible_lines));
  const disagreements = sum(cohorts.map((row) => row.disagreements));
  return <>
    <PageHeading title="Cohort coverage"
      description="Source rows, eligible claim groups and published outcomes for each CMS CERT release, reconciled from the downloaded files."
      aside={<a className="button secondary" href="./study.json" download><ArrowDownToLine size={15} aria-hidden="true" />Download study JSON</a>} />
    <div className="controls">
      <Select label="Reporting year" value={year} onChange={setYear}
        items={[{ value: "all", text: "All years" }, ...yearOptions(study.cohorts).reverse()]} />
      <Segmented label="Claim part" value={part} onChange={(value) => setPart(value as Part | "All")}
        items={[{ value: "All", text: "All parts" }, { value: "Part B", text: "Part B" }, { value: "DME", text: "DME" }]} />
    </div>
    <div className="columns wide-left" style={{ marginTop: 28 }}>
      <Section title="Release inventory" meta={part === "All" ? "Rows, eligible groups and disagreements" : `${part} rows and eligible groups`}>
        <Table caption="Cohort counts by reporting year" numeric={part === "All" ? [1, 2, 3, 4] : [1, 2, 3]}
          headings={part === "All" ? ["Year", "Source rows", "In-scope rows", "Eligible claims", "Disagreements", "Catalog version"]
            : ["Year", "Published rows", "Eligible claims", "Missing provider category", "Catalog version"]}
          rows={[...cohorts].reverse().map((row) => {
            if (part === "Part B" || part === "DME") {
              const group = row.parts[part];
              return [row.year, number(group.visible_lines), number(group.claims),
                group.missing_provider == null ? "Suppressed" : number(group.missing_provider), row.version];
            }
            return [row.year, number(row.rows), number(row.in_scope_rows), number(row.claims), number(row.disagreements), row.version];
          })} />
        <p className="footnote">{part === "All" ? "" : "Missing provider category counts from 1 to 9 are suppressed. "}Catalog version
          is the CMS publication date of the source file.</p>
      </Section>
      <Section title="Selection" meta={`${year === "all" ? `${cohorts.length} reporting years` : `Reporting year ${year}`} · ${part === "All" ? "Part B and DME" : part}`}>
        <dl className="details">
          <div><dt>{part === "All" ? "Source rows" : "Published rows"}</dt><dd>{number(sourceRows)}</dd></div>
          <div><dt>Eligible claim groups</dt><dd>{number(claims)}</dd></div>
          {part === "All" && <div><dt>Disagreements</dt><dd>{number(disagreements)} ({percent(disagreements / claims)})</dd></div>}
          <div><dt>Latest release</dt><dd>{study.cohorts.at(-1)!.year} · {study.cohorts.at(-1)!.version}</dd></div>
        </dl>
        <p className="quiet" style={{ marginTop: 14 }}>A reporting year covers a submission window that ends June 30 of the prior year.
          Claim groups use only the rows published in that release.</p>
      </Section>
    </div>
    <Section title="Observed disagreement rate" meta="Share of eligible claim groups with at least one published disagreement, all parts">
      <Plot title="Observed disagreement rate by CMS reporting year" series={[{
        name: "Eligible published cohort", tone: "accent", marker: 0,
        points: study.cohorts.map(({ year: at, disagreements: found, claims: total }) => [at, found / total]),
        details: study.cohorts.map((row) => `${number(row.disagreements)} of ${number(row.claims)} groups`),
      }]} rangeX={[study.cohorts[0].year - .35, study.cohorts.at(-1)!.year + .35]} rangeY={[0, .4]} yTicks={[0, .1, .2, .3, .4]}
        xTicks={study.cohorts.map((row) => row.year)} xFormat={String} yValue={(v) => percent(v, 1)}
        yTitle="Disagreement rate" xTitle="CMS reporting year" xName="Reporting year" height={240} />
    </Section>
  </>;
}

const H1_THRESHOLDS = { ap: .01, precision: .02 };

export function Models({ study }: { study: Study }) {
  const [year, setYear] = useState(study.models.at(-1)!.year);
  const [budget, setBudget] = useState(5);
  const cohort = study.models.find((row) => row.year === year)!;
  const challenger = study.selection.challenger;
  const champion = study.selection.scoring;
  const primary = year === study.models.at(-1)!.year;
  const lineStyle = (name: string) => name === champion ? { tone: "accent" as const, marker: 0, dash: 0 } : { tone: "ochre" as const, marker: 1, dash: 1 };
  return <>
    <PageHeading title="Discrimination and calibration"
      description="Temporal holdout comparison of the development-selected boosted challenger against the hierarchical shrinkage lookup." />
    <div className="controls">
      <Segmented label="Reporting year" value={year} onChange={(v) => setYear(Number(v))} items={yearOptions(study.models)} />
      <Segmented label="Review capacity" value={budget} onChange={(v) => setBudget(Number(v))} items={capacityOptions} />
    </div>
    <div className="columns" style={{ marginTop: 28 }}>
      <Section title="Precision and recall" meta={`${year} holdout · ${number(cohort.claims)} eligible claims`}>
        <Plot title={`Precision–recall comparison for ${year}`}
          series={[champion, challenger].map((name) => ({ name: label(name), points: cohort.models[name].pr_curve, ...lineStyle(name) }))}
          rangeX={[0, 1]} rangeY={[0, 1]} yTicks={[0, .25, .5, .75, 1]} xTicks={[0, .25, .5, .75, 1]}
          xTitle="Recall" yTitle="Precision" />
      </Section>
      <Section title="Reliability" meta="Mean calibrated risk against the observed rate, by decile">
        <Plot title={`Observed versus predicted disagreement for ${year}`}
          series={[champion, challenger].map((name) => ({ name: label(name), ...lineStyle(name),
            points: cohort.models[name].calibration.map((item) => [item.predicted, item.observed]),
            details: cohort.models[name].calibration.map((item) => `Bin ${item.bin} · ${number(item.claims)} claims`) }))}
          rangeX={[0, .6]} rangeY={[0, .6]} xTicks={[0, .15, .3, .45, .6]} yTicks={[0, .15, .3, .45, .6]} diagonal
          xTitle="Mean calibrated risk" yTitle="Observed disagreement"
          caption="The dashed diagonal marks perfect calibration. Bins below the disclosure thresholds are omitted." />
      </Section>
    </div>
    <Section title="Holdout scorecard" meta={`${number(cohort.claims)} eligible claims · ${number(cohort.findings)} disagreements · capacity metrics at ${budget}%`}>
      <Table caption="Risk model performance" numeric={[1, 2, 3, 4, 5]} highlight={(i) => Object.keys(cohort.models)[i] === champion}
        headings={["Model", "Average precision", "AUROC", "Brier", `Precision at ${budget}%`, `Recall at ${budget}%`]}
        rows={Object.entries(cohort.models).map(([name, row]) => [
          <span className="cell-stack" key={name}><span>{label(name)} {name === champion && <span className="tag">Active</span>}
            {name === challenger && <span className="tag neutral">Challenger</span>}</span></span>,
          number(row.ap, 3), number(row.auroc, 3), number(row.brier, 3),
          percent(row.capacity[budget].precision), percent(row.capacity[budget].recall)])} />
    </Section>
    <Section title="Challenger acceptance" meta={`Frozen H1 rule · ${year} ${primary ? "primary" : "secondary"} holdout · 400 paired bootstrap replicates`}
      actions={<Status value={cohort.comparison.status} />}>
      <div className="columns">
        <IntervalPlot title="Average precision change" estimate={cohort.comparison.average_precision_delta}
          bounds={cohort.comparison.intervals.ap.bounds} format={(value) => number(value, 4)}
          threshold={H1_THRESHOLDS.ap} thresholdText="Lower bound must exceed 0.0100" />
        <IntervalPlot title="Precision change at 5% capacity" estimate={cohort.comparison.precision_at_5_delta}
          bounds={cohort.comparison.intervals.precision_at_5.bounds} format={(value) => points(value, 2)}
          threshold={H1_THRESHOLDS.precision} thresholdText="Lower bound must exceed 2 pp" />
      </div>
      <div style={{ marginTop: 24 }}>
        <Table caption="Observed challenger change and preregistered thresholds" numeric={[1, 2, 3]}
          headings={["Measure", "Observed change", "97.5% paired interval", "Required lower bound"]}
          rows={[
            ["Average precision", number(cohort.comparison.average_precision_delta, 5),
              interval(cohort.comparison.intervals.ap, (v) => number(v, 5)), "Above 0.01"],
            ["Precision at 5% capacity", points(cohort.comparison.precision_at_5_delta),
              interval(cohort.comparison.intervals.precision_at_5, points), "Above 2 pp"],
          ]} />
      </div>
      <p className="quiet" style={{ marginTop: 12 }}>Both lower bounds must clear their thresholds before a challenger can replace the lookup.
        The intervals describe claim-level variation within the released cohort, not national or clustered design uncertainty.</p>
    </Section>
    <NextStep from="models" />
  </>;
}

export function Planner({ study }: { study: Study }) {
  const defaults = { year: study.finance.at(-1)!.year, budget: 5, exploration: "hybrid-10", ...study.finance_primary };
  const [year, setYear] = useState(defaults.year);
  const [budget, setBudget] = useState(defaults.budget);
  const [exploration, setExploration] = useState(defaults.exploration);
  const [exposure, setExposure] = useState(defaults.exposure);
  const [fraction, setFraction] = useState(defaults.relevant_percent);
  const [cost, setCost] = useState(defaults.review_cost_cents);
  const cohort = study.finance.find((row) => row.year === year)!;
  const rows = policiesAt(study, year, budget);
  const reviews = rows[0]?.review_count;
  const chosen = cohort.grid.find((row) => row.budget_percent === budget && row.exposure === exposure &&
    row.relevant_percent === fraction && row.review_cost_cents === cost);
  function reset() {
    setYear(defaults.year); setBudget(defaults.budget); setExploration(defaults.exploration);
    setExposure(defaults.exposure); setFraction(defaults.relevant_percent); setCost(defaults.review_cost_cents);
  }
  return <>
    <PageHeading title="Review budget scenarios"
      description="Set a review capacity and an exploration share. Every strategy is compared on the same historical cohort with the same number of reviews." />
    <div className="columns rail">
      <Panel title="Scenario" className="rail-panel"
        action={<button className="button secondary small" type="button" onClick={reset}>
          <RotateCcw size={13} aria-hidden="true" />Reset scenario</button>}>
        <div className="controls stacked">
          <Segmented fill label="Reporting year" value={year} onChange={(v) => setYear(Number(v))} items={yearOptions(study.finance)} />
          <Segmented fill label="Review capacity" value={budget} onChange={(v) => setBudget(Number(v))} items={capacityOptions} />
          <Segmented fill label="Exploration share" value={exploration} onChange={setExploration}
            items={[{ value: "hybrid-5", text: "5%" }, { value: "hybrid-10", text: "10%" }, { value: "hybrid-20", text: "20%" }]} />
          <details className="disclosure">
            <summary>Fictional financial assumptions</summary>
            <div className="controls stacked">
              <Select label="Exposure scenario" value={exposure} onChange={setExposure}
                items={["DME higher", "Part B higher", "Uniform"].map((value) => ({ value, text: value }))} />
              <Segmented fill label="Relevant fraction" value={fraction} onChange={(v) => setFraction(Number(v))}
                items={[15, 35, 60].map((value) => ({ value, text: `${value}%` }))} />
              <Segmented fill label="Cost per review" value={cost} onChange={(v) => setCost(Number(v))}
                items={[1500, 3000, 6000].map((value) => ({ value, text: cents(value).replace(".00", "") }))} />
            </div>
          </details>
        </div>
      </Panel>
      <div>
        <Section title="Strategy comparison" meta={`${year} cohort · ${budget}% capacity · ${number(reviews)} reviews per strategy · ${study.replay.seeds} seeds`}>
          <Frontier rows={rows} highlight={exploration} title={`${year} mean review yield and rate RMSE at ${budget}% capacity`}
            lead={headlineSentence(rows, exploration)} />
          <StrategyList rows={rows} highlight={exploration} />
        </Section>
        <Section title="Fictional financial scenario"
          meta={`${number(cohort.eligible)} eligible claims · ${exposure} · ${fraction}% relevant · ${cents(cost)} per review`}>
          {chosen ? <Table caption="Matched audit budget strategy comparison" numeric={[1, 2, 3, 4, 5, 6]}
            headings={["Strategy", "Reviews", "Findings", "Yield", "Nonfindings per finding", "Plan expected net †", "DME share"]}
            rows={Object.entries(chosen.plans).map(([name, plan]) => [label(name), number(plan.reviews),
              number(plan.findings), percent(plan.yield_rate), number(plan.nonfinding_per_finding, 2),
              cents(plan.expected_scenario_net_cents), percent(plan.review_share.DME)])} />
            : <Empty text="This combination has no measured result." />}
          <p className="footnote">† Fictional scenario value: predicted risk × exposure × relevant fraction, less review cost.
            It is not an actual payment, overpayment or recovery.</p>
          <p className="quiet" style={{ marginTop: 12 }}>The primary 5% scenario also tested a part cap with {number(cohort.primary.constrained.exploratory_reviews)} reviews
            reserved for exploration.</p>
        </Section>
      </div>
    </div>
    <NextStep from="planner" />
  </>;
}

const H3_CRITERIA = {
  hybrid: "RMSE at least 1 pp below greedy’s selected-only rate, yield within 10% of greedy",
  stratified: "RMSE at least 0.5 pp below uniform, coverage between 90% and 98%",
  ipw: "Brier at least 0.005 lower, 95% Monte Carlo interval excluding zero",
};

export function Replay({ study }: { study: Study }) {
  const [year, setYear] = useState(study.replay.timeline.at(-1)!.year);
  const [capacity, setCapacity] = useState(5);
  const [weight, setWeight] = useState("unweighted");
  const [strategy, setStrategy] = useState("hybrid-10");
  const rows = policiesAt(study, year, capacity, weight);
  const selected = rows.find((row) => row.strategy === strategy);
  const designs = ["uniform", "greedy", "hybrid-5", "hybrid-10", "hybrid-20", "stratified"];
  const budgets = [1, 2, 5, 10];
  const { hybrid_vs_greedy: hybrid, stratified_vs_uniform: stratified, ipw_vs_unweighted: ipw } = study.replay.conclusions.components;
  const policyChart: Series[] = designs.flatMap((key) => {
    const observed = study.replay.policies.filter((row) => row.year === year && row.strategy === key && row.weight === weight &&
      row.metrics.yield_rate.mean !== null).sort((a, b) => a.budget_percent - b.budget_percent);
    const reference = key === "greedy" || key === "uniform";
    return observed.length ? [{
      name: label(key), ...styleFor(key),
      emphasis: key === strategy ? "strong" as const : reference ? undefined : "muted" as const,
      points: observed.map((row) => [budgets.indexOf(row.budget_percent), row.metrics.yield_rate.mean!]),
      spread: key === strategy ? observed.map(({ metrics }) => {
        const quantiles = metrics.yield_rate.quantiles;
        return quantiles ? [quantiles[0], quantiles[2]] : null;
      }) : undefined,
      label: key === strategy ? label(key) : undefined, labelAt: "above" as const,
    }] : [];
  });
  return <>
    <PageHeading title="Exploration and cohort estimation"
      description={`Historical CERT outcomes with simulated review choices and delayed feedback, repeated over ${study.replay.seeds} seeds per configuration.`} />
    <div className="controls">
      <Segmented label="Reporting year" value={year} onChange={(v) => setYear(Number(v))} items={yearOptions(study.replay.timeline)} />
      <Segmented label="Review capacity" value={capacity} onChange={(v) => setCapacity(Number(v))} items={capacityOptions} />
      <Segmented label="Learning weights" value={weight} onChange={setWeight}
        items={["unweighted", "ipw", "clipped"].map((value) => ({ value, text: label(value) }))} />
      <Select label="Highlighted strategy" value={strategy} onChange={setStrategy}
        items={designs.map((value) => ({ value, text: label(value) }))} />
    </div>
    <Section title="Mean review yield by capacity" meta={`${year} · ${label(weight)} learning · whiskers show seed percentiles for ${label(strategy).toLowerCase()}`}>
      <Plot title={`Replay mean yield across the four capacities for ${year}`} series={policyChart}
        rangeX={[-.2, 3.2]} rangeY={[0, .5]} xTicks={[0, 1, 2, 3]} yTicks={[0, .1, .2, .3, .4, .5]}
        xFormat={(i) => `${budgets[Math.round(i)]}%`} xTitle="Share of eligible claims reviewed" yTitle="Mean review yield"
        xName="Capacity" yName="Mean yield"
        spreadLabel="2.5th to 97.5th seed percentile" height={300} />
    </Section>
    <Section title={`Yield and estimation at ${capacity}% capacity`} meta={`${number(rows[0]?.review_count)} reviews per seed · precomputed across ${study.replay.seeds} seeds`}>
      <Table caption="Replay strategy comparison" numeric={[1, 2, 3, 4, 5, 6]} highlight={(i) => rows[i]?.strategy === strategy}
        headings={["Strategy", "Reviews per seed", "Mean yield", "Selected-only RMSE", "Design-aware RMSE", "95% interval coverage", "Brier"]}
        rows={rows.map((row) => [label(row.strategy), number(row.review_count), percent(row.metrics.yield_rate.mean),
          points(row.metrics.naive_rmse), points(row.metrics.ht_rmse), percent(row.metrics.coverage.mean),
          number(row.metrics.brier.mean, 4)])} />
      <p className="footnote">Greedy leaves some claims with zero inclusion probability, so it has no design-aware estimate.
        Its selected-only rate describes only the reviewed claims.</p>
    </Section>
    <div className="columns">
      <Section title="Strategy diagnostics" meta={`${label(strategy)} · means with Monte Carlo standard errors`}>
        {selected ? <Table caption="Selected strategy simulation diagnostics" numeric={[1, 2]}
          headings={["Metric", "Mean", "Monte Carlo SE"]}
          rows={[
            ["Cumulative findings", number(selected.metrics.cumulative_findings.mean, 1), number(selected.metrics.cumulative_findings.mcse, 2)],
            ["Effective sample size", number(selected.metrics.ess.mean, 1), number(selected.metrics.ess.mcse, 2)],
            ["Design-aware bias", points(selected.metrics.ht_bias.mean), points(selected.metrics.ht_bias.mcse)],
            ["Expected calibration error", points(selected.metrics.ece.mean), points(selected.metrics.ece.mcse)],
          ]} /> : <Empty text="This weighting and strategy combination has no measured result." />}
      </Section>
      <Section title="Outcome availability" meta="Simulated decision date to the CMS catalog date of the outcome file">
        <DelayTimeline title="Months from simulated decision to outcome availability"
          rows={study.replay.timeline.map((row) => ({ year: row.year, decision: row.decision, available: row.label_available }))} />
        <details className="chart-data">
          <summary>Dates</summary>
          <Table caption="Simulated decision and outcome availability dates" headings={["Year", "Decision", "Outcomes available"]}
            rows={study.replay.timeline.map((row) => [row.year, row.decision, row.label_available])} />
        </details>
      </Section>
    </div>
    <Section title="H3 component criteria" meta={`Frozen rule · ${study.replay.timeline.at(-1)!.year} · 5% capacity`}
      actions={<Status value={study.replay.conclusions.status} />}>
      <Table caption="H3 component results against frozen criteria" numeric={[2]} wrap={[1]}
        headings={["Component", "Criterion", "Measured", "Result"]}
        rows={[
          ["10% exploration vs greedy", H3_CRITERIA.hybrid,
            `RMSE improvement ${points(hybrid.rmse_improvement)} · ${percent(hybrid.yield_ratio)} of greedy yield`, <Status key="h" value={hybrid.supported ? "supported" : "not supported"} />],
          ["Score stratification vs uniform", H3_CRITERIA.stratified,
            `RMSE improvement ${points(stratified.rmse_improvement)} · ${percent(stratified.coverage)} coverage`, <Status key="s" value={stratified.supported ? "supported" : "not supported"} />],
          ["Inverse weighting vs unweighted", H3_CRITERIA.ipw,
            `Brier improvement ${number(ipw.brier_improvement.mean, 4)} (${number(ipw.mc_interval[0], 4)} to ${number(ipw.mc_interval[1], 4)})`,
            <Status key="i" value={ipw.supported ? "supported" : "not supported"} />],
        ]} />
      <p className="quiet" style={{ marginTop: 12 }}>The components use different estimators and sampling designs, so the hybrid result does not show that
        exploration alone caused the lower error. Design-aware intervals measure repeated selection within a fixed released cohort.</p>
    </Section>
    <NextStep from="replay" />
  </>;
}

const H2_THRESHOLDS = { gain: .05, burden: .5 };

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
  const currencyAxis = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", notation: "compact", maximumFractionDigits: 1 });
  const inputs = [
    { title: "Predicted disagreement", unit: "%", value: risk, setter: setRisk, max: 100 },
    { title: "Fictional exposure", unit: "cents", value: exposure, setter: setExposure, max: 10000000 },
    { title: "Relevant fraction", unit: "%", value: fraction, setter: setFraction, max: 100 },
    { title: "Review cost", unit: "cents", value: cost, setter: setCost, max: 10000000 },
  ];
  return <>
    <PageHeading title="Fictional value sensitivity"
      description="Expected scenario net for reviewing one claim. Every amount is a fictional assumption; CERT does not publish the payments needed to measure savings." />
    <div className="columns wide-right">
      <Panel title="Scenario calculator" meta="Calculated in your browser with whole-cent arithmetic">
        <div className="calculator">{inputs.map((item) => <label key={item.title} className="control">
          <span>{item.title}<span className="sr-only"> ({item.unit})</span><small aria-hidden="true">{item.unit}</small></span>
          <input type="number" min={0} max={item.max} step="1" value={Number.isNaN(item.value) ? "" : item.value}
            onChange={(event) => item.setter(event.target.valueAsNumber)} />
          {item.unit === "cents" && <span className="input-hint">{Number.isSafeInteger(item.value) ? cents(item.value) : "Whole cents only"}</span>}
        </label>)}</div>
        <label className="control" style={{ marginTop: 16 }}>
          <span>Adjust predicted disagreement<small aria-hidden="true">{Number.isFinite(risk) ? `${risk}%` : "Not set"}</small></span>
          <input className="range" type="range" min={0} max={100} value={Number.isFinite(risk) ? risk : 0}
            aria-valuetext={`${Number.isFinite(risk) ? risk : 0}%`} onChange={(event) => setRisk(event.target.valueAsNumber)} />
        </label>
        <div className="result"><span>Expected scenario net per review</span>
          <output aria-live="polite">{cents(net)}</output>
          <small>Risk × exposure × relevant fraction, less review cost</small>
        </div>
      </Panel>
      <Section title="Net value by predicted disagreement" meta="Fictional inputs · US dollars per review">
        {net === null ? <Empty text="Enter whole numbers within the input limits to see the sensitivity." />
          : <Plot title="Fictional net value as predicted disagreement changes"
            series={[{ name: "Scenario net", tone: "accent", marker: 0, points: sensitivity, legend: false },
              { name: "Current inputs", tone: "ochre", marker: 2, points: [[risk / 100, net]], line: false, emphasis: "strong",
                label: cents(net), labelAt: "above" }]}
            rangeX={[0, 1]} rangeY={[lower, upper]} yTicks={ticks} referenceY={0} xTicks={[0, .2, .4, .6, .8, 1]}
            yFormat={(value) => currencyAxis.format(value / 100)} yValue={cents}
            xTitle="Predicted disagreement" yTitle="Scenario net per review" legend={false} />}
      </Section>
    </div>
    <Section title="Primary study comparison" meta={`H2 · ${result.year} · 5% capacity · value ranking minus risk ranking · 97.5% paired bootstrap intervals`}
      actions={<Status value={result.primary.status} />}>
      <div className="columns">
        <IntervalPlot title="Scenario-weighted findings" estimate={result.primary.relative_weighted_gain}
          bounds={result.primary.intervals.weighted_gain.bounds} format={(value) => percent(value, 2)}
          threshold={H2_THRESHOLDS.gain} thresholdText="Lower bound must exceed 5%" />
        <IntervalPlot title="Nonfinding reviews per finding" estimate={result.primary.burden_delta}
          bounds={result.primary.intervals.burden_delta.bounds} format={(value) => number(value, 2)}
          threshold={H2_THRESHOLDS.burden} thresholdText="Upper bound must stay below 0.50" />
      </div>
      <div style={{ marginTop: 24 }}>
        <Table caption="Financial comparison with paired intervals" numeric={[1, 2]} headings={["Measure", "Difference", "97.5% interval", "Criterion"]}
          rows={[
            ["Scenario-weighted findings", percent(result.primary.relative_weighted_gain, 2),
              interval(result.primary.intervals.weighted_gain, (v) => percent(v, 2)), "Lower bound above 5%"],
            ["Nonfinding reviews per finding", number(result.primary.burden_delta, 2),
              interval(result.primary.intervals.burden_delta, (v) => number(v, 2)), "Upper bound below 0.5"],
          ]} />
      </div>
    </Section>
    <Note>Scenario amounts are stored as whole cents and rounded half away from zero. They do not measure claim dollars,
      reimbursement, savings or return on investment.</Note>
  </>;
}

export function Validation({ study }: { study: Study }) {
  const { validation } = study;
  const thresholdNames: Record<string, string> = {
    score_psi: "Score PSI", category_js_distance: "Provider category distance",
    missing_rate_delta: "Missing rate change", unknown_rate_delta: "Unknown category change",
  };
  return <>
    <PageHeading title="Validation and monitoring"
      description="Registry status, drift thresholds and realized holdout performance for the active research scorecard." />
    <div className="columns">
      <Section title="Research registry" actions={<Status value={validation.status} />}>
        <dl className="details">
          <div><dt>Active version</dt><dd className="digest">{validation.active}</dd></div>
          <div><dt>Operational promotion</dt><dd><Status value={validation.promotion} /></dd></div>
          <div><dt>Fit</dt><dd>{number(study.split.train)} training and {number(study.split.calibration)} calibration groups</dd></div>
          <div><dt>Challenger</dt><dd>{label(study.selection.challenger)}, selected on {number(study.split.development)} development groups</dd></div>
        </dl>
        <p className="quiet" style={{ marginTop: 14 }}>A challenger needs both practical H1 gains, holdout Brier no more than 0.005 worse than the lookup,
          and no structural, artifact or service failure.</p>
      </Section>
      <Section title="Drift against thresholds" meta="Thresholds set on calibration and development cohorts">
        {Object.entries(validation.thresholds).map(([key, limit]) => <div className="drift-metric" key={key}>
          <h3>{thresholdNames[key] ?? label(key)}<small>Threshold {number(limit, 3)}</small></h3>
          <div className="bars">{validation.cohorts.map((row) =>
            <ThresholdBar key={row.year} label={String(row.year)} value={row.drift[key] ?? 0} limit={limit}
              format={(v) => number(v, 3)} />)}</div>
        </div>)}
      </Section>
    </div>
    <Section title="Holdout monitoring" meta="Covariate alerts are available at scoring time; outcome measures only after CMS releases labels">
      <Table caption="Annual feature shift and realized model performance" numeric={[1, 2, 4, 5, 6]}
        headings={["Year", "Score PSI", "Provider distance", "Covariate alerts", "Labelled claims", "Observed rate", "Brier"]}
        rows={validation.cohorts.map((row) => [row.year, number(row.drift.score_psi, 3),
          number(row.drift.category_js_distance, 3), row.covariate_alerts.map(label).join(", ") || "None",
          number(row.labelled_claims), percent(row.observed_rate), number(row.brier, 3)])} />
    </Section>
    <Note>This validation was carried out by the developer. It is not independent model validation, and no provider or demographic fairness
      conclusion can be drawn from the released data.</Note>
    <NextStep from="validation" />
  </>;
}

const pipeline = [
  { title: "Acquire", text: "CMS CERT CSV files with SHA-256 sidecars and catalog dates" },
  { title: "Build", text: "DuckDB Parquet features, with outcomes stored separately" },
  { title: "Evaluate", text: "Frozen evaluator, calibrated scorecards, replay and estimators" },
  { title: "Serve", text: "Integrity-checked JSON models on a loopback FastAPI service" },
  { title: "Publish", text: "Reviewed aggregate JSON rendered by this static build" },
];

export function Methods({ study }: { study: Study }) {
  return <>
    <PageHeading title="Methods and provenance"
      description="Research design, frozen settings and digests of the result files behind this workspace." />
    <div className="columns">
      <Section title="Study design" meta={`Protocol ${study.protocol}`}>
        <dl className="details">
          <div><dt>Decision unit</dt><dd>One reporting-year control-number group in the published Part B or DME sample</dd></div>
          <div><dt>Outcome</dt><dd>At least one published disagreement, among groups whose rows all have recognized outcomes</dd></div>
          <div><dt>Splits</dt><dd>Fit 2018–2021, calibrate 2022, select 2023, report 2025 with 2024 corroboration</dd></div>
          <div><dt>Uncertainty</dt><dd>Paired claim bootstrap for H1 and H2; conditional finite-population inference for H3</dd></div>
          <div><dt>Protocol commit</dt><dd className="digest">{study.freeze_commit}</dd></div>
        </dl>
      </Section>
      <Section title="References">
        <ul className="references">
          <li><a href="https://data.cms.gov/provider-compliance/fee-for-service-error-rate-improper-payment/medicare-fee-for-service-comprehensive-error-rate-testing">CMS CERT catalog and documentation</a>
            <span className="quiet">Source data, field definitions and release dates</span></li>
          <li><a href="https://ojs.aaai.org/index.php/AAAI/article/view/25637">Henderson et al., AAAI 2023</a>
            <span className="quiet">Audit selection with population estimation</span></li>
          <li><a href="https://arxiv.org/abs/2509.18739">Revelas, Boldea and Werker, 2025</a>
            <span className="quiet">Consistency of investigation selection strategies</span></li>
        </ul>
      </Section>
    </div>
    <Section title="Pipeline">
      <ol className="pipeline">
        {pipeline.map((stage) => <li key={stage.title}><strong>{stage.title}</strong><span>{stage.text}</span></li>)}
      </ol>
    </Section>
    <Section title="Result ledger" meta="SHA-256 of each source result file used to build the aggregate">
      <Table caption="Run IDs and exact source digests" headings={["Run", "SHA-256"]} rows={study.ledger.map((item) =>
        [item.run, <code key={item.run} className="digest">{item.sha256}</code>])} />
    </Section>
    <Note>Study values are read from the reviewed aggregate when the page loads. Extension results are bundled from their
      registered evidence files. The static build makes no backend requests and contains no claim-level records.</Note>
  </>;
}
