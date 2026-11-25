"use client";

import { Bar, CartesianGrid, ComposedChart, Line, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis, type TooltipContentProps } from "recharts";

import { AXIS, ChartFrame, Legend, TooltipCard, compactTick } from "@/components/viz/shared";

/** Items ranked by value. The cumulative share comes from the API (concentration analysis); the browser never sums. */
export type ParetoItem = { label: string; value: number; exact: string; cumulativePct: number; cumulativeExact: string };

/**
 * Pareto (ABC) curve: value bars by rank, the cumulative share as a line, and the class bands shaded.
 * `bands` are the cumulative-share cut-offs that end class A and class B (as configured, never assumed).
 */
export function ParetoChart({ items, bands, label, height = 260 }: { items: ParetoItem[]; bands?: [number, number]; label: string; height?: number }) {
  const data = items.map((it, i) => ({ ...it, rank: i + 1 }));
  const cutA = bands ? data.find((d) => d.cumulativePct >= bands[0])?.rank : undefined;
  const cutB = bands ? data.find((d) => d.cumulativePct >= bands[1])?.rank : undefined;
  return (
    <ChartFrame
      label={label}
      height={height}
      table={{ columns: ["Rank", "Item", "Value", "Cumulative share"], rows: data.map((d) => [d.rank, d.label, d.exact, d.cumulativeExact]) }}
    >
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 8, right: 4, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} stroke="var(--viz-grid)" />
          {cutA && <ReferenceArea yAxisId="v" x1={1} x2={cutA} fill="var(--accent)" fillOpacity={0.05} label={{ value: "A", position: "insideTopLeft", fill: "var(--ink-3)", fontSize: 11 }} />}
          {cutA && cutB && <ReferenceArea yAxisId="v" x1={cutA} x2={cutB} fill="var(--ai)" fillOpacity={0.05} label={{ value: "B", position: "insideTopLeft", fill: "var(--ink-3)", fontSize: 11 }} />}
          {cutB && <ReferenceArea yAxisId="v" x1={cutB} x2={data.length} fill="var(--ink-3)" fillOpacity={0.04} label={{ value: "C", position: "insideTopLeft", fill: "var(--ink-3)", fontSize: 11 }} />}
          <XAxis dataKey="rank" type="number" domain={[1, data.length]} {...AXIS} tickCount={6} allowDecimals={false} />
          <YAxis yAxisId="v" {...AXIS} width={44} tickFormatter={compactTick} tickCount={4} />
          <YAxis yAxisId="p" orientation="right" domain={[0, 100]} {...AXIS} width={36} tickFormatter={(v: number) => `${v}%`} ticks={[0, 50, 80, 100]} />
          <Tooltip
            cursor={{ fill: "var(--viz-cursor)" }}
            content={({ active, payload }: TooltipContentProps) => {
              const d = active ? (payload?.[0]?.payload as (typeof data)[number] | undefined) : undefined;
              return d ? (
                <TooltipCard
                  title={`#${d.rank} ${d.label}`}
                  lines={[
                    { label: "Value", value: d.exact, color: "var(--viz-1)" },
                    { label: "Cumulative share", value: d.cumulativeExact, color: "var(--ai)" },
                  ]}
                />
              ) : null;
            }}
          />
          <Bar yAxisId="v" dataKey="value" fill="var(--viz-1)" radius={[3, 3, 0, 0]} maxBarSize={14} isAnimationActive={false} />
          <Line yAxisId="p" dataKey="cumulativePct" stroke="var(--ai)" strokeWidth={2} dot={false} type="monotone" isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
      <Legend items={[{ label: "Value by item", color: "var(--viz-1)" }, { label: "Cumulative share of value", color: "var(--ai)" }]} />
    </ChartFrame>
  );
}
