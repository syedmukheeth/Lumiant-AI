"use client";

import { useId } from "react";
import { Area, AreaChart, CartesianGrid, Line, ResponsiveContainer, Tooltip, XAxis, YAxis, type TooltipContentProps } from "recharts";

import { AXIS, ChartFrame, Legend, TooltipCard, VIZ, compactTick } from "@/components/viz/shared";

export type TrendSeries = { key: string; label: string; color?: string; dashed?: boolean };
/** One period: a label plus, per series key, a geometry number and its exact display string (`exact[key]`). */
export type TrendRow = { label: string; values: Record<string, number>; exact: Record<string, string> };

/**
 * Change over time: the first series is a filled area, others are lines (a dashed line reads as a target or
 * comparison). Values in one chart must share a currency or unit; the caller says which in the label.
 */
export function TrendArea({ rows, series, label, height = 240 }: { rows: TrendRow[]; series: TrendSeries[]; label: string; height?: number }) {
  const id = useId().replace(/:/g, "");
  const data = rows.map((r) => ({ label: r.label, ...r.values }));
  const color = (i: number, s: TrendSeries) => s.color ?? VIZ[i % VIZ.length];
  const byLabel = new Map(rows.map((r) => [r.label, r]));
  const [first, ...rest] = series;
  return (
    <ChartFrame
      label={label}
      height={height}
      table={{ columns: ["Period", ...series.map((s) => s.label)], rows: rows.map((r) => [r.label, ...series.map((s) => r.exact[s.key] ?? "")]) }}
    >
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id={`trend-${id}`} x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor={color(0, first)} stopOpacity={0.32} />
              <stop offset="100%" stopColor={color(0, first)} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid vertical={false} stroke="var(--viz-grid)" />
          <XAxis dataKey="label" {...AXIS} minTickGap={16} />
          <YAxis {...AXIS} width={44} tickFormatter={compactTick} tickCount={4} />
          <Tooltip
            cursor={{ stroke: "var(--line-strong)" }}
            content={({ active, label: l }: TooltipContentProps) => {
              const row = active ? byLabel.get(String(l)) : undefined;
              return row ? (
                <TooltipCard title={row.label} lines={series.map((s, i) => ({ label: s.label, value: row.exact[s.key] ?? "—", color: color(i, s) }))} />
              ) : null;
            }}
          />
          <Area type="monotone" dataKey={first.key} stroke={color(0, first)} strokeWidth={2} fill={`url(#trend-${id})`} isAnimationActive={false} activeDot={{ r: 3.5 }} />
          {rest.map((s, i) => (
            <Line
              key={s.key}
              type="monotone"
              dataKey={s.key}
              stroke={color(i + 1, s)}
              strokeWidth={1.75}
              strokeDasharray={s.dashed ? "4 3" : undefined}
              dot={false}
              isAnimationActive={false}
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>
      {series.length > 1 && <Legend items={series.map((s, i) => ({ label: s.label, color: color(i, s), dashed: s.dashed }))} />}
    </ChartFrame>
  );
}
