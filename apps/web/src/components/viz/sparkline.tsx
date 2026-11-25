"use client";

import { useId } from "react";

type Tone = "accent" | "ai" | "critical" | "muted";
const STROKE: Record<Tone, string> = {
  accent: "var(--accent)",
  ai: "var(--ai)",
  critical: "var(--status-critical)",
  muted: "var(--ink-3)",
};

/**
 * A tiny trend line for KPI tiles. Hand-drawn SVG (no chart library) so a row of tiles stays cheap.
 * Values are geometry only; the tile prints the exact figure next to it.
 */
export function Sparkline({
  values,
  label,
  tone = "accent",
  width = 96,
  height = 28,
}: {
  values: number[];
  label: string;
  tone?: Tone;
  width?: number;
  height?: number;
}) {
  const id = useId().replace(/:/g, "");
  if (values.length < 2) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const pad = 2;
  const pts = values.map((v, i) => {
    const x = (i / (values.length - 1)) * (width - pad * 2) + pad;
    const y = height - pad - ((v - min) / span) * (height - pad * 2);
    return [x, y] as const;
  });
  const line = pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const area = `${line} L${pts[pts.length - 1][0].toFixed(1)},${height} L${pts[0][0].toFixed(1)},${height} Z`;
  const [lx, ly] = pts[pts.length - 1];
  const stroke = STROKE[tone];
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={label} className="overflow-visible">
      <defs>
        <linearGradient id={`spark-${id}`} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor={stroke} stopOpacity={0.28} />
          <stop offset="100%" stopColor={stroke} stopOpacity={0} />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#spark-${id})`} />
      <path d={line} fill="none" stroke={stroke} strokeWidth={1.5} strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={lx} cy={ly} r={2.25} fill={stroke} />
    </svg>
  );
}
