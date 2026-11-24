import { useLayoutEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { CircleHelp, Info } from "lucide-react";
import { percent } from "./numbers";

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
  const tone = ["supported", "completed", "verified", "ok"].includes(value) ? "good"
    : ["mixed", "inconclusive", "research-only", "pending"].includes(value) ? "caution"
    : ["unsupported", "not supported", "failed", "unavailable"].includes(value) ? "critical" : "";
  return <span className={`status ${tone}`}>{value}</span>;
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

export function Table({ headings, rows, caption, numeric = [] }: {
  headings: string[]; rows: ReactNode[][]; caption: string; numeric?: number[];
}) {
  const alignment = (i: number) => numeric.includes(i) ? "number-cell" : undefined;
  return <div className="table-wrap" role="region" tabIndex={0} aria-label={caption}>
    <table aria-label={caption}><thead><tr>{headings.map((head, i) =>
      <th key={head} scope="col" className={alignment(i)}>{head}</th>)}</tr></thead>
      <tbody>{rows.map((row, i) => <tr key={i}>{row.map((cell, j) => j === 0
        ? <th key={j} scope="row">{cell}</th> : <td key={j} className={alignment(j)}>{cell}</td>)}</tr>)}</tbody>
    </table>
  </div>;
}

export type Series = {
  name: string; points: [number, number][]; tone?: number;
  annotation?: string; annotationBelow?: boolean;
  spread?: ([number, number] | null)[]; pointLabels?: string[];
};
const dashes = [undefined, "5 3", "2 3", "7 3 2 3", "10 3", "3 2 1 2"];
const symbols = [
  "M 0 -5 A 5 5 0 1 1 0 5 A 5 5 0 1 1 0 -5",
  "M -5 -5 H 5 V 5 H -5 Z",
  "M 0 -6 L 6 0 L 0 6 L -6 0 Z",
  "M 0 -6 L 6 5 H -6 Z",
  "M -6 -5 H 6 L 0 6 Z",
  "M -5 -2 H -2 V -5 H 2 V -2 H 5 V 2 H 2 V 5 H -2 V 2 H -5 Z",
];
const axisPercent = (n: number) => percent(n, Math.abs(n * 100 - Math.round(n * 100)) > 1e-9 ? 1 : 0);

function Mark({ index, x, y, children }: { index: number; x: number; y: number; children?: ReactNode }) {
  return <path className="plot-mark" d={symbols[index % symbols.length]} transform={`translate(${x} ${y})`}>{children}</path>;
}

export function Plot({ title, series, rangeX, rangeY, xLabels = axisPercent, xTicks, xTitle, yTitle, diagonal = false,
  scatter = false, legendNote, xValue = xLabels === axisPercent ? (v: number) => percent(v, 2) : xLabels,
  yLabel = axisPercent, yValue = (v: number) => percent(v, 2), yTicks, referenceY, compact = false }: {
  title: string; series: Series[]; rangeX: [number, number]; rangeY: [number, number];
  xLabels?: (x: number) => string; xTicks?: number[]; xTitle?: string; yTitle?: string; diagonal?: boolean;
  scatter?: boolean; legendNote?: string; xValue?: (x: number) => string;
  yLabel?: (y: number) => string; yValue?: (y: number) => string;
  yTicks?: number[]; referenceY?: number; compact?: boolean;
}) {
  const [dataOpen, setDataOpen] = useState(false);
  const plot = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(550);
  useLayoutEffect(() => {
    const element = plot.current;
    if (!element) return;
    const measure = () => setWidth(Math.max(220, element.clientWidth));
    const observer = new ResizeObserver(measure);
    measure();
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  const height = compact ? 178 : width < 390 ? 194 : 214;
  const ySteps = yTicks ?? Array.from({ length: 5 }, (_, i) => rangeY[0] + i * (rangeY[1] - rangeY[0]) / 4);
  const left = Math.max(47, Math.max(...ySteps.map((value) => yLabel(value).length)) * 7 + 10);
  const right = width - 26, top = 12, bottom = height - 25;
  const x = (v: number) => left + (v - rangeX[0]) / (rangeX[1] - rangeX[0]) * (right - left);
  const y = (v: number) => bottom - (v - rangeY[0]) / (rangeY[1] - rangeY[0]) * (bottom - top);
  const xSteps = (xTicks ?? Array.from({ length: 5 }, (_, i) => rangeX[0] + i * (rangeX[1] - rangeX[0]) / 4))
    .filter((_, i, all) => width >= 420 || all.length < 7 || i % 2 === 0 && i < all.length - 2 || i === all.length - 1);
  const hasSpread = series.some((line) => line.spread);
  const hasLabels = series.some((line) => line.pointLabels);
  return <div className="plot" ref={plot}>
    {yTitle && <div className="axis-name">{yTitle}</div>}
    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={title}>
      <title>{title}</title>
      {ySteps.map((v) => <g key={v}>
        <line x1={left} x2={right} y1={y(v)} y2={y(v)} className="gridline" />
        <text x={left - 8} y={y(v) + 4} textAnchor="end">{yLabel(v)}</text>
      </g>)}
      <line x1={left} x2={right} y1={bottom} y2={bottom} className="plot-axis" />
      {referenceY !== undefined && <line x1={left} x2={right} y1={y(referenceY)} y2={y(referenceY)} className="diagonal" />}
      {xSteps.map((v) => <text key={v} x={x(v)} y={bottom + 18} textAnchor="middle">{xLabels(v)}</text>)}
      {diagonal && <path d={`M ${x(rangeX[0])},${y(rangeX[0])} L ${x(rangeX[1])},${y(rangeX[1])}`} className="diagonal" />}
      <g>{series.map((line, i) => {
        const index = line.tone ?? i;
        return <g key={line.name} className={`chart-series series-${index}`}>
          {!scatter && line.points.length > 1 && <polyline className="plot-line" strokeDasharray={dashes[index]}
            points={line.points.map(([a, b]) => `${x(a)},${y(b)}`).join(" ")} />}
          {line.points.length < 18 && line.points.map(([a, b], j) => {
            const band = line.spread?.[j];
            return <g key={j}>
              {band && <path className="plot-whisker" fill="none" d={`M${x(a) - 4} ${y(band[0])}h8 M${x(a)} ${y(band[0])}V${y(band[1])} M${x(a) - 4} ${y(band[1])}h8`} />}
              <Mark index={index} x={x(a)} y={y(b)}>
                <title>{line.name} · {xValue(a)} · {yValue(b)}{band && ` · ${yValue(band[0])}–${yValue(band[1])}`}
                  {line.pointLabels?.[j] && ` · ${line.pointLabels[j]}`}</title>
              </Mark>
              {line.annotation && <text className="plot-annotation" x={x(a)} y={y(b) + (line.annotationBelow ? 18 : -10)}
                textAnchor={x(a) - left < 30 ? "start" : "middle"}>{line.annotation}</text>}
            </g>;
          })}
        </g>;
      })}</g>
    </svg>
    {xTitle && <div className="axis-name x-axis">{xTitle}</div>}
    <div className="legend">{series.map((line, i) => {
      const index = line.tone ?? i;
      return <span key={line.name} className={`chart-series series-${index}`}>
        <svg width="20" height="14" aria-hidden="true">{scatter || line.points.length === 1 ? <Mark index={index} x={10} y={7} />
          : <path d="M1 7H19" className="plot-line" strokeDasharray={dashes[index]} />}</svg>
        {line.name}
      </span>;
    })}</div>
    {legendNote && <p className="chart-detail">{legendNote}</p>}
    <details className="provenance" onToggle={(event) => setDataOpen(event.currentTarget.open)}>
      <summary>Chart values</summary>
      {dataOpen && <Table caption={title} numeric={[1, 2]}
        headings={["Series", xTitle ?? "X", yTitle ?? "Y",
          ...(hasSpread ? ["2.5th–97.5th percentiles"] : []), ...(hasLabels ? ["Details"] : [])]}
        rows={series.flatMap((line) => line.points.map(([a, b], j) => {
          const band = line.spread?.[j];
          return [line.name, xValue(a), yValue(b),
            ...(hasSpread ? [band ? band.map(yValue).join("–") : "—"] : []),
            ...(hasLabels ? [line.pointLabels?.[j] ?? "—"] : [])];
        }))} />}
    </details>
  </div>;
}

export function IntervalChart({ label, estimate, bounds, format }: {
  label: string; estimate: number; bounds: [number, number] | null; format: (value: number) => string;
}) {
  if (!bounds) return <Empty text={`${label} interval unavailable.`} />;
  const edge = Math.max(Math.abs(bounds[0]), Math.abs(bounds[1]), Math.abs(estimate)) * 1.14 || 1;
  const x = (v: number) => 50 + v / edge * 48;
  return <div className="interval-chart">
    <p><strong>{label}</strong><span>{format(estimate)}</span></p>
    <svg role="img" aria-label={`${label}: estimate ${format(estimate)}, interval ${bounds.map(format).join(" to ")}`}>
      <line x1="50%" x2="50%" y1="1" y2="21" className="diagonal" />
      <g className="chart-series series-0">
        <line x1={`${x(bounds[0])}%`} x2={`${x(bounds[1])}%`} y1="11" y2="11" className="plot-whisker" />
        {bounds.map((v, i) => <line key={i} x1={`${x(v)}%`} x2={`${x(v)}%`} y1="7" y2="15" className="plot-whisker" />)}
        <circle cx={`${x(estimate)}%`} cy="11" r="4.5" className="plot-mark" />
      </g>
    </svg>
    <div className="interval-scale" aria-hidden="true"><span>{format(-edge)}</span><span>0</span><span>{format(edge)}</span></div>
  </div>;
}
