"use client";

import { ChartFrame } from "@/components/viz/shared";

/**
 * A score out of 100 on a half ring (data-quality score, service level). The colour band is chosen by the caller's
 * thresholds; the exact score is printed in the centre with its meaning in words.
 */
export function Gauge({
  value,
  exact,
  label,
  status,
  thresholds = { warn: 70, good: 90 },
  size = 168,
}: {
  value: number;
  exact: string;
  label: string;
  /** Words for the state ("Good", "Needs attention"); colour is never the only cue. */
  status: string;
  thresholds?: { warn: number; good: number };
  size?: number;
}) {
  const v = Math.max(0, Math.min(100, value));
  const r = size / 2 - 12;
  const cx = size / 2;
  const cy = size / 2 + 4;
  const arc = (from: number, to: number) => {
    const a0 = Math.PI * (1 - from / 100);
    const a1 = Math.PI * (1 - to / 100);
    const p = (a: number) => `${(cx + r * Math.cos(a)).toFixed(2)},${(cy - r * Math.sin(a)).toFixed(2)}`;
    return `M${p(a0)} A${r},${r} 0 0 1 ${p(a1)}`;
  };
  const tone = v >= thresholds.good ? "var(--ok)" : v >= thresholds.warn ? "var(--status-warning)" : "var(--status-critical)";
  return (
    <ChartFrame label={`${label}: ${exact} out of 100, ${status}`} table={{ columns: ["Measure", "Score", "State"], rows: [[label, exact, status]] }}>
      <div className="flex flex-col items-center">
        <svg width={size} height={size / 2 + 16} viewBox={`0 0 ${size} ${size / 2 + 16}`}>
          <path d={arc(0, 100)} fill="none" stroke="var(--surface-2)" strokeWidth={12} strokeLinecap="round" />
          {v > 0 && <path d={arc(0, v)} fill="none" stroke={tone} strokeWidth={12} strokeLinecap="round" />}
          {[thresholds.warn, thresholds.good].map((t) => {
            const a = Math.PI * (1 - t / 100);
            return (
              <line
                key={t}
                x1={cx + (r - 9) * Math.cos(a)}
                y1={cy - (r - 9) * Math.sin(a)}
                x2={cx + (r + 9) * Math.cos(a)}
                y2={cy - (r + 9) * Math.sin(a)}
                stroke="var(--line-strong)"
                strokeWidth={1.5}
              />
            );
          })}
          <text x={cx} y={cy - 6} textAnchor="middle" fill="var(--ink)" fontSize={28} fontWeight={600} className="figure">
            {exact}
          </text>
        </svg>
        <p className="-mt-1 text-xs font-medium text-ink-2">{status}</p>
      </div>
    </ChartFrame>
  );
}
