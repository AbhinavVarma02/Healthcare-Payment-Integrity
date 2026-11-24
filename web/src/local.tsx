import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Card, Note, PageHeading, Select, Status, Table } from "./components";
import { localRequest } from "./contracts";
import type { Claim, Job, LocalPlan, Part, Score } from "./contracts";
import { cents, number, percent } from "./numbers";

const demoClaims: Claim[] = [
  { part: "Part B", provider_type: "Clinical Laboratory (Billing Independently)", visible_lines: 3, provider_types: 1 },
  { part: "DME", provider_type: "Pharmacy", visible_lines: 1, provider_types: 1 },
  { part: "DME", provider_type: "Medical Supply Company with Respiratory Therapist", visible_lines: 2, provider_types: 1 },
  { part: "Part B", provider_type: "Family Practice", visible_lines: 2, provider_types: 1 },
];

const isRunning = (status: string) => status === "running" || status === "queued";
const errorMessage = (failure: unknown) => failure instanceof TypeError
  ? "The local API could not be reached at 127.0.0.1:8000."
  : failure instanceof Error ? failure.message : "The local workflow failed.";

export function LocalWorkflows() {
  const [readiness, setReadiness] = useState("Checking");
  const [claim, setClaim] = useState(demoClaims[0]);
  const [score, setScore] = useState<Score>();
  const [plan, setPlan] = useState<LocalPlan>();
  const [job, setJob] = useState<Job>();
  const [budget, setBudget] = useState(2);
  const [strategy, setStrategy] = useState("risk");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  const check = () => localRequest<{ status: string }>("/ready").then(
    (response) => setReadiness(response.status), () => setReadiness("Unavailable"));
  useEffect(() => { void check(); }, []);

  useEffect(() => {
    if (!job || !isRunning(job.status)) return;
    let stopped = false;
    const timer = window.setTimeout(() => {
      localRequest<Job>(`/v1/runs/${job.id}`).then(
        (next) => { if (!stopped) setJob(next); },
        (failure) => { if (!stopped) setError(errorMessage(failure)); },
      );
    }, 750);
    return () => { stopped = true; window.clearTimeout(timer); };
  }, [job]);

  async function execute<T>(key: string, path: string, data: unknown, onSuccess: (value: T) => void) {
    setBusy(key);
    setError("");
    try {
      onSuccess(await localRequest<T>(path, data));
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy("");
    }
  }

  function scoreClaim(event: FormEvent) {
    event.preventDefault();
    void execute<Score>("score", "/v1/score", claim, setScore);
  }

  return <>
    <PageHeading eyebrow="Local inference" title="Score and plan locally"
      description="Send fictional claim features to the loopback research API and run a bounded replay preview."
      aside={<button className="button secondary" onClick={() => void check()}>Check API</button>} />
    <Note>Local API status is {readiness}. Use fictional inputs without claim or provider identifiers.</Note>
    {error && <div className="error" role="alert">{error}</div>}
    <div className="two-columns">
      <Card title="Score a fictional claim" subtitle="Live local model inference">
        <form onSubmit={scoreClaim} className="calculator">
          <Select label="Claim part" value={claim.part} onChange={(v) => setClaim({ ...claim, part: v as Part })}
            items={[{ value: "Part B", text: "Part B" }, { value: "DME", text: "DME" }]} />
          <label className="control"><span>Provider category</span>
            <input required maxLength={160} value={claim.provider_type}
              onChange={(e) => setClaim({ ...claim, provider_type: e.target.value })} /></label>
          <label className="control"><span>Visible lines</span>
            <input type="number" required min={1} max={250} value={claim.visible_lines || ""}
              onChange={(e) => setClaim({ ...claim, visible_lines: e.target.valueAsNumber })} /></label>
          <label className="control"><span>Provider categories</span>
            <input type="number" required min={1} max={50} value={claim.provider_types || ""}
              onChange={(e) => setClaim({ ...claim, provider_types: e.target.valueAsNumber })} /></label>
          <button className="button" disabled={!!busy}>{busy === "score" ? "Scoring…" : "Score claim"}</button>
        </form>
        {score && <div className="result-block" role="status">
          <span>Calibrated disagreement risk</span><strong>{percent(score.calibrated_risk)}</strong>
          <p>{score.explanation.method} · {score.input_support}</p><small>{score.model}</small>
        </div>}
      </Card>
      <Card title="Plan four fictional claims" subtitle="Live local scoring and scenario planning">
        <div className="filters">
          <Select label="Review slots" value={budget} onChange={(v) => setBudget(+v)}
            items={[1, 2, 3, 4].map((n) => ({ value: n, text: String(n) }))} />
          <Select label="Selection strategy" value={strategy} onChange={setStrategy}
            items={[{ value: "risk", text: "Risk only" }, { value: "value", text: "Scenario value" },
              { value: "uniform", text: "Uniform random" }]} />
        </div>
        <Table caption="Fictional claim candidates" headings={["Candidate", "Part", "Visible lines"]}
          rows={demoClaims.map((item, i) => [`Example ${i + 1}`, item.part, item.visible_lines])} />
        <button className="button" disabled={!!busy} onClick={() => void execute<LocalPlan>(
          "plan", "/v1/audit-plan", { claims: demoClaims, capacity: budget, strategy }, setPlan,
        )}>{busy === "plan" ? "Planning…" : "Build plan"}</button>
        {plan && <div className="result-block" role="status">
          <span>Selected examples</span>
          <strong>{plan.selected_input_positions.map((i) => i + 1).join(", ") || "None"}</strong>
          <p>{number(plan.summary.minutes)} assumed minutes · {cents(plan.summary.expected_scenario_net_cents)} expected scenario net</p>
        </div>}
      </Card>
    </div>
    <Card title="Replay preview" subtitle="One seed using the frozen local cohort files">
      <div className="actions">
        <button className="button" disabled={!!busy || (!!job && isRunning(job.status))}
          onClick={() => void execute<Job>("job", "/v1/replay", { seeds: 1 }, setJob)}>Start replay</button>
        {job && isRunning(job.status) && <button className="button secondary" disabled={!!busy}
          onClick={() => void execute<Job>("job", `/v1/runs/${job.id}/cancel`, {}, setJob)}>Cancel replay</button>}
        {job && ["interrupted", "cancelled", "failed"].includes(job.status) &&
          <button className="button secondary" disabled={!!busy}
            onClick={() => void execute<Job>("job", `/v1/runs/${job.id}/resume`, {}, setJob)}>Resume replay</button>}
      </div>
      {job && <p className="job-state" role="status"><Status value={job.status} /> {job.seeds_completed}/{job.seeds_requested} seeds completed</p>}
    </Card>
  </>;
}
