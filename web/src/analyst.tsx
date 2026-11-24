import { useState } from "react";
import { ArrowRight } from "lucide-react";
import { Empty, Note, PageHeading, Panel, Section, Table } from "./components";
import { localRequest } from "./contracts";
import type { Study } from "./contracts";
import { cents, label, number, percent, points, scenarioNet } from "./numbers";

const examples = [
  { tool: "policies", question: "Compare review policies", detail: "2025 replay at 5% capacity, with estimator type" },
  { tool: "validation", question: "Retrieve model validation", detail: "Active research scorecard and promotion status" },
  { tool: "budget", question: "Simulate a fictional budget", detail: "Scenario net for one DME review" },
  { tool: "report", question: "Generate the research report", detail: "Study coverage across all releases" },
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
    cohorts: study.cohorts.length }, evidence: { run: "Coverage" } };
}

export function Analyst({ study }: { study: Study }) {
  const [tool, setTool] = useState<Tool>("policies");
  const [answer, setAnswer] = useState<Answer>();
  const [asked, setAsked] = useState<Tool>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function run(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    setBusy(true);
    setAnswer(undefined);
    setAsked(tool);
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
      setError(failure instanceof TypeError ? "The local API did not respond. Start it and run the query again."
        : "The requested evidence could not be loaded.");
    } finally {
      setBusy(false);
    }
  }
  const data = answer?.data;
  const question = examples.find((item) => item.tool === asked);
  return <>
    <PageHeading title="Research analyst"
      description="Structured questions answered by deterministic tools over the reviewed evidence. Answers cite their source run and never estimate savings." />
    <div className="columns wide-right">
      <Panel title="Query" action={<span className="tag">Deterministic</span>}
        meta={`${import.meta.env.DEV ? "Answered by the local API" : "Answered in your browser from the reviewed aggregate"}. Language model disabled.`}>
        <form onSubmit={(event) => void run(event)} className="stack">
          <fieldset className="choices">
            <legend>Question</legend>
            {examples.map((item) => <label className="choice" key={item.tool}>
              <input type="radio" name="analyst-query" value={item.tool} checked={tool === item.tool}
                onChange={() => { setTool(item.tool); setError(""); }} />
              <span className="choice-body"><strong>{item.question}</strong><small>{item.detail}</small></span>
            </label>)}
          </fieldset>
          {tool === "budget" && <p className="quiet">Assumes 30% predicted disagreement, $250 exposure, 35% relevant fraction and a $30 review cost.</p>}
          <button className="button" type="submit" disabled={busy}>Run query<ArrowRight size={14} aria-hidden="true" /></button>
        </form>
      </Panel>
      <Section title="Answer" meta={question ? question.question : "Choose a question and run it"}>
        <div aria-live="polite">
          {busy && <p className="quiet">Retrieving evidence</p>}
          {error && <p className="error" role="alert">{error}</p>}
          {!busy && !error && !answer && <Empty text="Run a query to see the answer and its source." />}
          {answer?.status !== "ok" && answer && <Empty text="No verified answer is available for this question." />}
          {data?.policies && <Table caption="Frozen 2025 replay at 5% capacity" numeric={[1, 2, 3]}
            headings={["Strategy", "Reviews", "Mean yield", "Rate RMSE", "Estimator"]}
            rows={data.policies.filter((row) => policyNames.includes(row.strategy)).map((row) => [
              label(row.strategy), number(row.reviews), percent(row.yield, 2), points(row.cohort_rmse ?? row.selected_only_rmse),
              row.cohort_rmse == null ? "Selected-only" : "Design-aware",
            ])} />}
          {data?.active && <dl className="details">
            <div><dt>Active research model</dt><dd className="digest">{data.active}</dd></div>
            <div><dt>Operational promotion</dt><dd>{data.promotion}</dd></div>
          </dl>}
          {data?.net_cents !== undefined && <div className="result" style={{ marginTop: 0, paddingTop: 0, borderTop: 0 }}>
            <span>Fictional expected net per review</span><strong>{cents(data.net_cents)}</strong>
            <small>Risk × exposure × relevant fraction, less review cost</small>
          </div>}
          {data?.eligible_groups !== undefined && <p className="prose">{number(data.eligible_groups)} eligible claim groups across {data.cohorts} CERT
            reporting years, each with reconciled source counts.</p>}
          {answer?.status === "ok" && <p className="quiet" style={{ marginTop: 14 }}>
            {answer.evidence?.formula ? `Calculated with formula ${answer.evidence.formula}` :
              <>Source <a href="#/methods">{answer.evidence?.run ?? "study evidence ledger"}</a></>}
          </p>}
        </div>
      </Section>
    </div>
    <Note>Replay figures apply to eligible published claims. Budget answers use fictional assumptions. The optional local language model
      failed its reliability gate, so it is not used.</Note>
  </>;
}
