"use client";

import { useQuery } from "@tanstack/react-query";

import { ErrorState, Panel, Skeleton } from "@/components/data/widget";
import { formatCount, formatMoney } from "@/lib/format";
import { queries } from "@/lib/queries";

type Bucket = { bucket: string; label: string; pairs: number; value?: Record<string, string> };
export type Ageing = { as_of: string; rule: string; buckets: Bucket[]; currencies: string[]; value_visible: boolean; warnings: { code: string; message: string }[] };

// Older buckets read warmer: the bar colour carries age, the text carries the figure.
const TONE: Record<string, string> = {
  "0-90": "bg-(--seq-2)",
  "91-180": "bg-(--seq-3)",
  "181-365": "bg-(--div-neg)/70",
  "365+": "bg-(--div-neg)",
  never: "bg-(--status-critical)",
};

/** Risks: stock by time since its last issue. Bar lengths are geometry only; printed figures are the API's strings. */
export function AgeingPanel() {
  const q = useQuery(queries.ageing());
  const currency = q.data?.currencies[0];
  const measure = (b: Bucket) => (q.data?.value_visible && currency ? Number(b.value?.[currency] ?? 0) : b.pairs);
  const max = Math.max(1, ...(q.data?.buckets ?? []).map(measure));
  return (
    <Panel title="Stock ageing" subtitle={q.data?.rule ?? "On-hand stock by days since its last issue."} warnings={q.data?.warnings}>
      {q.isPending ? (
        <Skeleton className="h-40 w-full" />
      ) : q.error ? (
        <ErrorState error={q.error} />
      ) : (
        <div className="space-y-3" data-testid="ageing">
          {q.data.value_visible && q.data.currencies.length > 1 && (
            <p className="text-xs text-ink-3">Bars show {currency}; other currencies are listed, never added in.</p>
          )}
          <ul className="space-y-2.5">
            {q.data.buckets.map((b) => (
              <li key={b.bucket} className="grid grid-cols-[8.5rem_1fr_auto] items-center gap-3 text-sm">
                <span className="text-ink-2">{b.label}</span>
                <span className="h-2.5 overflow-hidden rounded-full bg-surface-2" aria-hidden>
                  <span className={`block h-full rounded-full ${TONE[b.bucket] ?? "bg-accent"}`} style={{ width: `${(measure(b) / max) * 100}%` }} />
                </span>
                <span className="figure text-right text-ink">
                  {q.data.value_visible && currency ? (
                    <>
                      {formatMoney(b.value?.[currency] ?? "0", currency, { compact: true })}
                      <span className="ml-2 text-xs text-ink-3">{formatCount(b.pairs)} pairs</span>
                    </>
                  ) : (
                    `${formatCount(b.pairs)} pairs`
                  )}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Panel>
  );
}
