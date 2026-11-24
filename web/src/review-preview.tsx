import { useLayoutEffect, useRef, useState } from "react";
import { Empty, NextStep, Note, PageHeading, Section, Segmented, Status, Table } from "./components";
import { reviewActions, reviewOutcomes, reviewSteps } from "./review-state";
import type { Finding } from "./review-state";

const stepNotes = [
  "Four fictional claims are eligible. None has been selected yet.",
  "A uniform draw selected Demo A and assigned it to a reviewer.",
  "The finding is recorded but stays hidden until its availability tick.",
  "The clock reached tick 1, so version 1 of the finding is visible.",
  "A correction appended version 2. Version 1 is retained for audit.",
];

export function ReviewPreview() {
  const [step, setStep] = useState(0);
  const [capacity, setCapacity] = useState(2);
  const [finding, setFinding] = useState<Finding>("agree");
  const nextAction = useRef<HTMLButtonElement>(null);
  const reset = useRef<HTMLButtonElement>(null);
  const restoreFocus = useRef(false);
  useLayoutEffect(() => {
    if (!restoreFocus.current) return;
    (nextAction.current ?? reset.current)?.focus();
    restoreFocus.current = false;
  }, [step]);
  const moveTo = (next: number) => {
    restoreFocus.current = true;
    setStep(next);
  };
  const outcomes = reviewOutcomes(step, finding);
  return <>
    <PageHeading title="Follow a claim review"
      description="A fictional case moves from selection to a delayed finding and a recorded correction. Everything on this page runs in your browser." />
    <div className="columns">
      <Section title="Review workflow" meta="Fictional batch of four eligible cases">
        <div className="controls" style={{ marginBottom: 20 }}>
          <Segmented label="Review capacity" value={capacity} items={[1, 2, 3, 4].map((n) => ({ value: n, text: `${n} of 4` }))}
            onChange={(value) => { setCapacity(Number(value)); setStep(0); }} />
          <Segmented label="Reviewer finding" value={finding}
            items={[{ value: "agree", text: "Agreement" }, { value: "disagree", text: "Disagreement" }]}
            onChange={(value) => { setFinding(value as Finding); setStep(0); }} />
        </div>
        <ol className="timeline" aria-label="Review workflow">
          {reviewSteps.map((name, i) => <li key={name} className={i < step ? "done" : undefined} aria-current={i === step ? "step" : undefined}>
            <span>{name}</span>{i === step ? <Status value="current" /> : <span />}</li>)}
        </ol>
        <p className="quiet" aria-live="polite" style={{ margin: "14px 0 16px" }}>{stepNotes[step]}</p>
        <div className="actions">
          {step < reviewActions.length && <button ref={nextAction} type="button" className="button" onClick={() => moveTo(step + 1)}>
            {reviewActions[step]}</button>}
          {step > 0 && <button ref={reset} type="button" className="button secondary" onClick={() => moveTo(0)}>Reset example</button>}
        </div>
      </Section>
      <Section title="Decision receipt" meta="Synthetic case Demo A">
        <div className="receipt">
          <div className="receipt-head"><Status value={step >= 4 ? "corrected" : step >= 3 ? "revealed" : step >= 1 ? "assigned" : "pending"} />
            <p>receipt demo-a · v{Math.max(1, outcomes.length)}</p></div>
          <div className="receipt-body">
            <dl className="details">
              <div><dt>Design</dt><dd>Uniform sample without replacement</dd></div>
              <div><dt>Selection reason</dt><dd>Drawn from four eligible fictional cases</dd></div>
              <div><dt>Inclusion probability</dt><dd>{capacity}/4 ({capacity * 25}%)</dd></div>
              <div><dt>Finding available</dt><dd>Simulation tick 1</dd></div>
              <div><dt>State</dt><dd aria-live="polite">{reviewSteps[step]}</dd></div>
            </dl>
            {outcomes.length ? <Table caption="Revealed illustrative findings" headings={["Version", "Finding", "Available at tick"]}
              rows={outcomes} /> : <div style={{ marginTop: 14 }}><Empty text="No finding is visible at this step." /></div>}
          </div>
        </div>
      </Section>
    </div>
    <Note>This simulation uses four invented cases. The local workspace persists the same events in SQLite, verifies the receipt
      chain and scores fictional features with the reference model.</Note>
    <NextStep from="review" />
  </>;
}
