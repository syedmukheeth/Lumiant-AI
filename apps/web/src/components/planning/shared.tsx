"use client";

import { AlertOctagon, AlertTriangle, Info, ShieldCheck } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { PlanningIssue } from "@/lib/api";
import { formatQuantity } from "@/lib/format";

const ICON = { blocker: AlertOctagon, warning: AlertTriangle, info: Info } as const;

/** Blockers and warnings from a planning run: what could not be calculated, and why. */
export function PlanningIssues({ issues, limit = 8 }: { issues: PlanningIssue[]; limit?: number }) {
  const shown = issues.filter((i) => i.severity !== "info").slice(0, limit);
  if (!shown.length) return null;
  return (
    <ul className="space-y-1.5" aria-label="Planning issues" data-testid="planning-issues">
      {shown.map((i, n) => {
        const Icon = ICON[i.severity];
        return (
          <li key={`${i.code}-${n}`} className="flex items-start gap-2 rounded-control bg-signal-soft/50 px-2.5 py-1.5 text-xs text-ink-2">
            <Icon size={13} className="mt-px shrink-0 text-signal" aria-hidden />
            <span>
              <span className="font-medium text-ink">{i.severity === "blocker" ? "Cannot calculate: " : "Check: "}</span>
              {i.message}
            </span>
          </li>
        );
      })}
      {issues.filter((i) => i.severity !== "info").length > limit && (
        <li className="text-xs text-ink-3">…and more; the tables show the detail per line.</li>
      )}
    </ul>
  );
}

/** States plainly that a result is advice for a person to act on. */
export function RecommendationNote({ children }: { children?: React.ReactNode }) {
  return (
    <p className="flex items-center gap-1.5 text-xs text-ink-3">
      <ShieldCheck size={13} aria-hidden />
      {children ?? "Recommendation only — nothing is ordered, booked or changed in your source system."}
    </p>
  );
}

export function Qty({ value, uom }: { value: string | null | undefined; uom?: string }) {
  if (value === null || value === undefined) return <span className="text-ink-3">—</span>;
  return <span className="figure">{formatQuantity(value, uom)}</span>;
}

export function DateCell({ value, late }: { value: string | null; late?: boolean }) {
  if (!value) return <span className="text-xs whitespace-nowrap text-ink-3">cannot be dated</span>;
  return <span className={late ? "figure text-xs whitespace-nowrap text-signal" : "figure text-xs whitespace-nowrap"}>{value}</span>;
}

export function Stat({ label, value, hint, tone }: { label: string; value: React.ReactNode; hint?: string; tone?: "signal" | "ok" }) {
  return (
    <div className="panel flex min-w-0 flex-col gap-1 p-4">
      <span className="text-xs text-ink-3">{label}</span>
      <span className={`figure text-section font-semibold ${tone === "signal" ? "text-signal" : tone === "ok" ? "text-ok" : "text-ink"}`}>{value}</span>
      {hint && <span className="text-xs text-ink-3">{hint}</span>}
    </div>
  );
}

export function YesNo({ yes, yesLabel = "Yes", noLabel = "No" }: { yes: boolean; yesLabel?: string; noLabel?: string }) {
  return yes ? <Badge tone="ok">{yesLabel}</Badge> : <Badge tone="signal">{noLabel}</Badge>;
}
