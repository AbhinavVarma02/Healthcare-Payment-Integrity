import { useState } from "react";
import { Card, Empty, Note, PageHeading, Select, Table } from "./components";
import { localRequest } from "./contracts";
import type { Study } from "./contracts";
import { cents, label, number, percent, points, scenarioNet } from "./numbers";

const examples = [
  { tool: "policies", question: "Compare review policies" },
  { tool: "validation", question: "Retrieve model validation" },
  { tool: "budget", question: "Simulate a fictional budget" },
  { tool: "report", question: "Generate the research report" },
] as const;
type Tool = typeof examples[number]["tool"];
type Policy = { strategy: string; reviews: number; yield: number | null; cohort_rmse: number | null; selected_only_rmse: number | null };
type Answer = {
  status: string;
  data?: { policies?: Policy[]; active?: string; promotion?: string; net_cents?: number; eligible_groups?: number; cohorts?: number };
  evidence?: { run?: string; formula?: string; aggregate_sha256?: string };
};
const budgetArgs = { part: "DME", risk_bps: 3000, exposure_cents: 25000, relevant_percent: 35, review_cost_cents: 3000 };
const policyNames = ["uniform", "greedy", "hybrid-10"];

function browserAnswer(tool: Tool, study: Study): Answer {
  if (tool === "budget") {
    return { status: "ok", data: { net_cents: scenarioNet(30, 25000, 35, 3000)! }, evidence: { formula: "scenario-net-v1" } };
  }
  if (tool === "policies") {
    return { status: "ok", data: { policies: study.replay.policies.filter((row) =>
      row.year === 2025 && row.budget_percent === 5 && row.weight === "unweighted").map((row) => ({
      strategy: row.strategy, reviews: row.review_count, yield: row.metrics.yield_rate.mean,
      cohort_rmse: row.metrics.ht_rmse, selected_only_rmse: row.metrics.naive_rmse,
    })) }, evidence: { run: "H3-sequential" } };
  }
  if (tool === "validation") {
    return { status: "ok", data: { active: study.validation.active, promotion: study.validation.promotion },
      evidence: { run: "Governance" } };
  }
  return { status: "ok", data: { eligible_groups: study.cohorts.reduce((total, row) => total + row.claims, 0),
    cohorts: study.cohorts.length } };
}

export function Analyst({ study }: { study: Study }) {
  const [tool, setTool] = useState<Tool>("policies");
  const [answer, setAnswer] = useState<Answer>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function run(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    setBusy(true);
    setAnswer(undefined);
    try {
      if (import.meta.env.DEV) {
        const question = examples.find((item) => item.tool === tool)!.question;
        setAnswer(await localRequest<Answer>("/v1/analyst/question?role=analyst", {
          question, mode: "deterministic", call: tool === "budget" ? { tool, ...budgetArgs } : { tool },
        }));
      } else {
        setAnswer(browserAnswer(tool, study));
      }
    } catch (failure) {
      setError(failure instanceof TypeError ? "Start the local API and retry." : "The requested evidence could not be loaded.");
    } finally {
      setBusy(false);
    }
  }
  const data = answer?.data;
  return <>
    <PageHeading eyebrow="Evidence tools" title="Research analyst"
      description="Run a structured query over reviewed evidence or calculate a fictional budget scenario." />
    <div className="overview-grid">
      <Card title="Evidence query" subtitle={import.meta.env.DEV ? "Deterministic · Local API" : "Deterministic · Browser and reviewed aggregates"}>
        <form onSubmit={(event) => void run(event)} className="filters">
          <Select label="Query" value={tool} items={examples.map((item) => ({ value: item.tool, text: item.question }))}
            onChange={(value) => { setTool(value as Tool); setAnswer(undefined); setError(""); }} />
          <button className="button" disabled={busy}>Run query</button>
        </form>
        {tool === "budget" && <p className="quiet">Example assumptions are 30% predicted disagreement, $250 exposure, 35% relevant fraction and $30 review cost.</p>}
        <div aria-live="polite">
          {busy && <p>Retrieving evidence…</p>}
          {error && <p className="error" role="alert">{error}</p>}
          {answer?.status !== "ok" && answer && <Empty text="No verified answer is available for this query." />}
          {data?.policies && <Table caption="Frozen 2025 replay at 5% capacity"
            headings={["Strategy", "Reviews", "Mean yield", "Rate RMSE", "Estimator"]}
            rows={data.policies.filter((row) => policyNames.includes(row.strategy)).map((row) => [
              label(row.strategy), number(row.reviews), percent(row.yield, 2), points(row.cohort_rmse ?? row.selected_only_rmse),
              row.cohort_rmse == null ? "Selected-only" : "Design-aware",
            ])} />}
          {data?.active && <dl className="details">
            <div><dt>Active research model</dt><dd>{data.active}</dd></div>
            <div><dt>Operational promotion</dt><dd>{data.promotion}</dd></div>
          </dl>}
          {data?.net_cents !== undefined && <div className="result-block">
            <span>Fictional expected net per review</span><strong>{cents(data.net_cents)}</strong>
          </div>}
          {data?.eligible_groups !== undefined && <p>{number(data.eligible_groups)} eligible claim groups across {data.cohorts} reporting years.</p>}
          {answer?.status === "ok" && <p className="quiet">
            {answer.evidence?.formula ? `Formula ${answer.evidence.formula}` :
              <a href="#/methods">{answer.evidence?.run ? `Source · ${answer.evidence.run}` : "Study evidence ledger"}</a>}
          </p>}
        </div>
      </Card>
      <Card title="Evidence scope" subtitle="CMS public release cohort">
        <p>Replay estimates apply to the eligible released claim groups. Financial scenarios use fictional assumptions. The study has no actual recovery amounts.</p>
        <a className="text-action" href="#/methods">See the protocol and run fingerprints</a>
      </Card>
    </div>
    <Note>Optional local language-model selection missed its reliability gate. The workspace uses deterministic queries.</Note>
  </>;
}
