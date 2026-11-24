import { useId, useLayoutEffect, useRef, useState } from "react";
import type { ReactNode, RefObject } from "react";
import { Empty, Table } from "./components";
import { percent } from "./numbers";

export type Tone = "uniform" | "greedy" | "hybrid-5" | "hybrid-10" | "hybrid-20" | "stratified" | "adaptive"
  | "accent" | "neutral" | "ochre";

/** Every strategy keeps one color, marker and dash pattern across the workspace. */
export const strategyStyle: Record<string, { tone: Tone; marker: number; dash: number }> = {
  "hybrid-10": { tone: "hybrid-10", marker: 0, dash: 0 },
  greedy: { tone: "greedy", marker: 1, dash: 3 },
  uniform: { tone: "uniform", marker: 2, dash: 1 },
  "hybrid-5": { tone: "hybrid-5", marker: 3, dash: 2 },
  "hybrid-20": { tone: "hybrid-20", marker: 4, dash: 4 },
  stratified: { tone: "stratified", marker: 5, dash: 5 },
  adaptive: { tone: "adaptive", marker: 6, dash: 0 },
};
export const styleFor = (strategy: string) => strategyStyle[strategy.replace("fixed-", "hybrid-").replace("matched", "hybrid-10")]
  ?? { tone: "neutral" as Tone, marker: 0, dash: 0 };

export type Series = {
  name: string;
  points: [number, number][];
  tone: Tone;
  marker?: number;
  dash?: number;
  hollow?: boolean;
  emphasis?: "strong" | "muted";
  line?: boolean;
  label?: string;
  labelAt?: "above" | "below" | "left" | "right";
  spread?: ([number, number] | null)[];
  details?: string[];
  legend?: boolean;
};

const dashes = [undefined, "6 4", "2 3", "8 3 2 3", "12 4", "3 3 1 3"];
function markerPath(index: number, size: number) {
  const s = size;
  switch (index % 7) {
    case 1: return `M ${-s * .86} ${-s * .86} H ${s * .86} V ${s * .86} H ${-s * .86} Z`;
    case 2: return `M 0 ${-s * 1.2} L ${s * 1.2} 0 L 0 ${s * 1.2} L ${-s * 1.2} 0 Z`;
    case 3: return `M 0 ${-s * 1.2} L ${s * 1.1} ${s * .85} H ${-s * 1.1} Z`;
    case 4: return `M ${-s * 1.1} ${-s * .85} H ${s * 1.1} L 0 ${s * 1.2} Z`;
    case 5: {
      const a = s * .38, b = s * 1.05;
      return `M ${-a} ${-b} H ${a} V ${-a} H ${b} V ${a} H ${a} V ${b} H ${-a} V ${a} H ${-b} V ${-a} H ${-a} Z`;
    }
    case 6: {
      const a = s * .42, b = s * 1.05;
      return `M ${-b} ${-b + a} L ${-b + a} ${-b} L 0 ${-a} L ${b - a} ${-b} L ${b} ${-b + a} L ${a} 0 L ${b} ${b - a} `
        + `L ${b - a} ${b} L 0 ${a} L ${-b + a} ${b} L ${-b} ${b - a} L ${-a} 0 Z`;
    }
    default: return `M 0 ${-s} A ${s} ${s} 0 1 1 0 ${s} A ${s} ${s} 0 1 1 0 ${-s} Z`;
  }
}

function useWidth(fallback: number): [RefObject<HTMLDivElement | null>, number] {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(fallback);
  useLayoutEffect(() => {
    const element = ref.current;
    if (!element) return;
    const measure = () => setWidth(Math.max(240, Math.round(element.clientWidth)));
    const observer = new ResizeObserver(measure);
    measure();
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  return [ref, width];
}

export function LegendKey({ series, size = 4 }: { series: Pick<Series, "tone" | "marker" | "dash" | "hollow" | "line">; size?: number }) {
  const line = series.line !== false;
  return <svg width={line ? 24 : 16} height="14" aria-hidden="true" className={`tone-${series.tone}`}>
    {line && <path d="M1 7H23" className="plot-line" strokeDasharray={dashes[series.dash ?? 0]} />}
    <path className={`plot-mark${series.hollow ? " hollow" : ""}`} transform={`translate(${line ? 12 : 8} 7)`}
      d={markerPath(series.marker ?? 0, size)} />
  </svg>;
}

const axisPercent = (n: number) => percent(n, Math.abs(n * 100 - Math.round(n * 100)) > 1e-9 ? 1 : 0);

export function Plot({ title, series, rangeX, rangeY, xTicks, yTicks, xFormat = axisPercent, yFormat = axisPercent,
  xValue, yValue = (v: number) => percent(v, 2), xTitle, yTitle, xName, yName, diagonal = false, referenceY, guides = [],
  height = 260, caption, lead, legend = true, spreadLabel = "2.5th to 97.5th percentile" }: {
  title: string; series: Series[]; rangeX: [number, number]; rangeY: [number, number];
  xTicks?: number[]; yTicks?: number[]; xFormat?: (x: number) => string; yFormat?: (y: number) => string;
  xValue?: (x: number) => string; yValue?: (y: number) => string; xTitle?: string; yTitle?: string;
  xName?: string; yName?: string; diagonal?: boolean; referenceY?: number; guides?: { points: [number, number][]; label?: string }[];
  height?: number; caption?: ReactNode; lead?: ReactNode; legend?: boolean; spreadLabel?: string;
}) {
  const [frame, width] = useWidth(640);
  const [tip, setTip] = useState<{ x: number; y: number; title: string; lines: string[] } | null>(null);
  const captionId = useId();
  const formatX = xValue ?? xFormat;
  const xShort = xName ?? xTitle ?? "X", yShort = yName ?? yTitle ?? "Y";
  const tall = Math.round(Math.min(height, Math.max(200, width * .62)));
  const ySteps = yTicks ?? Array.from({ length: 5 }, (_, i) => rangeY[0] + i * (rangeY[1] - rangeY[0]) / 4);
  const left = Math.max(34, Math.max(...ySteps.map((value) => yFormat(value).length)) * 6.6 + 12);
  const right = width - 14, top = 10, bottom = tall - 26;
  const x = (v: number) => left + (v - rangeX[0]) / (rangeX[1] - rangeX[0]) * (right - left);
  const y = (v: number) => bottom - (v - rangeY[0]) / (rangeY[1] - rangeY[0]) * (bottom - top);
  const allTicks = xTicks ?? Array.from({ length: 5 }, (_, i) => rangeX[0] + i * (rangeX[1] - rangeX[0]) / 4);
  const crowded = (right - left) / Math.max(1, allTicks.length - 1) < 44;
  const xSteps = crowded ? allTicks.filter((_, i) => i % 2 === 0 || i === allTicks.length - 1) : allTicks;
  const hasSpread = series.some((line) => line.spread);
  const hasDetails = series.some((line) => line.details);
  const shown = series.filter((line) => line.legend !== false);
  const place = (line: Series, px: number, py: number) => {
    const at = line.labelAt ?? "above";
    let dx = 0, dy = -11, anchor: "start" | "middle" | "end" = "middle";
    if (at === "below") dy = 19;
    if (at === "right") { dx = 11; dy = 4; anchor = "start"; }
    if (at === "left") { dx = -11; dy = 4; anchor = "end"; }
    if (anchor === "middle" && px - left < 40) anchor = "start";
    if (anchor === "middle" && right - px < 40) anchor = "end";
    if (anchor === "start" && right - px < 90) { dx = -11; anchor = "end"; }
    return { x: px + dx, y: Math.max(top + 10, Math.min(bottom - 6, py + dy)), anchor };
  };
  // Place strong labels first and drop any label whose estimated box would overlap one already placed.
  const placed: { left: number; right: number; top: number; bottom: number }[] = [];
  const directLabels = series.filter((line) => line.label && line.points.length)
    .sort((a, b) => Number(b.emphasis === "strong") - Number(a.emphasis === "strong"))
    .flatMap((line) => {
      if (width < 480 && line.points.length > 1) return [];
      const [a, b] = line.points.at(-1)!;
      const spot = place(line, x(a), y(b));
      const span = line.label!.length * 6.6;
      const start = spot.anchor === "start" ? spot.x : spot.anchor === "end" ? spot.x - span : spot.x - span / 2;
      const box = { left: start - 3, right: start + span + 3, top: spot.y - 12, bottom: spot.y + 4 };
      if (placed.some((other) => box.left < other.right && box.right > other.left && box.top < other.bottom && box.bottom > other.top)) {
        return [];
      }
      placed.push(box);
      return [{ line, spot }];
    });
  const described = lead ?? caption;
  return <figure className="plot">
    {lead && <figcaption id={captionId} className="standfirst">{lead}</figcaption>}
    {legend && shown.length > 1 && <div className="plot-legend" aria-hidden="true">{shown.map((line) =>
      <span key={line.name} className={line.emphasis === "muted" ? "muted" : undefined}>
        <LegendKey series={{ ...line, line: line.line ?? line.points.length > 1 }} />{line.name}</span>)}
    </div>}
    {yTitle && <div className="axis-title y">{yTitle}</div>}
    <div className="plot-frame" ref={frame} onPointerLeave={() => setTip(null)}>
      <svg viewBox={`0 0 ${width} ${tall}`} role="img" aria-label={title} aria-describedby={described ? captionId : undefined}>
        {ySteps.map((v) => <g key={v}>
          <line x1={left} x2={right} y1={y(v)} y2={y(v)} className={v === rangeY[0] ? "plot-axis" : "gridline"} />
          <text x={left - 8} y={y(v) + 4} textAnchor="end">{yFormat(v)}</text>
        </g>)}
        {xSteps.map((v) => <g key={v}>
          <line x1={x(v)} x2={x(v)} y1={bottom} y2={bottom + 4} className="plot-axis" />
          <text x={x(v)} y={bottom + 18} textAnchor={x(v) - left < 12 ? "start" : right - x(v) < 12 ? "end" : "middle"}>{xFormat(v)}</text>
        </g>)}
        {referenceY !== undefined && <line x1={left} x2={right} y1={y(referenceY)} y2={y(referenceY)} className="reference" />}
        {diagonal && <path d={`M ${x(rangeX[0])} ${y(rangeX[0])} L ${x(rangeX[1])} ${y(rangeX[1])}`} className="reference" />}
        {guides.map((guide, i) => <g key={i}>
          <polyline className="guide" points={guide.points.map(([a, b]) => `${x(a)},${y(b)}`).join(" ")} />
        </g>)}
        {series.map((line) => {
          const showLine = line.line ?? line.points.length > 1;
          const marks = line.points.length <= 24;
          return <g key={line.name} className={`series tone-${line.tone}${line.emphasis ? ` ${line.emphasis}` : ""}`}>
            {showLine && <polyline className="plot-line" strokeDasharray={dashes[line.dash ?? 0]}
              points={line.points.map(([a, b]) => `${x(a)},${y(b)}`).join(" ")} />}
            {marks && line.points.map(([a, b], j) => {
              const band = line.spread?.[j];
              const lines = [`${xShort}: ${formatX(a)}`, `${yShort}: ${yValue(b)}`,
                ...(band ? [`${spreadLabel}: ${yValue(band[0])} to ${yValue(band[1])}`] : []),
                ...(line.details?.[j] ? [line.details[j]] : [])];
              return <g key={j}>
                {band && <path className="plot-whisker"
                  d={`M${x(a) - 4} ${y(band[0])}h8 M${x(a)} ${y(band[0])}V${y(band[1])} M${x(a) - 4} ${y(band[1])}h8`} />}
                <path className={`plot-mark${line.hollow ? " hollow" : ""}`} transform={`translate(${x(a)} ${y(b)})`}
                  d={markerPath(line.marker ?? 0, line.emphasis === "strong" ? 5.6 : 4.6)} />
                <circle className="plot-hit" cx={x(a)} cy={y(b)} r={11}
                  onPointerEnter={() => setTip({ x: x(a), y: y(b), title: line.name, lines })} />
              </g>;
            })}
          </g>;
        })}
        {directLabels.map(({ line, spot }) =>
          <text key={`label-${line.name}`} className={`direct-label${line.emphasis === "muted" ? " secondary" : ""}`}
            x={spot.x} y={spot.y} textAnchor={spot.anchor}>{line.label}</text>)}
        {guides.filter((guide) => guide.label).map((guide, i) => {
          const [a, b] = guide.points[Math.floor(guide.points.length / 2)];
          return <text key={`guide-${i}`} className="guide-label" x={x(a) + 8} y={y(b) - 8}>{guide.label}</text>;
        })}
      </svg>
      {tip && <div className="tooltip" style={{ left: Math.min(Math.max(tip.x, 80), width - 80), top: tip.y }} role="presentation">
        <strong>{tip.title}</strong>{tip.lines.map((text) => <span key={text}>{text}</span>)}
      </div>}
    </div>
    {xTitle && <div className="axis-title x">{xTitle}</div>}
    {caption && !lead && <figcaption id={captionId} className="plot-caption">{caption}</figcaption>}
    <details className="chart-data">
      <summary>Chart values</summary>
      <Table caption={title} numeric={[1, 2]}
        headings={["Series", xShort, yShort, ...(hasSpread ? [spreadLabel] : []), ...(hasDetails ? ["Details"] : [])]}
        rows={series.flatMap((line) => line.points.map(([a, b], j) => {
          const band = line.spread?.[j];
          return [line.name, formatX(a), yValue(b),
            ...(hasSpread ? [band ? `${yValue(band[0])} to ${yValue(band[1])}` : "Not shown"] : []),
            ...(hasDetails ? [line.details?.[j] ?? ""] : [])];
        }))} />
    </details>
  </figure>;
}

/** A paired interval with the frozen decision threshold it was judged against. */
export function IntervalPlot({ title, estimate, bounds, format, threshold, thresholdText, confidence = .975 }: {
  title: string; estimate: number; bounds: [number, number] | null; format: (value: number) => string;
  threshold?: number; thresholdText?: string; confidence?: number;
}) {
  const [frame, width] = useWidth(420);
  if (!bounds) return <Empty text={`${title}: interval unavailable.`} />;
  const values = [0, estimate, ...bounds, ...(threshold === undefined ? [] : [threshold])];
  const low = Math.min(...values), high = Math.max(...values);
  const pad = (high - low || 1) * .1;
  const left = 8, right = width - 8;
  const x = (v: number) => left + (v - (low - pad)) / ((high + pad) - (low - pad)) * (right - left);
  const labels: { at: number; text: string; cls?: string }[] = [];
  for (const candidate of [{ at: 0, text: format(0) }, { at: bounds[0], text: format(bounds[0]) }, { at: bounds[1], text: format(bounds[1]) }]) {
    if (labels.every((placed) => Math.abs(x(placed.at) - x(candidate.at)) > 52)) labels.push(candidate);
  }
  const description = `${title}: estimate ${format(estimate)}, ${Math.round(confidence * 1000) / 10}% interval `
    + `${format(bounds[0])} to ${format(bounds[1])}${thresholdText ? `. ${thresholdText}` : ""}.`;
  return <div className="interval">
    <div className="interval-head"><h3>{title}</h3>
      <p><strong>{format(estimate)}</strong> estimate, interval {format(bounds[0])} to {format(bounds[1])}</p></div>
    <div ref={frame}>
      <svg viewBox={`0 0 ${width} 58`} role="img" aria-label={description}>
        <rect className="band" x={x(bounds[0])} y={16} width={Math.max(1, x(bounds[1]) - x(bounds[0]))} height={14} rx={3} />
        <line className="axis" x1={left} x2={right} y1={42} y2={42} />
        <line className="zero" x1={x(0)} x2={x(0)} y1={10} y2={46} />
        {threshold !== undefined && <>
          <line className="threshold" x1={x(threshold)} x2={x(threshold)} y1={6} y2={46} />
          <text className="threshold-label" x={x(threshold) + (x(threshold) > width * .7 ? -6 : 6)} y={11}
            textAnchor={x(threshold) > width * .7 ? "end" : "start"}>{thresholdText ?? `Threshold ${format(threshold)}`}</text>
        </>}
        <line className="ci" x1={x(bounds[0])} x2={x(bounds[1])} y1={23} y2={23} />
        {bounds.map((v, i) => <line key={i} className="ci-cap" x1={x(v)} x2={x(v)} y1={17} y2={29} />)}
        <circle className="estimate" cx={x(estimate)} cy={23} r={5} />
        {labels.map((label) => <text key={label.text + label.at} x={x(label.at)} y={56}
          textAnchor={x(label.at) - left < 20 ? "start" : right - x(label.at) < 20 ? "end" : "middle"}>{label.text}</text>)}
      </svg>
    </div>
  </div>;
}

export function ThresholdBar({ label, value, limit, format }: {
  label: string; value: number; limit: number; format: (value: number) => string;
}) {
  const max = Math.max(limit * 1.5, value * 1.12);
  const over = value > limit;
  return <div className="threshold-bar" role="img"
    aria-label={`${label}: ${format(value)}, ${over ? "above" : "within"} the threshold of ${format(limit)}`}>
    <small aria-hidden="true">{label}</small>
    <div className="track" aria-hidden="true">
      <span className={`fill${over ? " over" : ""}`} style={{ width: `${Math.max(1.5, value / max * 100)}%` }} />
      <span className="limit" style={{ left: `${limit / max * 100}%` }} />
    </div>
    <span className="value" aria-hidden="true">{format(value)}</span>
  </div>;
}

const parse = (value: string) => new Date(`${value}T00:00:00Z`).getTime();
const monthFormat = new Intl.DateTimeFormat("en-US", { month: "short", year: "numeric", timeZone: "UTC" });

export function DelayTimeline({ rows, title }: {
  rows: { year: number; decision: string; available: string }[]; title: string;
}) {
  const [frame, width] = useWidth(420);
  const start = Math.min(...rows.map((row) => parse(row.decision))) - 120 * 864e5;
  const end = Math.max(...rows.map((row) => parse(row.available))) + 90 * 864e5;
  const left = 44, right = width - 8, rowHeight = 30, chartHeight = rows.length * rowHeight + 30;
  const x = (time: number) => left + (time - start) / (end - start) * (right - left);
  const first = new Date(start).getUTCFullYear() + 1, last = new Date(end).getUTCFullYear();
  const years = Array.from({ length: last - first + 1 }, (_, i) => first + i);
  const months = (row: { decision: string; available: string }) => Math.round((parse(row.available) - parse(row.decision)) / (30.44 * 864e5));
  const summary = rows.map((row) => `${row.year}: decision ${monthFormat.format(parse(row.decision))}, outcomes `
    + `${monthFormat.format(parse(row.available))}, ${months(row)} months`).join("; ");
  return <div className="plot" ref={frame}>
    <svg viewBox={`0 0 ${width} ${chartHeight}`} role="img" aria-label={`${title}. ${summary}.`}>
      {years.map((year) => {
        const at = x(Date.UTC(year, 0, 1));
        return <g key={year}><line className="gridline" x1={at} x2={at} y1={4} y2={chartHeight - 22} />
          <text x={at} y={chartHeight - 6} textAnchor="middle">{year}</text></g>;
      })}
      {rows.map((row, i) => {
        const cy = 18 + i * rowHeight, a = x(parse(row.decision)), b = x(parse(row.available));
        return <g key={row.year} className="series tone-accent">
          <text x={0} y={cy + 4} className="direct-label">{row.year}</text>
          <line x1={a} x2={b} y1={cy} y2={cy} className="plot-line" strokeOpacity={.45} strokeWidth={5} />
          <circle cx={a} cy={cy} r={4.5} className="plot-mark hollow" />
          <circle cx={b} cy={cy} r={4.5} className="plot-mark" />
          <text x={(a + b) / 2} y={cy - 8} textAnchor="middle">{months(row)} months</text>
        </g>;
      })}
    </svg>
  </div>;
}
