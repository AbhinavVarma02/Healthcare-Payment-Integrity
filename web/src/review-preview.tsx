import { useState } from "react";
import { Card, Note, PageHeading, Select, Status, Table } from "./components";

const steps = ["Intake available", "Review assigned", "Finding pending", "Finding revealed", "Correction recorded"];
const next = ["Assign a review", "Submit finding", "Advance clock", "Record correction"];

export function ReviewPreview() {
  const [step, setStep] = useState(0);
  const [capacity, setCapacity] = useState(2);
  const [finding, setFinding] = useState("agree");
  return <>
    <PageHeading eyebrow="Browser simulation" title="Follow a claim review"
      description="Walk through a fictional review from assignment to a delayed finding and a recorded correction." />
    <div className="overview-grid">
      <Card title="Review timeline" subtitle="Fictional batch · Four eligible demo cases">
        <div className="filters">
          <Select label="Review capacity" value={capacity} items={[1, 2, 3, 4].map((n) => ({ value: n, text: `${n} of 4` }))}
            onChange={(value) => { setCapacity(Number(value)); setStep(0); }} />
          <Select label="Reviewer finding" value={finding} items={[{ value: "agree", text: "Agreement" }, { value: "disagree", text: "Disagreement" }]}
            onChange={(value) => { setFinding(value); setStep(0); }} />
        </div>
        <ol className="timeline" aria-label="Review workflow">
          {steps.map((label, i) => <li key={label} aria-current={i === step ? "step" : undefined}>
            <span>{label}</span>{i === step && <Status value="Current" />}</li>)}
        </ol>
        <div className="actions">
          {step < steps.length - 1 && <button className="button" onClick={() => setStep(step + 1)}>{next[step]}</button>}
          {step > 0 && <button className="button secondary" onClick={() => setStep(0)}>Reset example</button>}
        </div>
      </Card>
      <Card title="Illustrative receipt" subtitle="Synthetic case · Demo A">
        <dl className="details">
          <div><dt>Design</dt><dd>Uniform sample</dd></div>
          <div><dt>Inclusion probability</dt><dd>{capacity}/4</dd></div>
          <div><dt>Availability</dt><dd>Simulation tick 1</dd></div>
          <div><dt>State</dt><dd aria-live="polite">{steps[step]}</dd></div>
        </dl>
        {step >= 3 && <Table caption="Revealed illustrative findings" headings={["Version", "Finding", "Available at"]}
          rows={[[1, finding, 1], ...(step === 4 ? [[2, finding === "agree" ? "disagree" : "agree", 2]] : [])]} />}
      </Card>
    </div>
    <Note>This preview runs in the browser using four invented cases. The local operations workspace persists events,
      verifies receipts and scores fictional features with the reference model.</Note>
  </>;
}
