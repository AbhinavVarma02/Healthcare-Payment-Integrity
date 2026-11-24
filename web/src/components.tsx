import { useId } from "react";
import type { ReactNode } from "react";
import { ArrowRight, Info, TriangleAlert } from "lucide-react";

export function PageHeading({ kicker, title, description, aside }: {
  kicker?: string; title: string; description: ReactNode; aside?: ReactNode;
}) {
  return <header className="page-head">
    <div>{kicker && <p className="kicker">{kicker}</p>}<h1>{title}</h1><p className="lede">{description}</p></div>
    {aside && <div className="page-actions">{aside}</div>}
  </header>;
}

/** A titled block. It is deliberately not a named landmark: headings already structure the page. */
export function Section({ title, meta, actions, children, className = "" }: {
  title: string; meta?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string;
}) {
  return <section className={`section ${className}`}>
    <header className="section-head">
      <div><h2>{title}</h2>{meta && <p className="meta">{meta}</p>}</div>
      {actions && <div className="section-actions">{actions}</div>}
    </header>
    {children}
  </section>;
}

export function Panel({ title, meta, action, children, className = "" }: {
  title?: string; meta?: ReactNode; action?: ReactNode; children: ReactNode; className?: string;
}) {
  return <div className={`panel ${className}`}>
    {(title || action) && <div className="panel-head">
      <div>{title && <h2>{title}</h2>}{meta && <p className="meta">{meta}</p>}</div>{action}
    </div>}
    {children}
  </div>;
}

const statusTone = (value: string) => ["supported", "completed", "verified", "ok", "passed", "ready", "reviewed", "closed"].includes(value) ? "good"
  : ["mixed", "inconclusive", "research-only", "pending", "queued", "running", "assigned", "current"].includes(value) ? "caution"
  : ["unsupported", "not supported", "failed", "unavailable", "not approved", "rejected", "cancelled", "interrupted"].includes(value)
    ? "critical" : "";

export const sentence = (value: string) => value.charAt(0).toUpperCase() + value.slice(1);

export function Status({ value }: { value: string }) {
  return <span className={`status ${statusTone(value.toLowerCase())}`}>{sentence(value)}</span>;
}

export function Note({ children, tone }: { children: ReactNode; tone?: "caution" }) {
  return <div className={`note ${tone ?? ""}`}>
    {tone === "caution" ? <TriangleAlert size={16} aria-hidden="true" /> : <Info size={16} aria-hidden="true" />}
    <p>{children}</p>
  </div>;
}

export function Empty({ text }: { text: string }) {
  return <p className="empty">{text}</p>;
}

/** Wraps a trailing percentage-point unit so points never read like percentages. */
export function Value({ text }: { text: ReactNode }) {
  if (typeof text !== "string") return <>{text}</>;
  const match = /^(.*\d)( pp)$/.exec(text);
  return match ? <span className="measure">{match[1]}<span className="unit">{match[2]}</span></span> : <>{text}</>;
}

export type Option = { value: string | number; text: string };

export function Select({ label, value, items, onChange, hint }: {
  label: string; value: string | number; items: Option[]; onChange: (value: string) => void; hint?: string;
}) {
  return <label className="control"><span>{label}{hint && <small>{hint}</small>}</span>
    <span className="select"><select value={value} onChange={(event) => onChange(event.target.value)}>
      {items.map((item) => <option key={item.value} value={item.value}>{item.text}</option>)}
    </select></span>
  </label>;
}

export function Segmented({ label, value, items, onChange, fill = false }: {
  label: string; value: string | number; items: Option[]; onChange: (value: string) => void; fill?: boolean;
}) {
  const name = useId();
  return <div className={`segmented${fill ? " fill" : ""}`}>
    <span className="segmented-label" aria-hidden="true">{label}</span>
    <div className="track" role="radiogroup" aria-label={label}>{items.map((item) => <label key={item.value}>
      <input type="radio" name={name} value={item.value} checked={String(item.value) === String(value)}
        onChange={() => onChange(String(item.value))} /><span>{item.text}</span>
    </label>)}</div>
  </div>;
}

export function Table({ headings, rows, caption, numeric = [], wrap = [], highlight, rowLabels }: {
  headings: string[]; rows: ReactNode[][]; caption: string; numeric?: number[]; wrap?: number[];
  highlight?: (index: number) => boolean; rowLabels?: boolean;
}) {
  const alignment = (i: number) => numeric.includes(i) ? "number-cell" : wrap.includes(i) ? "wrap-cell" : undefined;
  return <div className="table-wrap" role="region" tabIndex={0} aria-label={caption}>
    <table aria-label={caption}><thead><tr>{headings.map((head, i) =>
      <th key={head} scope="col" className={alignment(i)}>{head}</th>)}</tr></thead>
      <tbody>{rows.map((row, i) => <tr key={i} className={highlight?.(i) ? "highlight" : undefined}>{row.map((cell, j) =>
        j === 0 && rowLabels !== false
          ? <th key={j} scope="row">{cell}</th>
          : <td key={j} className={alignment(j)}><Value text={cell} /></td>)}</tr>)}</tbody>
    </table>
  </div>;
}

export function Figures({ items, compact = false, vertical = false, label }: {
  items: { title: string; value: ReactNode; detail?: ReactNode }[]; compact?: boolean; vertical?: boolean; label?: string;
}) {
  return <dl className={`figures${compact ? " compact" : ""}${vertical ? " vertical" : ""}`}
    style={{ "--count": items.length } as React.CSSProperties} data-label={label}>
    {items.map(({ title, value, detail }) => <div key={title}>
      <dt>{title}</dt><dd><strong><Value text={value} /></strong>{detail && <small>{detail}</small>}</dd>
    </div>)}
  </dl>;
}

export const tour = [
  { key: "planner", page: "Audit planner", title: "Set the review capacity", text: "Compare strategies at 1% to 10% of claims with the same number of reviews." },
  { key: "replay", page: "Policy replay", title: "Check the uncertainty", text: "Seed percentiles, interval coverage and the uniform reference." },
  { key: "review", page: "Review simulation", title: "Follow a decision receipt", text: "Assignment, a delayed finding and a recorded correction." },
  { key: "validation", page: "Validation", title: "Review the champion decision", text: "Why the hierarchical lookup remains the research scorecard." },
];

export function NextStep({ from }: { from: string }) {
  const index = tour.findIndex((step) => step.key === from);
  if (index < 0) return null;
  const next = tour[index + 1];
  return <nav className="next-step" aria-label="Walkthrough progress">
    <div><p>Walkthrough, step {index + 1} of {tour.length}</p>
      <strong>{next ? next.title : "Walkthrough complete"}</strong></div>
    <a className="button secondary" href={next ? `#/${next.key}` : "#/overview"}>
      {next ? `Continue to ${next.page.toLowerCase()}` : "Return to the overview"}<ArrowRight size={15} aria-hidden="true" />
    </a>
  </nav>;
}
