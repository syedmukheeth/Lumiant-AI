"use client";

import { ResponsiveContainer, Tooltip, Treemap as RTreemap, type TooltipContentProps, type TreemapNode } from "recharts";

import { ChartFrame, SEQ, SEQ_INK, TooltipCard } from "@/components/viz/shared";

export type TreemapItem = { id: string; label: string; value: number; exact: string; share?: string };

/** Share of a whole as nested rectangles (value by item group). Larger = more value; colour repeats the rank. */
export function Treemap({
  items,
  label,
  height = 260,
  onSelect,
}: {
  items: TreemapItem[];
  label: string;
  height?: number;
  onSelect?: (item: TreemapItem) => void;
}) {
  const sorted = [...items].sort((a, b) => b.value - a.value);
  // Colour by size relative to the largest (steps 1–4 of the ramp; the brightest step is kept for emphasis elsewhere).
  const max = sorted[0]?.value || 1;
  const step = (v: number) => Math.min(3, Math.max(0, Math.round((v / max) * 3)));
  const data = sorted.map((it) => ({ ...it, name: it.label, fill: SEQ[step(it.value)], ink: SEQ_INK[step(it.value)] }));
  const byName = new Map(data.map((d) => [d.name, d]));

  function Cell(node: TreemapNode) {
    const { x, y, width, height: h, name } = node;
    const d = byName.get(name);
    if (!d || width <= 0 || h <= 0) return <g />;
    const roomy = width > 72 && h > 36;
    return (
      <g style={{ cursor: onSelect ? "pointer" : undefined }} onClick={() => onSelect?.(d)}>
        <rect x={x} y={y} width={width} height={h} rx={6} fill={d.fill} stroke="var(--surface)" strokeWidth={2} />
        {roomy && (
          <>
            <text x={x + 8} y={y + 18} fill={d.ink} fontSize={12} fontWeight={600}>
              {d.label.length > width / 7 ? `${d.label.slice(0, Math.floor(width / 7) - 1)}…` : d.label}
            </text>
            <text x={x + 8} y={y + 33} fill={d.ink} fillOpacity={0.85} fontSize={11} className="figure">
              {d.share ?? d.exact}
            </text>
          </>
        )}
      </g>
    );
  }

  return (
    <ChartFrame label={label} height={height} table={{ columns: ["Group", "Value", "Share"], rows: data.map((d) => [d.label, d.exact, d.share ?? ""]) }}>
      <ResponsiveContainer width="100%" height="100%">
        <RTreemap data={data} dataKey="value" nameKey="name" content={Cell} isAnimationActive={false} aspectRatio={4 / 3}>
          <Tooltip
            content={({ active, payload }: TooltipContentProps) => {
              const d = active ? byName.get(String((payload?.[0]?.payload as { name?: string } | undefined)?.name)) : undefined;
              return d ? <TooltipCard title={d.label} lines={[{ label: "Value", value: d.exact }, ...(d.share ? [{ label: "Share", value: d.share }] : [])]} /> : null;
            }}
          />
        </RTreemap>
      </ResponsiveContainer>
    </ChartFrame>
  );
}
