import { useEffect, useState } from "react";
import { RefreshCw, ShieldCheck } from "lucide-react";
import { Empty, Figures, Note, PageHeading, Panel, Section, Segmented, Select, Status, Table, sentence } from "./components";
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
  history: { seq: number; kind: string; tick: number; digest: string }[];
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

const options = (values: string[]) => values.map((value) => ({ value, text: sentence(value.replaceAll("-", " ")) }));
const textError = (error: unknown) => error instanceof TypeError
  ? "The loopback API is unavailable. Start it locally and retry."
  : error instanceof Error ? error.message : "The operation could not be completed.";

export function Operations() {
  const [overview, setOverview] = useState<Overview>();
  const [run, setRun] = useState("");
  const [cases, setCases] = useState<Case[]>([]);
  const [selected, setSelected] = useState("");
  const [queueState, setQueueState] = useState("all");
  const [queueOrder, setQueueOrder] = useState("case");
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
  const queueRows = cases.filter((item) => queueState === "all" || item.state === queueState)
    .sort((a, b) => (queueOrder === "state" ? a.state.localeCompare(b.state) : 0) || a.case_id.localeCompare(b.case_id));
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
    if (!active) {
      setCases([]); setSelected(""); setReceipt(undefined); setTrace(undefined);
      return;
    }
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
    <PageHeading title="Review operations"
      description="Intake fictional claims, allocate reviews, advance the simulated clock and verify each decision receipt. State persists in a local SQLite store."
      aside={<button className="button secondary" type="button" disabled={busy}
        onClick={() => void execute(() => refresh(run || undefined, selected))}><RefreshCw size={14} aria-hidden="true" />Refresh</button>} />
    {error && <p className="error" role="alert">{error}</p>}
    {message && <p className="message" role="status">{message}</p>}
    {!overview && !error && <p className="loading" role="status">Loading local operations</p>}
    {overview && <Figures label="Operations status" items={[
      { title: "Simulation tick", value: number(overview.tick) },
      { title: "Queued reviews", value: number(overview.states.queued ?? 0) },
      { title: "Cases with revealed findings", value: number(overview.revealed_cases) },
      { title: "Event p95 latency", value: overview.event_latency.p95_ms == null ? "No events" : `${number(overview.event_latency.p95_ms, 1)} ms` },
    ]} />}
    <Section title="Batch intake" meta="Synthetic claims · analyst role">
      <div className="controls">
        <Segmented label="Review capacity" value={capacity} items={[0, 1, 2, 3, 4].map((n) => ({ value: n, text: `${n} of 4` }))}
          onChange={(value) => setCapacity(Number(value))} />
        <Segmented label="Selection strategy" value={strategy} items={[{ value: "hybrid-10", text: "10% exploration" },
          { value: "uniform", text: "Uniform" }, { value: "greedy", text: "Greedy" }]} onChange={setStrategy} />
        <div className="actions">
          <button className="button" type="button" onClick={startBatch} disabled={busy || !overview}>Intake sample batch</button>
          <button className="button secondary" type="button" disabled={busy || !run} onClick={() => void execute(async () => {
            await event("advance", "operator", { advance_to: tick + 1 });
            await refresh(run, selected);
            setMessage("Simulation clock advanced.");
          })}>Advance clock one tick</button>
        </div>
      </div>
    </Section>
    <div className="columns wide-left">
      <Section title="Review queue" meta="Findings appear once their availability tick is reached">
        {overview?.recent_runs.length ? <div className="controls" style={{ marginBottom: 14 }}>
          <Select label="Intake run" value={run} items={options(overview.recent_runs.map((item) => item.run_id))}
            onChange={(value) => { setQueueState("all"); void execute(() => refresh(value)); }} />
          {cases.length > 0 && <>
            <Select label="Queue state" value={queueState} items={options(["all", ...new Set(cases.map((item) => item.state))])}
              onChange={setQueueState} />
            <Select label="Sort cases" value={queueOrder} items={options(["case", "state"])} onChange={setQueueOrder} />
          </>}
        </div> : <Empty text="Intake a sample batch to create a queue." />}
        {queueRows.length > 0 && <Table caption="Synthetic review queue" headings={["Case", "State", "Finding", "Receipt"]}
          highlight={(i) => queueRows[i]?.case_id === selected}
          rows={queueRows.map((row) => [<span className="digest" key={row.case_id}>{row.case_id}</span>, <Status key="s" value={row.state} />,
            row.finding?.finding ?? "Pending",
            <button key="b" type="button" className={`button small ${selected === row.case_id ? "" : "secondary"}`} disabled={busy}
              aria-pressed={selected === row.case_id}
              onClick={() => void execute(async () => {
                setSelected(row.case_id);
                setReplacement("");
                setReceipt(await localRequest<Receipt>(`${operations}/receipts/${row.case_id}`));
              })}>Inspect {row.case_id.split("-").at(-1)}</button>])} />}
        {cases.length > 0 && !queueRows.length && <Empty text="No cases match this queue state." />}
        {current && <div className="queue-actions">
          <h3>Actions for case {current.case_id.split("-").at(-1)} <Status value={current.state} /></h3>
          <div className="controls">
            {current.state === "queued" && <>
              <Select label="Reviewer" value={reviewer} items={options(["reviewer-a", "reviewer-b"])} onChange={setReviewer} />
              <button className="button" type="button" disabled={busy} onClick={() => review("assign", "reviewer", { reviewer })}>Assign review</button>
            </>}
            {(current.state === "assigned" || current.finding) && <>
              <Select label="Finding" value={finding} items={options(["agree", "disagree"])} onChange={setFinding} />
              <Select label="Review note" value={note} items={options(["documentation", "coding", "eligibility", "other"])} onChange={setNote} />
              {current.state === "assigned" ? <button className="button" type="button" disabled={busy}
                onClick={() => review("submit", "reviewer", { finding, note, available_tick: tick + 1 })}>Submit delayed finding</button>
                : <button className="button secondary" type="button" disabled={busy}
                  onClick={() => review("correct", "supervisor", { finding, note, available_tick: tick + 1,
                    replaces: current.finding?.version, reason: "source_revision" })}>Record correction</button>}
              {current.state === "reviewed" && <button className="button secondary" type="button" disabled={busy}
                onClick={() => review("close", "reviewer")}>Close</button>}
            </>}
          </div>
          {current.state === "queued" && cases.some((row) => row.state === "unselected") && <div className="controls">
            <Select label="Override replacement" value={replacement}
              items={[{ value: "", text: "Choose a case" }, ...options(cases.filter((row) => row.state === "unselected").map((row) => row.case_id))]}
              onChange={setReplacement} />
            <button className="button secondary" type="button" disabled={busy || !replacement}
              onClick={() => review("override", "supervisor", { replacement, reason: "priority_change" })}>Swap queued case</button>
          </div>}
        </div>}
      </Section>
      <Section title="Decision receipt" meta="Evidence captured at decision time, plus revealed finding versions">
        {receipt ? <div className="receipt">
          <div className="receipt-head"><Status value={receipt.design_status} /><p>{receipt.receipt.case_id.split("-").slice(-2).join("-")}</p></div>
          <div className="receipt-body">
            <dl className="details">
              <div><dt>Model</dt><dd className="digest">{receipt.receipt.score.model}</dd></div>
              <div><dt>Score</dt><dd>{percent(receipt.receipt.score.calibrated_risk, 2)} · {receipt.receipt.score.explanation.method}</dd></div>
              <div><dt>Selection</dt><dd>{receipt.receipt.decision.reason} · inclusion {
                receipt.receipt.decision.probability.numerator}/{receipt.receipt.decision.probability.denominator}</dd></div>
              {receipt.receipt.score.shadow && <div><dt>Shadow</dt><dd>{receipt.receipt.score.shadow.model} · {
                receipt.receipt.score.shadow.risk == null ? receipt.receipt.score.shadow.status : percent(receipt.receipt.score.shadow.risk, 2)}</dd></div>}
              <div><dt>Digest</dt><dd className="digest">{receipt.digest}</dd></div>
            </dl>
            <div className="actions" style={{ marginTop: 14 }}>
              <button className="button secondary small" type="button" disabled={busy} onClick={() => void execute(async () => {
                const integrity = await localRequest<{ sequence: number }>(`${operations}/integrity`);
                setMessage(`Receipt projection and event chain verified through event ${integrity.sequence}.`);
              })}><ShieldCheck size={14} aria-hidden="true" />Verify event chain</button>
            </div>
            {receipt.outcomes.length ? <Table caption="Finding history" headings={["Version", "Finding", "Available tick"]}
              rows={receipt.outcomes.map((item) => [item.version, item.finding, item.available])} />
              : <div style={{ marginTop: 14 }}><Empty text="No finding available at this simulation tick." /></div>}
            {!!receipt.history.length && <details className="disclosure" style={{ marginTop: 14 }}>
              <summary>Case actions</summary>
              <Table caption="Persisted case actions" headings={["Sequence", "Action", "Tick"]} numeric={[2]}
                rows={receipt.history.map((item) => [item.seq, item.kind, item.tick])} />
            </details>}
          </div>
        </div> : <Empty text="Select a case to inspect its receipt." />}
      </Section>
    </div>
    <div className="columns">
      <Panel title="Model lifecycle" meta="Synthetic candidates only. The research champion is never replaced.">
        <dl className="details">
          <div><dt>Active</dt><dd>{lifecycle?.active ?? "Reference research scorecard"}</dd></div>
          <div><dt>Shadow</dt><dd>{lifecycle?.shadow ?? "No challenger in shadow"}</dd></div>
          <div><dt>Paired shadow feedback</dt><dd>{overview?.paired_shadow.brier_delta != null
            ? `Brier difference ${number(overview.paired_shadow.brier_delta, 4)} across ${overview.paired_shadow.cases} revealed cases`
            : "Waiting for revealed paired findings"}</dd></div>
        </dl>
        <div className="controls" style={{ marginTop: 16 }}>
          <Segmented label="Training mode" value={trainingMode} items={[{ value: "recalibrate", text: "Recalibrate" },
            { value: "retrain", text: "Retrain" }]} onChange={setTrainingMode} />
          <button className="button secondary" type="button" disabled={busy || !overview} onClick={() => void execute(async () => {
            await localRequest(`${operations}/lifecycle/train?role=operator`, { cutoff: tick, mode: trainingMode });
            await refresh(run, selected);
            setMessage("Candidate validated against mature synthetic feedback.");
          })}>Train from mature findings</button>
        </div>
        <p className="quiet" style={{ marginTop: 10 }}>Training needs at least 30 mature findings in each of three chronological splits.</p>
        {lifecycle?.candidates.map((candidate) => <div className="candidate" key={candidate.model}>
          <h3>{candidate.model}</h3>
          <p>{candidate.report ? Object.entries(candidate.report.gates).filter(([, pass]) => !pass).map(([key]) => key.replaceAll("_", " "))
            .join(", ").replace(/^(.+)$/, "Failed gates: $1") || "All validation gates passed" : "Candidate evidence unavailable"}</p>
          <div className="actions">
            <button className="button secondary small" type="button" disabled={busy || !candidate.report || lifecycle.active === candidate.model}
              onClick={() => lifecycleAction("shadow", candidate.model, candidate)}>Set shadow</button>
            <button className="button secondary small" type="button" disabled={busy || lifecycle.shadow !== candidate.model ||
              !candidate.report || !Object.values(candidate.report.gates).every(Boolean)}
              onClick={() => lifecycleAction("promote", candidate.model, candidate)}>Approve activation</button>
          </div>
        </div>)}
        {lifecycle?.active && <button className="button secondary small" type="button" style={{ marginTop: 12 }} disabled={busy}
          onClick={() => lifecycleAction("rollback", lifecycle.active!)}>Roll back activation</button>}
      </Panel>
      <Panel title="Analyst tools" meta="Deterministic explanations with receipt and evidence links">
        <div className="actions">
          <button className="button secondary" type="button" disabled={busy || !current} onClick={() => void execute(async () => {
            setAssistant(await localRequest<AssistantReply>("/v1/analyst/tool?role=analyst", { tool: "risk", case_id: selected }));
          })}>Explain selected score</button>
          <button className="button secondary" type="button" disabled={busy} onClick={() => void execute(async () => {
            setAssistant(await localRequest<AssistantReply>("/v1/analyst/tool?role=analyst", { tool: "report" }));
          })}>Get research brief</button>
        </div>
        {assistant ? <div className="stack" aria-live="polite" style={{ marginTop: 16 }}>
          <p><Status value={assistant.status} /></p>
          {assistant.data?.risk !== undefined && <p className="prose">Calibrated risk {percent(assistant.data.risk, 2)}.</p>}
          {assistant.data?.eligible_groups !== undefined && <p className="prose">{number(assistant.data.eligible_groups)} eligible historical claim groups.</p>}
          {assistant.evidence?.model && <p className="quiet">Model <span className="digest">{assistant.evidence.model}</span></p>}
          <p className="digest">{assistant.evidence?.receipt ?? assistant.evidence?.aggregate_sha256}</p>
        </div> : <p className="quiet" style={{ marginTop: 14 }}>Select a case, then ask for an explanation of its score.</p>}
      </Panel>
    </div>
    <Section title="Operations trace" meta="Accepted synthetic events for the selected run">
      {overview?.alert && <div style={{ marginBottom: 14 }}><Note tone="caution">Check feature coverage. The unknown-category rate
        is {percent(overview.unknown_category_rate ?? 0, 1)}.</Note></div>}
      {overview?.recent_dme_share_delta != null && <p className="quiet" style={{ marginBottom: 12 }}>DME share changed by
        {` ${number(overview.recent_dme_share_delta * 100, 1)} percentage points across the latest two batches.`}</p>}
      {trace?.events.length ? <Table caption="Operations trace" headings={["Sequence", "Event", "Tick", "Receipt chain"]} numeric={[2]}
        rows={trace.events.map((item) => [item.seq, item.kind, item.tick, <code className="digest" key={item.seq} title={item.digest}>{item.digest.slice(0, 16)}</code>])} />
        : <Empty text="Trace events appear after intake." />}
    </Section>
    {!!overview?.recent_rejections.length && <Section title="Rejected events" meta="Local redacted quarantine">
      <Table caption="Redacted quarantined event metadata" headings={["Action", "Reason", "Tick", "Retry"]}
        rows={overview.recent_rejections.map((item) => [item.kind, item.code.replaceAll("_", " "), item.tick, item.retryable ? "Eligible" : "Review input"])} />
    </Section>}
  </>;
}
