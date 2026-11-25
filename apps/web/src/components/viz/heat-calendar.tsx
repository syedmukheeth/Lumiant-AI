"use client";

import { ChartFrame, MONTHS, SEQ } from "@/components/viz/shared";

export type CalendarDay = { date: string; value: number; exact: string };

const DAY = 86_400_000;
const CELL = 13;
const GAP = 3;

function parse(d: string) {
  return Date.UTC(Number(d.slice(0, 4)), Number(d.slice(5, 7)) - 1, Number(d.slice(8, 10)));
}

/**
 * Activity by day (expiries, receipts): one square per day, weeks as columns, Monday first. Colour steps are the
 * quintiles of the shown values; days without data are left neutral, never shown as zero.
 */
export function HeatCalendar({ days, label, unitLabel = "value" }: { days: CalendarDay[]; label: string; unitLabel?: string }) {
  if (days.length === 0) return null;
  const sorted = [...days].sort((a, b) => a.date.localeCompare(b.date));
  const start = parse(sorted[0].date);
  const end = parse(sorted[sorted.length - 1].date);
  const startDow = (new Date(start).getUTCDay() + 6) % 7; // Monday = 0
  const origin = start - startDow * DAY;
  const weeks = Math.floor((end - origin) / DAY / 7) + 1;
  const byDate = new Map(sorted.map((d) => [d.date, d]));
  const positive = sorted.map((d) => d.value).filter((v) => v > 0).sort((a, b) => a - b);
  const q = (p: number) => positive[Math.min(positive.length - 1, Math.floor(p * positive.length))] ?? 0;
  const cuts = [q(0.2), q(0.4), q(0.6), q(0.8)];
  const step = (v: number) => (v <= 0 ? 0 : 1 + cuts.filter((c) => v > c).length) as 0 | 1 | 2 | 3 | 4 | 5;
  const width = weeks * (CELL + GAP) + 24;
  const height = 7 * (CELL + GAP) + 18;
  const months: { x: number; text: string }[] = [];
  for (let w = 0; w < weeks; w++) {
    const day = new Date(origin + w * 7 * DAY);
    if (day.getUTCDate() <= 7) months.push({ x: 24 + w * (CELL + GAP), text: MONTHS[day.getUTCMonth()] });
  }

  return (
    <ChartFrame label={label} table={{ columns: ["Date", unitLabel], rows: sorted.map((d) => [d.date, d.exact]) }}>
      <div className="overflow-x-auto pb-1">
        <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className="block">
          {months.map((m) => (
            <text key={`${m.x}`} x={m.x} y={10} fill="var(--ink-3)" fontSize={10}>
              {m.text}
            </text>
          ))}
          {["Mon", "", "Wed", "", "Fri", "", ""].map((d, i) =>
            d ? (
              <text key={d} x={0} y={18 + i * (CELL + GAP) + CELL - 3} fill="var(--ink-3)" fontSize={10}>
                {d}
              </text>
            ) : null,
          )}
          {Array.from({ length: weeks * 7 }, (_, i) => {
            const t = origin + i * DAY;
            if (t < start || t > end) return null;
            const iso = new Date(t).toISOString().slice(0, 10);
            const d = byDate.get(iso);
            const s = d ? step(d.value) : 0;
            const x = 24 + Math.floor(i / 7) * (CELL + GAP);
            const y = 18 + (i % 7) * (CELL + GAP);
            return (
              <rect key={iso} x={x} y={y} width={CELL} height={CELL} rx={3} fill={s === 0 ? "var(--surface-2)" : SEQ[s - 1]} stroke="var(--line)" strokeWidth={s === 0 ? 1 : 0}>
                <title>{d ? `${iso}: ${d.exact}` : `${iso}: no data`}</title>
              </rect>
            );
          })}
        </svg>
      </div>
      <div className="mt-2 flex items-center gap-1.5 text-caption text-ink-3" aria-hidden>
        Less
        {SEQ.map((c) => (
          <span key={c} className="size-2.5 rounded-sm" style={{ background: c }} />
        ))}
        More
      </div>
    </ChartFrame>
  );
}
