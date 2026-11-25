/**
 * Fixed sample values for the component showcase (/design) and the landing page. They are illustrations, never
 * tenant data, and every place that shows them says so. Deterministic (no randomness) so server and client match.
 */
import type { CalendarDay } from "@/components/viz/heat-calendar";
import type { ParetoItem } from "@/components/viz/pareto-chart";
import type { RadarSeries } from "@/components/viz/radar-chart";
import type { RiskPoint } from "@/components/viz/risk-matrix";
import type { StackRow, StackSeries } from "@/components/viz/stacked-bars";
import type { TimelineLane } from "@/components/viz/timeline";
import type { TreemapItem } from "@/components/viz/treemap";
import type { TrendRow, TrendSeries } from "@/components/viz/trend-area";
import type { WaterfallStep } from "@/components/viz/waterfall";

const money = (v: number) => `USD ${v.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
const months = ["Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov"];

const VALUE = [2.41, 2.46, 2.52, 2.49, 2.58, 2.63, 2.61, 2.7, 2.74, 2.69, 2.73, 2.77].map((m) => Math.round(m * 1_000_000));
const TARGET = VALUE.map(() => 2_500_000);
export const SAMPLE_TREND: { rows: TrendRow[]; series: TrendSeries[] } = {
  series: [
    { key: "value", label: "Inventory value" },
    { key: "target", label: "Target ceiling", color: "var(--ink-3)", dashed: true },
  ],
  rows: months.map((m, i) => ({
    label: m,
    values: { value: VALUE[i], target: TARGET[i] },
    exact: { value: money(VALUE[i]), target: money(TARGET[i]) },
  })),
};
export const SAMPLE_SPARK = VALUE.map((v) => v / 1000);

const PARETO_VALUES = [412, 318, 251, 198, 160, 131, 109, 92, 78, 66, 56, 48, 41, 35, 30, 26, 22, 19, 16, 14, 12, 10, 9, 8, 7, 6, 5, 4, 3, 2].map((v) => v * 1000);
const PARETO_TOTAL = PARETO_VALUES.reduce((a, b) => a + b, 0);
export const SAMPLE_PARETO: ParetoItem[] = PARETO_VALUES.map((v, i) => {
  const cum = (PARETO_VALUES.slice(0, i + 1).reduce((a, b) => a + b, 0) / PARETO_TOTAL) * 100;
  return { label: `Item ${String(i + 1).padStart(3, "0")}`, value: v, exact: money(v), cumulativePct: cum, cumulativeExact: `${cum.toFixed(1)}%` };
});

const GROUPS: [string, number][] = [
  ["Mechanical spares", 812],
  ["Electrical", 604],
  ["Rubber", 388],
  ["Temperature sensitive", 297],
  ["Fasteners", 214],
  ["Flammable", 161],
  ["Packaging", 92],
];
const GROUP_TOTAL = GROUPS.reduce((a, [, v]) => a + v, 0);
export const SAMPLE_TREEMAP: TreemapItem[] = GROUPS.map(([label, v]) => ({
  id: label,
  label,
  value: v * 1000,
  exact: money(v * 1000),
  share: `${((v / GROUP_TOTAL) * 100).toFixed(1)}%`,
}));

export const SAMPLE_STACK_SERIES: StackSeries[] = [
  { key: "raw", label: "Raw" },
  { key: "semi", label: "Semi-finished" },
  { key: "finished", label: "Finished" },
  { key: "spare", label: "Spares" },
];
const STACK: [string, number[]][] = [
  ["3100 Riyadh", [420, 180, 260, 140]],
  ["2100 Dammam", [310, 120, 190, 90]],
  ["1100 Jeddah", [260, 90, 210, 120]],
  ["4100 Yanbu", [140, 60, 80, 70]],
];
export const SAMPLE_STACK: StackRow[] = STACK.map(([label, vals]) => ({
  label,
  values: Object.fromEntries(SAMPLE_STACK_SERIES.map((s, i) => [s.key, vals[i] * 1000])),
  exact: Object.fromEntries(SAMPLE_STACK_SERIES.map((s, i) => [s.key, money(vals[i] * 1000)])),
  total: money(vals.reduce((a, b) => a + b, 0) * 1000),
}));

export const SAMPLE_RISK: RiskPoint[] = [
  [182, 410, 22],
  [95, 380, 14],
  [61, 300, 9],
  [140, 120, 18],
  [36, 520, 6],
  [22, 90, 4],
  [75, 210, 10],
  [12, 640, 3],
  [168, 260, 20],
  [48, 45, 7],
  [110, 330, 15],
  [28, 180, 5],
].map(([v, d, s], i) => ({
  id: `R${i}`,
  label: `Item ${String(i + 101)}`,
  x: d,
  y: v * 1000,
  xExact: `${d} days`,
  yExact: money(v * 1000),
  size: s,
}));

function calendar(): CalendarDay[] {
  const out: CalendarDay[] = [];
  const start = Date.UTC(2026, 5, 1);
  for (let i = 0; i < 182; i++) {
    const d = new Date(start + i * 86_400_000).toISOString().slice(0, 10);
    const v = (i * 37 + (i % 7) * 11) % 9 === 0 ? 0 : ((i * 13) % 17) + ((i * 7) % 5);
    out.push({ date: d, value: v, exact: `${v} lots` });
  }
  return out;
}
export const SAMPLE_CALENDAR = calendar();

export const SAMPLE_WATERFALL: WaterfallStep[] = [
  { label: "Moving avg", value: 48200, exact: "USD 48,200", kind: "total" },
  { label: "FIFO layers", value: 2600, exact: "+USD 2,600", kind: "change" },
  { label: "Lot cost", value: -1400, exact: "−USD 1,400", kind: "change" },
  { label: "Latest price", value: 3100, exact: "+USD 3,100", kind: "change" },
  { label: "Latest", value: 52500, exact: "USD 52,500", kind: "total" },
];

const AXES = ["Price", "Lead-time score", "On-time delivery", "Quality", "Capacity"];
const sup = (name: string, s: number[]): RadarSeries => ({
  name,
  scores: Object.fromEntries(AXES.map((a, i) => [a, s[i]])),
  exact: Object.fromEntries(AXES.map((a, i) => [a, `${s[i]} / 100`])),
});
export const SAMPLE_RADAR = { axes: AXES, series: [sup("Supplier A", [82, 64, 91, 88, 70]), sup("Supplier B", [94, 48, 72, 80, 85]), sup("Supplier C", [70, 90, 84, 76, 60])] };

export const SAMPLE_TIMELINE: { lanes: TimelineLane[]; from: string; to: string; today: string } = {
  from: "2026-11-23",
  to: "2027-01-18",
  today: "2026-11-25",
  lanes: [
    { id: "a", label: "SO-4821 · Pump assy", bars: [{ label: "PO-771 bearing", start: "2026-11-24", end: "2026-12-19", tone: "critical", note: "lands after due date" }], markers: [{ date: "2026-12-12", label: "Customer due" }] },
    { id: "b", label: "SO-4830 · Valve kit", bars: [{ label: "Transfer from 2100", start: "2026-11-26", end: "2026-12-03", tone: "accent" }], markers: [{ date: "2026-12-10", label: "Customer due" }] },
    { id: "c", label: "SO-4842 · Gasket set", bars: [{ label: "PO-779 rubber", start: "2026-12-01", end: "2026-12-29", tone: "warning", note: "4 days of slack" }], markers: [{ date: "2027-01-02", label: "Customer due" }] },
    { id: "d", label: "SO-4855 · Motor", bars: [{ label: "Alternate item", start: "2026-12-08", end: "2026-12-15", tone: "accent", note: "suggested option" }], markers: [{ date: "2026-12-20", label: "Customer due" }] },
  ],
};
