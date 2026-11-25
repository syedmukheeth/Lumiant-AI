"use client";

import { clsx } from "clsx";
import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";

import { Sparkline } from "@/components/viz/sparkline";

type Direction = "up" | "down" | "flat";

/**
 * Change against the previous period. `text` is the exact change the API reports (e.g. "4.2%"); the chip only
 * decides colour and icon. Whether "up" is good depends on the metric (stock-outs up is bad).
 */
export function DeltaChip({ direction, text, goodWhen = "up", period }: { direction: Direction; text: string; goodWhen?: "up" | "down"; period?: string }) {
  const good = direction !== "flat" && direction === goodWhen;
  const bad = direction !== "flat" && direction !== goodWhen;
  const Icon = direction === "up" ? ArrowUpRight : direction === "down" ? ArrowDownRight : Minus;
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-caption font-medium",
        good && "bg-ok/10 text-ok",
        bad && "bg-status-critical/10 text-status-critical",
        !good && !bad && "bg-surface-2 text-ink-3",
      )}
    >
      <Icon className="size-3" aria-hidden />
      <span className="figure">{text}</span>
      <span className="sr-only">{direction === "flat" ? "no change" : direction === "up" ? "up" : "down"}</span>
      {period && <span className="font-normal text-ink-3">&nbsp;{period}</span>}
    </span>
  );
}

/** A hero KPI: label, exact figure, change, and the shape of the last periods. */
export function KpiCard({
  label,
  value,
  unit,
  delta,
  trend,
  tone = "accent",
  hint,
}: {
  label: string;
  value: string;
  unit?: string;
  delta?: { direction: Direction; text: string; goodWhen?: "up" | "down"; period?: string };
  trend?: number[];
  tone?: "accent" | "critical" | "muted";
  hint?: string;
}) {
  return (
    <div className="rise panel flex min-w-0 flex-col gap-3 p-4">
      <p className="eyebrow">{label}</p>
      <div className="flex items-end justify-between gap-3">
        <p className="kpi-fit min-w-0 text-kpi font-semibold text-ink figure">
          {value}
          {unit && <span className="ml-1 text-sm font-medium text-ink-3">{unit}</span>}
        </p>
        {trend && <Sparkline values={trend} tone={tone} label={`${label}: trend over the last ${trend.length} periods`} />}
      </div>
      <div className="flex min-h-5 items-center gap-2">
        {delta && <DeltaChip {...delta} />}
        {hint && <span className="truncate text-caption text-ink-3">{hint}</span>}
      </div>
    </div>
  );
}
