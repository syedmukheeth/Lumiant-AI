"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, type TooltipContentProps } from "recharts";

import { AXIS, ChartFrame, Legend, TooltipCard, VIZ, compactTick } from "@/components/viz/shared";

export type StackSeries = { key: string; label: string; color?: string };
export type StackRow = { label: string; values: Record<string, number>; exact: Record<string, string>; total?: string };

/** Parts of each whole side by side (value by warehouse split by stage). All parts share one currency or unit. */
export function StackedBars({ rows, series, label, height = 260 }: { rows: StackRow[]; series: StackSeries[]; label: string; height?: number }) {
  const data = rows.map((r) => ({ label: r.label, ...r.values }));
  const byLabel = new Map(rows.map((r) => [r.label, r]));
  const color = (i: number, s: StackSeries) => s.color ?? VIZ[i % VIZ.length];
  return (
    <ChartFrame
      label={label}
      height={height}
      table={{ columns: ["Group", ...series.map((s) => s.label), "Total"], rows: rows.map((r) => [r.label, ...series.map((s) => r.exact[s.key] ?? ""), r.total ?? ""]) }}
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 8, bottom: 0, left: 0 }} barCategoryGap={8}>
          <CartesianGrid horizontal={false} stroke="var(--viz-grid)" />
          <XAxis type="number" {...AXIS} tickFormatter={compactTick} tickCount={4} />
          <YAxis type="category" dataKey="label" {...AXIS} width={112} />
          <Tooltip
            cursor={{ fill: "var(--viz-cursor)" }}
            content={({ active, label: l }: TooltipContentProps) => {
              const r = active ? byLabel.get(String(l)) : undefined;
              return r ? (
                <TooltipCard
                  title={r.label}
                  lines={[
                    ...series.map((s, i) => ({ label: s.label, value: r.exact[s.key] ?? "–", color: color(i, s) })),
                    ...(r.total ? [{ label: "Total", value: r.total }] : []),
                  ]}
                />
              ) : null;
            }}
          />
          {series.map((s, i) => (
            <Bar
              key={s.key}
              dataKey={s.key}
              stackId="a"
              fill={color(i, s)}
              stroke="var(--surface)"
              strokeWidth={1}
              radius={i === series.length - 1 ? [0, 4, 4, 0] : 0}
              isAnimationActive={false}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
      <Legend items={series.map((s, i) => ({ label: s.label, color: color(i, s) }))} />
    </ChartFrame>
  );
}
