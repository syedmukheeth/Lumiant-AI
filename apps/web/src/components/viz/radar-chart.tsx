"use client";

import { PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart as RRadarChart, ResponsiveContainer, Tooltip, type TooltipContentProps } from "recharts";

import { ChartFrame, Legend, TooltipCard, VIZ } from "@/components/viz/shared";

/** Scores 0–100 per axis (higher is better on every axis, so lead time is shown as "lead-time score"). */
export type RadarSeries = { name: string; scores: Record<string, number>; exact: Record<string, string>; color?: string };

/** Compare up to three suppliers (or items) across the same scorecard axes. */
export function RadarChart({ axes, series, label, height = 280 }: { axes: string[]; series: RadarSeries[]; label: string; height?: number }) {
  const shown = series.slice(0, 3);
  const data = axes.map((a) => ({ axis: a, ...Object.fromEntries(shown.map((s) => [s.name, s.scores[a] ?? 0])) }));
  const color = (i: number, s: RadarSeries) => s.color ?? VIZ[i];
  return (
    <ChartFrame
      label={label}
      height={height}
      table={{ columns: ["Measure", ...shown.map((s) => s.name)], rows: axes.map((a) => [a, ...shown.map((s) => s.exact[a] ?? "")]) }}
    >
      <ResponsiveContainer width="100%" height="100%">
        <RRadarChart data={data} outerRadius="72%">
          <PolarGrid stroke="var(--viz-grid)" />
          <PolarAngleAxis dataKey="axis" tick={{ fill: "var(--ink-2)", fontSize: 11 }} />
          <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
          <Tooltip
            content={({ active, label: l }: TooltipContentProps) =>
              active ? <TooltipCard title={String(l)} lines={shown.map((s, i) => ({ label: s.name, value: s.exact[String(l)] ?? "—", color: color(i, s) }))} /> : null
            }
          />
          {shown.map((s, i) => (
            <Radar key={s.name} dataKey={s.name} stroke={color(i, s)} fill={color(i, s)} fillOpacity={0.14} strokeWidth={1.75} isAnimationActive={false} />
          ))}
        </RRadarChart>
      </ResponsiveContainer>
      <Legend items={shown.map((s, i) => ({ label: s.name, color: color(i, s) }))} />
    </ChartFrame>
  );
}
