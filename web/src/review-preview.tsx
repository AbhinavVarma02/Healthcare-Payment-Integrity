import { useState } from "react";
import { Card, Empty, Note, PageHeading, Select, Status, Table } from "./components";
import { reviewActions, reviewOutcomes, reviewSteps } from "./review-state";
import type { Finding } from "./review-state";

export function ReviewPreview() {
  const [step, setStep] = useState(0);
  const [capacity, setCapacity] = useState(2);
  const [finding, setFinding] = useState<Finding>("agree");
  const outcomes = reviewOutcomes(step, finding);
  return <>
    <PageHeading eyebrow="Browser simulation" title="Follow a claim review"
      description="Walk through a fictional review from assignment to a delayed finding and a recorded correction." />
    <div className="overview-grid">
      <Card title="Review timeline" subtitle="Fictional batch · Four eligible demo cases">
        <div className="filters">
          <Select label="Review capacity" value={capacity} items={[1, 2, 3, 4].map((n) => ({ value: n, text: `${n} of 4` }))}
            onChange={(value) => { setCapacity(Number(value)); setStep(0); }} />
          <Select label="Reviewer finding" value={finding} items={[{ value: "agree", text: "Agreement" }, { value: "disagree", text: "Disagreement" }]}
            onChange={(value) => { setFinding(value as Finding); setStep(0); }} />
        </div>
        <ol className="timeline" aria-label="Review workflow">
          {reviewSteps.map((label, i) => <li key={label} aria-current={i === step ? "step" : undefined}>
            <span>{label}</span>{i === step && <Status value="Current" />}</li>)}
        </ol>
        <div className="actions">
          {step < reviewActions.length && <button className="button" onClick={() => setStep(step + 1)}>{reviewActions[step]}</button>}
          {step > 0 && <button className="button secondary" onClick={() => setStep(0)}>Reset example</button>}
        </div>
      </Card>
      <Card title="Illustrative receipt" subtitle="Synthetic case · Demo A">
        <dl className="details">
          <div><dt>Design</dt><dd>Uniform sample</dd></div>
          <div><dt>Selection reason</dt><dd>Drawn from four eligible fictional cases</dd></div>
          <div><dt>Inclusion probability</dt><dd>{capacity}/4</dd></div>
          <div><dt>Availability</dt><dd>Simulation tick 1</dd></div>
          <div><dt>State</dt><dd aria-live="polite">{reviewSteps[step]}</dd></div>
        </dl>
        {outcomes.length ? <Table caption="Revealed illustrative findings" headings={["Version", "Finding", "Available at"]}
          rows={outcomes} /> : <Empty text="No finding is available at this step." />}
      </Card>
    </div>
    <Note>This preview runs in the browser using four invented cases. The local operations workspace persists events,
      verifies receipts and scores fictional features with the reference model.</Note>
    <a className="text-action" href="#/validation">Continue to the champion decision</a>
  </>;
}
