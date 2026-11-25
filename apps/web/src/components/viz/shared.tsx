"use client";

import { clsx } from "clsx";

/**
 * Chart kit rules (docs/05-plan/PRODUCT_V2_PLAN.md §4):
 * - Numbers drive geometry only; every printed value (labels, tooltips, the hidden table) is the exact string the
 *   API sent, so nothing is re-rounded or summed for display in the browser.
 * - Colours come from tokens (`--viz-*` categorical, `--seq-*` sequential, `--div-*` diverging, `--status-*`).
 * - Every chart has a text alternative: an accessible label and a visually hidden data table.
 * - Recharts animation stays off (frames never run in a hidden tab, ISSUES #10); entrances are CSS (`.rise`).
 */

export type TableAlt = { columns: string[]; rows: (string | number)[][] };

export const VIZ = ["var(--viz-1)", "var(--viz-2)", "var(--viz-3)", "var(--viz-4)", "var(--viz-5)"];
export const SEQ = ["var(--seq-1)", "var(--seq-2)", "var(--seq-3)", "var(--seq-4)", "var(--seq-5)"];
/** Text colour that stays readable on the matching SEQ step. */
export const SEQ_INK = ["var(--seq-ink-1)", "var(--seq-ink-2)", "var(--seq-ink-3)", "var(--seq-ink-4)", "var(--seq-ink-5)"];

export const AXIS = {
  stroke: "var(--viz-axis)",
  tick: { fill: "var(--ink-3)", fontSize: 11 },
  tickLine: false,
  axisLine: false,
} as const;

export function ChartFrame({
  label,
  table,
  height,
  className,
  children,
}: {
  /** One sentence that says what the chart shows (read by screen readers instead of the picture). */
  label: string;
  table: TableAlt;
  height?: number;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <figure className={clsx("rise relative min-w-0", className)}>
      <div role="img" aria-label={label} style={height ? { height } : undefined} className="min-w-0">
        {children}
      </div>
      {/* sr-only on the wrapper: a <table> ignores the 1px width and would widen the page. */}
      <div className="sr-only">
        <table>
        <caption>{label}</caption>
        <thead>
          <tr>
            {table.columns.map((c) => (
              <th key={c} scope="col">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {table.rows.map((r, i) => (
            <tr key={i}>
              {r.map((v, j) => (
                <td key={j}>{v}</td>
              ))}
            </tr>
          ))}
        </tbody>
        </table>
      </div>
    </figure>
  );
}

/** The one tooltip card every chart uses. */
export function TooltipCard({ title, lines }: { title?: string; lines: { label: string; value: string; color?: string }[] }) {
  return (
    <div className="min-w-36 rounded-control border border-line-strong bg-surface-3 px-2.5 py-2 text-xs shadow-e2">
      {title && <p className="mb-1 font-medium text-ink">{title}</p>}
      <ul className="space-y-0.5">
        {lines.map((l) => (
          <li key={l.label} className="flex items-center gap-2 text-ink-2">
            {l.color && <span className="size-2 shrink-0 rounded-full" style={{ background: l.color }} aria-hidden />}
            <span className="min-w-0 flex-1 truncate">{l.label}</span>
            <span className="figure font-medium text-ink">{l.value}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Legend as text chips (colour is never the only cue: each series is also named). */
export function Legend({ items }: { items: { label: string; color: string; dashed?: boolean }[] }) {
  return (
    <ul className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-caption text-ink-3">
      {items.map((i) => (
        <li key={i.label} className="flex items-center gap-1.5">
          <span
            className={clsx("h-0.5 w-3 rounded-full", i.dashed && "opacity-70")}
            style={{ background: i.dashed ? `repeating-linear-gradient(90deg, ${i.color} 0 3px, transparent 3px 5px)` : i.color }}
            aria-hidden
          />
          {i.label}
        </li>
      ))}
    </ul>
  );
}

/** Compact axis labels from geometry numbers (1.2M, 340K). Axis ticks only, never data labels. */
export function compactTick(v: number) {
  return new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 1 }).format(v);
}

/** Rounds an axis bound out to a multiple of half its power of ten (53,550 → 55,000), geometry only. */
export function niceCeil(v: number) {
  if (v <= 0) return 0;
  const step = 10 ** Math.floor(Math.log10(v)) / 2;
  return Math.ceil(v / step) * step;
}

export function niceFloor(v: number) {
  if (v <= 0) return 0;
  const step = 10 ** Math.floor(Math.log10(v)) / 2;
  return Math.floor(v / step) * step;
}

/** Fixed English month names: locale-formatted dates differ between server and browser (hydration). */
export const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2026-12-05" → "5 Dec" (UTC, no locale), identical on server and client. */
export function shortDate(iso: string) {
  return `${Number(iso.slice(8, 10))} ${MONTHS[Number(iso.slice(5, 7)) - 1]}`;
}
