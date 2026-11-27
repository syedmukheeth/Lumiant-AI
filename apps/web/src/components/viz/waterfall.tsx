"use client";

import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis, type TooltipContentProps } from "recharts";

import { AXIS, ChartFrame, TooltipCard, compactTick, niceCeil, niceFloor } from "@/components/viz/shared";

/** One step: a total (`kind: "total"`) or a change from the previous total. `exact` is what is printed. */
export type WaterfallStep = { label: string; value: number; exact: string; kind: "total" | "change" };

/**
 * How one figure becomes another (moving average → FIFO → standard cost). Bar positions are geometry built from the
 * step values; every printed figure is the exact string from the API.
 */
/** Bar geometry: each change floats between the running level before and after it. */
function layout(steps: WaterfallStep[]) {
  const out: (WaterfallStep & { base: number; bar: number })[] = [];
  let level = 0;
  for (const s of steps) {
    if (s.kind === "total") {
      level = s.value;
      out.push({ ...s, base: 0, bar: s.value });
    } else {
      const next = level + s.value;
      out.push({ ...s, base: Math.min(level, next), bar: Math.abs(s.value) });
      level = next;
    }
  }
  return out;
}

export function Waterfall({ steps, label, height = 240 }: { steps: WaterfallStep[]; label: string; height?: number }) {
  const data = layout(steps);
  // Start the axis near the lowest level so small changes stay visible; totals simply run off the bottom.
  const lows = data.map((d) => (d.kind === "total" ? d.value : d.base));
  const highs = data.map((d) => (d.kind === "total" ? d.value : d.base + d.bar));
  const lo = niceFloor(Math.min(...lows) * 0.9);
  const hi = niceCeil(Math.max(...highs) * 1.02);
  const fill = (s: WaterfallStep) => (s.kind === "total" ? "var(--viz-1)" : s.value >= 0 ? "var(--div-neg)" : "var(--div-pos)");
  return (
    <ChartFrame label={label} height={height} table={{ columns: ["Step", "Amount"], rows: steps.map((s) => [s.label, s.exact]) }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} stroke="var(--viz-grid)" />
          <XAxis dataKey="label" {...AXIS} interval={0} />
          <YAxis {...AXIS} width={44} tickFormatter={compactTick} tickCount={5} domain={[lo, hi]} allowDataOverflow />
          <Tooltip
            cursor={{ fill: "var(--viz-cursor)" }}
            content={({ active, payload }: TooltipContentProps) => {
              const s = active ? (payload?.[0]?.payload as WaterfallStep | undefined) : undefined;
              return s ? <TooltipCard title={s.label} lines={[{ label: s.kind === "total" ? "Amount" : "Change", value: s.exact, color: fill(s) }]} /> : null;
            }}
          />
          <Bar dataKey="base" stackId="w" fill="transparent" isAnimationActive={false} />
          <Bar dataKey="bar" stackId="w" radius={[4, 4, 0, 0]} isAnimationActive={false}>
            {data.map((d) => (
              <Cell key={d.label} fill={fill(d)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}
