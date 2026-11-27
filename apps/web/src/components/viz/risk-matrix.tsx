"use client";

import { CartesianGrid, ReferenceArea, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis, type TooltipContentProps } from "recharts";

import { AXIS, ChartFrame, TooltipCard, compactTick, niceCeil } from "@/components/viz/shared";

export type RiskPoint = { id: string; label: string; x: number; y: number; xExact: string; yExact: string; size?: number };

/**
 * Two risk measures against each other (value at stake × days without movement). The quadrant beyond both splits
 * is shaded as the "act first" corner; every point is named in the tooltip and the hidden table.
 */
export function RiskMatrix({
  points,
  label,
  xLabel,
  yLabel,
  xSplit,
  ySplit,
  corner = "Act first",
  height = 280,
  onSelect,
}: {
  points: RiskPoint[];
  label: string;
  xLabel: string;
  yLabel: string;
  xSplit: number;
  ySplit: number;
  corner?: string;
  height?: number;
  onSelect?: (p: RiskPoint) => void;
}) {
  const xMax = niceCeil(Math.max(xSplit * 1.2, ...points.map((p) => p.x)));
  const yMax = niceCeil(Math.max(ySplit * 1.2, ...points.map((p) => p.y)));
  const hot = (p: RiskPoint) => p.x >= xSplit && p.y >= ySplit;
  return (
    <ChartFrame
      label={label}
      height={height}
      table={{ columns: ["Item", xLabel, yLabel, "Quadrant"], rows: points.map((p) => [p.label, p.xExact, p.yExact, hot(p) ? corner : ""]) }}
    >
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 12, right: 12, bottom: 18, left: 0 }}>
          <CartesianGrid stroke="var(--viz-grid)" />
          <ReferenceArea x1={xSplit} x2={xMax} y1={ySplit} y2={yMax} fill="var(--status-critical)" fillOpacity={0.06} label={{ value: corner, position: "insideTopRight", fill: "var(--ink-3)", fontSize: 11 }} />
          <ReferenceLine x={xSplit} stroke="var(--line-strong)" strokeDasharray="3 3" />
          <ReferenceLine y={ySplit} stroke="var(--line-strong)" strokeDasharray="3 3" />
          <XAxis type="number" dataKey="x" domain={[0, xMax]} {...AXIS} tickFormatter={compactTick} label={{ value: xLabel, position: "insideBottom", offset: -12, fill: "var(--ink-3)", fontSize: 11 }} />
          <YAxis type="number" dataKey="y" domain={[0, yMax]} {...AXIS} width={44} tickFormatter={compactTick} label={{ value: yLabel, angle: -90, position: "insideLeft", fill: "var(--ink-3)", fontSize: 11 }} />
          <ZAxis type="number" dataKey="size" range={[40, 260]} />
          <Tooltip
            cursor={{ strokeDasharray: "3 3", stroke: "var(--line-strong)" }}
            content={({ active, payload }: TooltipContentProps) => {
              const p = active ? (payload?.[0]?.payload as RiskPoint | undefined) : undefined;
              return p ? (
                <TooltipCard
                  title={p.label}
                  lines={[
                    { label: xLabel, value: p.xExact },
                    { label: yLabel, value: p.yExact },
                  ]}
                />
              ) : null;
            }}
          />
          <Scatter
            data={points.filter((p) => !hot(p))}
            fill="var(--viz-1)"
            fillOpacity={0.7}
            isAnimationActive={false}
            cursor={onSelect ? "pointer" : undefined}
            onClick={(d) => onSelect?.((d as { payload?: RiskPoint }).payload as RiskPoint)}
          />
          <Scatter
            data={points.filter(hot)}
            fill="var(--status-critical)"
            fillOpacity={0.85}
            isAnimationActive={false}
            cursor={onSelect ? "pointer" : undefined}
            onClick={(d) => onSelect?.((d as { payload?: RiskPoint }).payload as RiskPoint)}
          />
        </ScatterChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}
