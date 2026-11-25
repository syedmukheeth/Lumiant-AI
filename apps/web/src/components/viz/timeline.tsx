"use client";

import { clsx } from "clsx";

import { ChartFrame, shortDate } from "@/components/viz/shared";

type Tone = "neutral" | "accent" | "ai" | "warning" | "critical";
const TONE: Record<Tone, string> = {
  neutral: "bg-surface-3 border-line-strong text-ink-2",
  accent: "bg-accent-soft border-accent/40 text-accent",
  ai: "bg-ai-soft border-ai-line text-ink",
  warning: "bg-status-warning/15 border-status-warning/50 text-ink",
  critical: "bg-status-critical/15 border-status-critical/50 text-ink",
};

export type TimelineBar = { label: string; start: string; end: string; tone?: Tone; note?: string };
export type TimelineLane = { id: string; label: string; bars: TimelineBar[]; markers?: { date: string; label: string }[] };

const DAY = 86_400_000;
const t = (d: string) => Date.parse(`${d}T00:00:00Z`);

/**
 * Time-phased plan (purchase orders, MRP shortages, commitment dates) as lanes. A marker is a due date; a bar that
 * ends after its lane's marker is the caller's "late" tone. Dates print in full in the hidden table and on hover.
 */
export function Timeline({ lanes, from, to, label, today }: { lanes: TimelineLane[]; from: string; to: string; label: string; today?: string }) {
  const t0 = t(from);
  const span = Math.max(t(to) - t0, DAY);
  const pct = (d: string) => `${Math.min(100, Math.max(0, ((t(d) - t0) / span) * 100))}%`;
  const ticks: string[] = [];
  // Weekly ticks; none in the last few days, where a centred label would be clipped at the edge.
  for (let x = t0; x <= t(to) - 3 * DAY; x += 7 * DAY) ticks.push(new Date(x).toISOString().slice(0, 10));
  return (
    <ChartFrame
      label={label}
      table={{
        columns: ["Lane", "Bar", "Start", "End", "Note"],
        rows: lanes.flatMap((l) => l.bars.map((b) => [l.label, b.label, b.start, b.end, b.note ?? ""])),
      }}
    >
      <div className="min-w-0 overflow-x-auto">
        <div className="min-w-[36rem]">
          <div className="relative ml-36 h-5 border-b border-line text-caption text-ink-3">
            {ticks.map((d) => (
              <span key={d} className="absolute -translate-x-1/2 figure" style={{ left: pct(d) }}>
                {shortDate(d)}
              </span>
            ))}
          </div>
          <ul className="relative">
            {today && <li aria-hidden className="pointer-events-none absolute inset-y-0 z-10 ml-36 w-[calc(100%-9rem)]"><span className="absolute inset-y-0 w-px bg-ai" style={{ left: pct(today) }} /></li>}
            {lanes.map((l) => (
              <li key={l.id} className="flex h-10 items-center border-b border-line/70 last:border-0">
                <span className="w-36 shrink-0 truncate pr-3 text-xs text-ink-2" title={l.label}>
                  {l.label}
                </span>
                <div className="relative h-full flex-1">
                  {ticks.map((d) => (
                    <span key={d} className="absolute inset-y-0 w-px bg-line/60" style={{ left: pct(d) }} aria-hidden />
                  ))}
                  {l.bars.map((b) => {
                    const narrow = (t(b.end) - t(b.start)) / span < 0.18; // too short for its label: print it after the bar
                    return (
                      <span key={b.label + b.start} title={`${b.label}: ${b.start} → ${b.end}${b.note ? ` · ${b.note}` : ""}`}>
                        <span
                          className={clsx("absolute top-2 flex h-6 items-center truncate rounded-control border px-2 text-caption font-medium", TONE[b.tone ?? "neutral"])}
                          style={{ left: pct(b.start), width: `calc(${pct(b.end)} - ${pct(b.start)})`, minWidth: "0.5rem" }}
                        >
                          {narrow ? null : b.label}
                        </span>
                        {narrow && (
                          <span className="absolute top-2 flex h-6 items-center pl-1.5 text-caption font-medium whitespace-nowrap text-ink-2" style={{ left: pct(b.end) }}>
                            {b.label}
                          </span>
                        )}
                      </span>
                    );
                  })}
                  {l.markers?.map((m) => (
                    <span key={m.label} title={`${m.label}: ${m.date}`} className="absolute top-1 bottom-1 w-0.5 rounded-full bg-status-critical" style={{ left: pct(m.date) }} />
                  ))}
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </ChartFrame>
  );
}
