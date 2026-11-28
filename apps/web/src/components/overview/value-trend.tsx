"use client";

import { useQuery } from "@tanstack/react-query";

import { ErrorState, Panel, Skeleton } from "@/components/data/widget";
import { TrendArea } from "@/components/viz/trend-area";
import { formatMoney } from "@/lib/format";
import { queries } from "@/lib/queries";

type Point = { period: string; date: string; value: string | null; receipts_value: string | null; issues_value: string | null };
export type Trend = { as_of: string; months: number; rule: string; series: { currency: string | null; points: Point[] }[]; warnings: { code: string; message: string }[] };

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const label = (p: Point) => (p.period === "now" ? "Now" : `${MONTHS[Number(p.period.slice(5, 7)) - 1]} ${p.period.slice(2, 4)}`);

export const useValueTrend = (enabled: boolean) =>
  useQuery({ ...queries.valueTrend(), enabled });

/** Command centre: month-end inventory value (current prices) with monthly receipts and issues, per currency. */
export function ValueTrend() {
  const q = useValueTrend(true);
  const first = q.data?.series[0];
  const rows = (first?.points ?? []).map((p) => ({
    label: label(p),
    values: { value: Number(p.value ?? 0), receipts: Number(p.receipts_value ?? 0), issues: Number(p.issues_value ?? 0) },
    exact: {
      value: formatMoney(p.value, first?.currency ?? undefined),
      receipts: p.receipts_value ? formatMoney(p.receipts_value, first?.currency ?? undefined) : "",
      issues: p.issues_value ? formatMoney(p.issues_value, first?.currency ?? undefined) : "",
    },
  }));
  const last = first?.points.at(-1);
  const start = first?.points[0];
  return (
    <Panel
      title="Inventory value over 12 months"
      subtitle={q.data?.rule ?? "Month-end value at today's prices, with receipts and issues per month."}
      warnings={q.data?.warnings}
    >
      {q.isPending ? (
        <Skeleton className="h-64 w-full" />
      ) : q.error ? (
        <ErrorState error={q.error} />
      ) : !first ? (
        <p className="text-sm text-ink-3">No valued stock to trace.</p>
      ) : (
        <div className="space-y-4" data-testid="value-trend">
          <div className="flex flex-wrap items-baseline gap-x-6 gap-y-1">
            <span className="figure text-kpi font-semibold text-ink">{formatMoney(last?.value ?? null, first.currency ?? undefined)}</span>
            {start?.value && (
              <span className="text-sm text-ink-2">
                from {formatMoney(start.value, first.currency ?? undefined)} at the end of {label(start)}
              </span>
            )}
            {q.data.series.length > 1 && <span className="text-xs text-ink-3">Shown in {first.currency}; other currencies are never added in.</span>}
          </div>
          <TrendArea
            rows={rows}
            series={[
              { key: "value", label: "Month-end value" },
              { key: "receipts", label: "Received in month", color: "var(--viz-3)", dashed: true },
              { key: "issues", label: "Issued in month", color: "var(--viz-2)", dashed: true },
            ]}
            label={`Inventory value at each month end over the last 12 months, in ${first.currency ?? "the source currency"}, with the value received and issued each month.`}
            height={260}
          />
        </div>
      )}
    </Panel>
  );
}
