import { useState } from "react";
import type { ReactNode } from "react";
import { CircleHelp, Info } from "lucide-react";
import { number } from "./numbers";

export function PageHeading({ eyebrow, title, description, aside }: {
  eyebrow: string; title: string; description: string; aside?: ReactNode;
}) {
  return <header className="page-heading">
    <div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p className="lede">{description}</p></div>
    {aside}
  </header>;
}

export function Card({ title, subtitle, action, children, className = "" }: {
  title: string; subtitle?: string; action?: ReactNode; children: ReactNode; className?: string;
}) {
  return <section className={`card ${className}`}>
    <div className="card-heading"><div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div>{action}</div>
    {children}
  </section>;
}

export function Status({ value }: { value: string }) {
  return <span className={`status ${value === "supported" || value === "completed" ? "good" : ""}`}>{value}</span>;
}

export function Note({ children }: { children: ReactNode }) {
  return <div className="note"><Info size={18} aria-hidden="true" /><p>{children}</p></div>;
}

export function Empty({ text }: { text: string }) {
  return <p className="empty"><CircleHelp size={18} aria-hidden="true" />{text}</p>;
}

export function Select({ label, value, items, onChange }: {
  label: string; value: string | number; items: { value: string | number; text: string }[];
  onChange: (value: string) => void;
}) {
  return <label className="control"><span>{label}</span>
    <select value={value} onChange={(e) => onChange(e.target.value)}>
      {items.map((item) => <option key={item.value} value={item.value}>{item.text}</option>)}
    </select>
  </label>;
}

export function Table({ headings, rows, caption }: { headings: string[]; rows: ReactNode[][]; caption: string }) {
  return <div className="table-wrap" role="region" tabIndex={0} aria-label={caption}>
    <table aria-label={caption}><thead><tr>{headings.map((head) => <th key={head} scope="col">{head}</th>)}</tr></thead>
      <tbody>{rows.map((row, i) => <tr key={i}>{row.map((cell, j) => j === 0
        ? <th key={j} scope="row">{cell}</th> : <td key={j}>{cell}</td>)}</tr>)}</tbody>
    </table>
  </div>;
}

const colors = ["#0a7569", "#315f9f", "#aa632b", "#885da9", "#c34e74", "#63824a"];
export type Series = { name: string; points: [number, number][] };

export function Plot({ title, series, rangeX, rangeY, xLabels, xTicks, xTitle, yTitle, diagonal = false }: {
  title: string; series: Series[]; rangeX: [number, number]; rangeY: [number, number];
  xLabels?: (x: number) => string; xTicks?: number[]; xTitle?: string; yTitle?: string; diagonal?: boolean;
}) {
  const [dataOpen, setDataOpen] = useState(false);
  const left = 51, right = 546, top = 18, bottom = 215;
  const x = (v: number) => left + (v - rangeX[0]) / (rangeX[1] - rangeX[0]) * (right - left);
  const y = (v: number) => bottom - (v - rangeY[0]) / (rangeY[1] - rangeY[0]) * (bottom - top);
  const ySteps = Array.from({ length: 5 }, (_, i) => rangeY[0] + i * (rangeY[1] - rangeY[0]) / 4);
  const xSteps = xTicks ?? Array.from({ length: 5 }, (_, i) => rangeX[0] + i * (rangeX[1] - rangeX[0]) / 4);
  return <div className="plot">
    {yTitle && <div className="axis-name">{yTitle}</div>}
    <svg viewBox="0 0 570 252" role="img" aria-label={title}>
      <title>{title}</title>
      {ySteps.map((v) => <g key={v}>
        <line x1={left} x2={right} y1={y(v)} y2={y(v)} className="gridline" />
        <text x={left - 10} y={y(v) + 4} textAnchor="end">{number(v * 100, Math.abs(v * 100 - Math.round(v * 100)) > 1e-9 ? 1 : 0)}%</text>
      </g>)}
      {xSteps.map((v) => <text key={v} x={x(v)} y={bottom + 20} textAnchor="middle">
        {xLabels ? xLabels(v) : `${number(v * 100)}%`}
      </text>)}
      {diagonal && <path d={`M ${x(0)},${y(0)} L ${x(1)},${y(1)}`} className="diagonal" />}
      {series.map((line, i) => <g key={line.name}>
        <polyline points={line.points.map(([a, b]) => `${x(a)},${y(b)}`).join(" ")}
          fill="none" stroke={colors[i % colors.length]} strokeWidth="2.5" strokeLinejoin="round" />
        {line.points.length < 15 && line.points.map(([a, b]) => <circle key={`${a}-${b}`}
          cx={x(a)} cy={y(b)} r="4" fill={colors[i % colors.length]} stroke="#fff" strokeWidth="1.2">
          <title>{line.name} · {xLabels ? xLabels(a) : number(a * 100, 1) + "%"} · {number(b * 100, 1)}%</title>
        </circle>)}
      </g>)}
    </svg>
    {xTitle && <div className="axis-name x-axis">{xTitle}</div>}
    <div className="legend">{series.map((line, i) => <span key={line.name}>
      <svg width="14" height="9" aria-hidden="true"><rect width="14" height="3" y="3" fill={colors[i % colors.length]} /></svg>
      {line.name}
    </span>)}</div>
    <details className="provenance" onToggle={(event) => setDataOpen(event.currentTarget.open)}>
      <summary>Chart values</summary>
      {dataOpen && <Table caption={title} headings={["Series", xTitle ?? "X", yTitle ?? "Y"]}
        rows={series.flatMap((line) => line.points.map(([a, b]) => [
          line.name, xLabels ? xLabels(a) : `${number(a * 100, 2)}%`, `${number(b * 100, 2)}%`,
        ]))} />}
    </details>
  </div>;
}
