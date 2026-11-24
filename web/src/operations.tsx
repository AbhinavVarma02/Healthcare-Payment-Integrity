import { useEffect, useState } from "react";
import { Card, Empty, Note, PageHeading, Select, Status, Table } from "./components";
import { localRequest } from "./contracts";
import { number, percent } from "./numbers";

const operations = "/v1/operations";
const sample = [
  { part: "Part B", provider_type: "Family Practice", visible_lines: 2, provider_types: 1 },
  { part: "DME", provider_type: "Pharmacy", visible_lines: 1, provider_types: 1 },
  { part: "DME", provider_type: "Medical Supply Company", visible_lines: 3, provider_types: 1 },
  { part: "Part B", provider_type: "Fictional Practice", visible_lines: 4, provider_types: 1 },
];
type Finding = { version: number; finding: string; available: number; note: string };
type Case = { case_id: string; state: string; reviewer: string | null; finding: Finding | null };
type Overview = {
  tick: number; status: string; revealed_cases: number; event_latency: { p95_ms: number | null };
  unknown_category_rate: number | null; shadow_failures: number; states: Record<string, number>;
  alert: string | null; recent_runs: { run_id: string }[];
  recent_rejections: { kind: string; code: string; tick: number; retryable: number }[];
  recent_dme_share_delta: number | null;
  paired_shadow: { cases: number; brier_delta: number | null };
};
type Receipt = {
  digest: string; intake_event_digest: string; design_status: string; outcomes: Finding[];
  receipt: { case_id: string; run_id: string; input_sha256: string; snapshot_sha256: string;
    score: { calibrated_risk: number; model: string; explanation: { method: string };
      shadow?: { status: string; model: string; risk?: number } };
    decision: { reason: string; probability: { numerator: number; denominator: number; status: string } } };
};
type Trace = { events: { seq: number; kind: string; tick: number; digest: string }[] };
type Candidate = { model: string; artifact_sha256?: string; report_sha256?: string;
  report?: { mode: string; gates: Record<string, boolean>; split: { train: number; calibration: number; validation: number } } };
type Lifecycle = { generation: number; active: string | null; shadow: string | null; candidates: Candidate[] };
type AssistantReply = { status: string; mode: string; data?: { risk?: number; eligible_groups?: number; net_cents?: number };
  evidence?: { model?: string; receipt?: string; aggregate_sha256?: string; formula?: string } };

const options = (values: string[]) => values.map((value) => ({ value, text: value.replaceAll("-", " ") }));
const textError = (error: unknown) => error instanceof TypeError
  ? "The loopback API is unavailable. Start it locally and retry."
  : error instanceof Error ? error.message : "The operation could not be completed.";

export function Operations() {
  const [overview, setOverview] = useState<Overview>();
  const [run, setRun] = useState("");
  const [cases, setCases] = useState<Case[]>([]);
  const [selected, setSelected] = useState("");
  const [receipt, setReceipt] = useState<Receipt>();
  const [trace, setTrace] = useState<Trace>();
  const [lifecycle, setLifecycle] = useState<Lifecycle>();
  const [assistant, setAssistant] = useState<AssistantReply>();
  const [capacity, setCapacity] = useState(2);
  const [strategy, setStrategy] = useState("hybrid-10");
  const [finding, setFinding] = useState("agree");
  const [reviewer, setReviewer] = useState("reviewer-a");
  const [note, setNote] = useState("documentation");
  const [replacement, setReplacement] = useState("");
  const [trainingMode, setTrainingMode] = useState("recalibrate");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const current = cases.find((item) => item.case_id === selected);
  const tick = overview?.tick ?? 0;

  async function refresh(nextRun?: string, caseId = "") {
    const [summary, models] = await Promise.all([
      localRequest<Overview>(`${operations}/overview`),
      localRequest<Lifecycle>(`${operations}/lifecycle`),
    ]);
    const active = nextRun ?? summary.recent_runs[0]?.run_id ?? "";
    setOverview(summary);
    setLifecycle(models);
    setRun(active);
    if (!active) return;
    const [queue, events] = await Promise.all([
      localRequest<{ cases: Case[] }>(`${operations}/runs/${active}/cases`),
      localRequest<Trace>(`${operations}/runs/${active}/trace`),
    ]);
    setCases(queue.cases);
    setTrace(events);
    const focus = queue.cases.find((item) => item.case_id === caseId) ??
      queue.cases.find((item) => item.state !== "unselected") ?? queue.cases[0];
    if (focus) {
      setSelected(focus.case_id);
      setReceipt(await localRequest<Receipt>(`${operations}/receipts/${focus.case_id}`));
    }
  }

  useEffect(() => {
    void refresh().catch((failure: unknown) => setError(textError(failure)));
  }, []);

  async function execute(action: () => Promise<void>) {
    setError("");
    setMessage("");
    setBusy(true);
    try {
      await action();
    } catch (failure) {
      setError(textError(failure));
    } finally {
      setBusy(false);
    }
  }

  function event(kind: string, role: string, details: Record<string, unknown>, runId = run) {
    const id = crypto.randomUUID();
    return localRequest(`${operations}/events/${kind}?role=${role}`, {
      event_id: id, idempotency_key: id, run_id: runId, event_tick: tick, ...details,
    });
  }

  function startBatch() {
    void execute(async () => {
      const runId = `review-${crypto.randomUUID().slice(0, 12)}`;
      await event("intake", "analyst", {
        capacity, strategy, seed: 37301, claims: sample.map((item, i) => ({ ...item, case_id: `demo-${runId}-${i + 1}` })),
      }, runId);
      await refresh(runId);
      setMessage("Fictional batch scored and allocated.");
    });
  }

  function review(kind: string, role: string, details: Record<string, unknown> = {}) {
    void execute(async () => {
      await event(kind, role, { case_id: selected, ...details });
      await refresh(run, selected);
      setMessage("Review event recorded.");
    });
  }

  function lifecycleAction(action: string, model: string, candidate?: Candidate) {
    void execute(async () => {
      await localRequest(`${operations}/lifecycle/${action}?role=${action === "shadow" ? "operator" : "supervisor"}`, {
        generation: lifecycle?.generation, model, artifact_sha256: candidate?.artifact_sha256,
        report_sha256: candidate?.report_sha256,
        reason: action === "shadow" ? "evaluate" : action === "rollback" ? "restore_reference" : "reviewed_evidence",
      });
      await refresh(run, selected);
      setMessage("Synthetic lifecycle updated.");
    });
  }

  return <>
    <PageHeading eyebrow="Local simulation" title="Review operations"
      description="Allocate fictional cases, advance the review clock, and inspect verified decision receipts."
      aside={<button className="button secondary" disabled={busy} onClick={() => void execute(() => refresh(run || undefined, selected))}>Refresh operations</button>} />
    {error && <p className="error" role="alert">{error}</p>}
    {message && <p className="note" role="status">{message}</p>}
    <div className="kpi-grid">
      {[["Simulation tick", tick], ["Queued reviews", overview?.states.queued ?? 0],
        ["Cases with revealed findings", overview?.revealed_cases ?? 0],
        ["Event p95", overview?.event_latency.p95_ms == null ? "No data" : `${number(overview.event_latency.p95_ms, 1)} ms`]]
        .map(([label, value]) => <div className="kpi" key={label}><p className="kpi-label">{label}</p><strong>{value}</strong></div>)}
    </div>
    <Card title="Batch intake" subtitle="Synthetic claims · Analyst controls">
      <div className="filters">
        <Select label="Review capacity" value={capacity} items={[0, 1, 2, 3, 4].map((n) => ({ value: n, text: `${n} of 4` }))}
          onChange={(value) => setCapacity(Number(value))} />
        <Select label="Selection strategy" value={strategy} items={options(["hybrid-10", "uniform", "greedy"])} onChange={setStrategy} />
        <button className="button" onClick={startBatch} disabled={busy || !overview}>Intake sample batch</button>
        <button className="button secondary" disabled={busy || !run} onClick={() => void execute(async () => {
          await event("advance", "operator", { advance_to: tick + 1 });
          await refresh(run, selected);
          setMessage("Simulation clock advanced.");
        })}>Advance clock one tick</button>
      </div>
    </Card>
    <div className="overview-grid">
      <Card title="Review queue" subtitle="Findings appear when their availability tick is reached">
        {overview?.recent_runs.length ? <div className="filters">
          <Select label="Intake run" value={run} items={options(overview.recent_runs.map((item) => item.run_id))}
            onChange={(value) => void execute(() => refresh(value))} />
        </div> : <Empty text="Intake a sample batch to create a queue." />}
        {cases.length > 0 && <Table caption="Synthetic review queue" headings={["Case", "State", "Finding", "Details"]}
          rows={cases.map((row) => [row.case_id, row.state, row.finding?.finding ?? "—",
            <button className={`button ${selected === row.case_id ? "" : "secondary"}`} disabled={busy}
              onClick={() => void execute(async () => {
                setSelected(row.case_id);
                setReplacement("");
                setReceipt(await localRequest<Receipt>(`${operations}/receipts/${row.case_id}`));
              })}>Inspect {row.case_id.split("-").at(-1)}</button>])} />}
        {current && <div className="case-actions">
          <h3>{current.case_id}</h3>
          <div className="filters">
            {current.state === "queued" && <>
              <Select label="Reviewer" value={reviewer} items={options(["reviewer-a", "reviewer-b"])} onChange={setReviewer} />
              <button className="button" disabled={busy} onClick={() => review("assign", "reviewer", { reviewer })}>Assign review</button>
            </>}
            {(current.state === "assigned" || current.finding) && <>
              <Select label="Finding" value={finding} items={options(["agree", "disagree"])} onChange={setFinding} />
              <Select label="Review note" value={note} items={options(["documentation", "coding", "eligibility", "other"])} onChange={setNote} />
              {current.state === "assigned" ? <button className="button" disabled={busy}
                onClick={() => review("submit", "reviewer", { finding, note, available_tick: tick + 1 })}>Submit delayed finding</button>
                : <button className="button secondary" disabled={busy}
                  onClick={() => review("correct", "supervisor", { finding, note, available_tick: tick + 1,
                    replaces: current.finding?.version, reason: "source_revision" })}>Record correction</button>}
              {current.state === "reviewed" && <button className="button secondary" disabled={busy}
                onClick={() => review("close", "reviewer")}>Close</button>}
            </>}
          </div>
          {current.state === "queued" && cases.some((row) => row.state === "unselected") && <div className="filters">
            <Select label="Override replacement" value={replacement}
              items={[{ value: "", text: "Choose a case" }, ...options(cases.filter((row) => row.state === "unselected").map((row) => row.case_id))]}
              onChange={setReplacement} />
            <button className="button secondary" disabled={busy || !replacement}
              onClick={() => review("override", "supervisor", { replacement, reason: "priority_change" })}>Swap queued case</button>
          </div>}
        </div>}
      </Card>
      <Card title="Decision receipt" subtitle="Decision-time evidence and revealed finding versions">
        {receipt ? <>
          <dl className="details">
            <div><dt>Model</dt><dd>{receipt.receipt.score.model}</dd></div>
            <div><dt>Score</dt><dd>{percent(receipt.receipt.score.calibrated_risk, 2)} · {receipt.receipt.score.explanation.method}</dd></div>
            <div><dt>Original selection</dt><dd>{receipt.receipt.decision.reason} · {
              receipt.receipt.decision.probability.numerator}/{receipt.receipt.decision.probability.denominator}</dd></div>
            <div><dt>Design status</dt><dd>{receipt.design_status}</dd></div>
            {receipt.receipt.score.shadow && <div><dt>Shadow</dt><dd>{receipt.receipt.score.shadow.model} · {
              receipt.receipt.score.shadow.risk == null ? receipt.receipt.score.shadow.status : percent(receipt.receipt.score.shadow.risk, 2)}</dd></div>}
            <div><dt>Digest</dt><dd className="digest">{receipt.digest}</dd></div>
          </dl>
          {receipt.outcomes.length ? <Table caption="Finding history" headings={["Version", "Finding", "Available tick"]}
            rows={receipt.outcomes.map((item) => [item.version, item.finding, item.available])} />
            : <Empty text="No finding available at this simulation tick." />}
        </> : <Empty text="Select a case to inspect its receipt." />}
      </Card>
    </div>
    <div className="two-columns">
      <Card title="Model lifecycle" subtitle="Only synthetic operations can activate these candidates">
        <dl className="details">
          <div><dt>Active</dt><dd>{lifecycle?.active ?? "Reference research scorecard"}</dd></div>
          <div><dt>Shadow model</dt><dd>{lifecycle?.shadow ?? "No challenger selected"}</dd></div>
          <div><dt>Paired shadow feedback</dt><dd>{overview?.paired_shadow.brier_delta != null
            ? `Brier Δ ${number(overview.paired_shadow.brier_delta, 4)} across ${overview.paired_shadow.cases} revealed demo cases`
            : "Waiting for revealed paired findings"}</dd></div>
        </dl>
        <div className="filters">
          <Select label="Training mode" value={trainingMode} items={options(["recalibrate", "retrain"])} onChange={setTrainingMode} />
          <button className="button secondary" disabled={busy || !overview} onClick={() => void execute(async () => {
            await localRequest(`${operations}/lifecycle/train?role=operator`, { cutoff: tick, mode: trainingMode });
            await refresh(run, selected);
            setMessage("Candidate validated against mature synthetic feedback.");
          })}>Train from mature findings</button>
        </div>
        {lifecycle?.candidates.map((candidate) => <div className="finding" key={candidate.model}>
          <h3 className="digest">{candidate.model}</h3>
          <p>{candidate.report ? Object.entries(candidate.report.gates).filter(([, pass]) => !pass).map(([key]) => key)
            .join(", ") || "All validation gates passed" : "Candidate evidence unavailable"}</p>
          <div className="actions">
            <button className="button secondary" disabled={busy || !candidate.report || lifecycle.active === candidate.model}
              onClick={() => lifecycleAction("shadow", candidate.model, candidate)}>Set shadow</button>
            <button className="button secondary" disabled={busy || lifecycle.shadow !== candidate.model ||
              !candidate.report || !Object.values(candidate.report.gates).every(Boolean)}
              onClick={() => lifecycleAction("promote", candidate.model, candidate)}>Approve activation</button>
          </div>
        </div>)}
        {lifecycle?.active && <button className="button secondary" disabled={busy}
          onClick={() => lifecycleAction("rollback", lifecycle.active!)}>Rollback activation</button>}
        <p className="quiet">Training requires at least 30 mature findings in each of three chronological splits.</p>
      </Card>
      <Card title="Analyst tools" subtitle="Deterministic evidence and explanations">
        <div className="actions">
          <button className="button secondary" disabled={busy || !current} onClick={() => void execute(async () => {
            setAssistant(await localRequest<AssistantReply>("/v1/analyst/tool?role=analyst", { tool: "risk", case_id: selected }));
          })}>Explain selected score</button>
          <button className="button secondary" disabled={busy} onClick={() => void execute(async () => {
            setAssistant(await localRequest<AssistantReply>("/v1/analyst/tool?role=analyst", { tool: "report" }));
          })}>Get research brief</button>
        </div>
        {assistant && <div className="job-state" aria-live="polite">
          <Status value={assistant.status} />
          {assistant.data?.risk !== undefined && <p>Calibrated risk {percent(assistant.data.risk, 2)}.</p>}
          {assistant.data?.eligible_groups !== undefined && <p>{number(assistant.data.eligible_groups)} eligible historical claim groups.</p>}
          {assistant.evidence?.model && <p>Model {assistant.evidence.model}</p>}
          <p className="digest">{assistant.evidence?.receipt ?? assistant.evidence?.aggregate_sha256}</p>
        </div>}
      </Card>
    </div>
    <Card title="Operations trace" subtitle="Accepted synthetic events for the selected run">
      {overview?.alert && <Note>Check feature coverage. The unknown-category rate is {percent(overview.unknown_category_rate ?? 0, 1)}.</Note>}
      {overview?.recent_dme_share_delta != null && <p className="quiet">DME share change across the latest two batches
        {` ${number(overview.recent_dme_share_delta * 100, 1)} percentage points.`}</p>}
      {trace?.events.length ? <Table caption="Operations trace" headings={["Sequence", "Event", "Tick", "Receipt chain"]}
        rows={trace.events.map((item) => [item.seq, item.kind, item.tick, <code title={item.digest}>{item.digest.slice(0, 16)}</code>])} />
        : <Empty text="Trace events will appear after intake." />}
    </Card>
    {!!overview?.recent_rejections.length && <Card title="Recent rejected events" subtitle="Local redacted quarantine">
      <Table caption="Redacted quarantined event metadata" headings={["Action", "Reason", "Tick", "Retry"]}
        rows={overview.recent_rejections.map((item) => [item.kind, item.code, item.tick, item.retryable ? "Eligible" : "Review input"])} />
    </Card>}
  </>;
}
