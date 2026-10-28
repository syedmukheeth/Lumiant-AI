"use client";

import { clsx } from "clsx";
import { Lock } from "lucide-react";

import { ProvenanceButton } from "@/components/data/provenance";
import { ErrorState, Skeleton } from "@/components/data/widget";
import type { Envelope, Provenance, ResultWarning } from "@/lib/api";
import { formatCount, formatMoney } from "@/lib/format";
import { useBelowReorder, useMetric } from "@/lib/hooks";
import { enterDelay } from "@/lib/motion";

type CellProps = {
  label: string;
  footnote?: string;
  provenance?: Provenance;
  warnings?: ResultWarning[];
  pending?: boolean;
  error?: unknown;
  tone?: "default" | "signal";
  /** Position in the strip (entrance stagger). */
  index: number;
  children?: React.ReactNode;
  testId?: string;
};

function Cell({ label, footnote, provenance, warnings, pending, error, tone = "default", index, children, testId }: CellProps) {
  const gaps = warnings?.filter((w) => w.code === "missing_valuation_price") ?? [];
  return (
    <div
      className={clsx(
        "rise panel relative flex min-w-0 flex-col gap-2 overflow-hidden p-4 transition-colors hover:border-line-strong",
        // a lit top edge: teal for position, amber for attention
        "before:absolute before:inset-x-4 before:top-0 before:h-px before:bg-linear-to-r before:from-transparent before:to-transparent",
        tone === "signal" ? "before:via-signal/70" : "before:via-accent/60",
      )}
      style={enterDelay(index)}
      data-testid={testId}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="eyebrow">{label}</span>
        <ProvenanceButton provenance={provenance} label="" />
      </div>
      <div className={clsx("min-h-9", tone === "signal" ? "text-signal" : "text-ink")}>
        {pending ? <Skeleton className="h-8 w-32" /> : error ? <ErrorState error={error} /> : children}
      </div>
      {footnote && !pending && !error && <p className="text-xs text-ink-3">{footnote}</p>}
      {gaps.map((w) => (
        <p key={w.code} className="text-xs text-signal">
          {w.message}
        </p>
      ))}
    </div>
  );
}

function Restricted() {
  return (
    <p className="flex items-center gap-1.5 text-sm text-ink-3">
      <Lock size={14} aria-hidden /> Your role cannot view values
    </p>
  );
}

function firstNumber(env: Envelope | undefined, key: string) {
  const v = env?.data[0]?.[key];
  return typeof v === "number" || typeof v === "string" ? v : null;
}

export function KpiStrip({ canSeeValue }: { canSeeValue: boolean }) {
  const value = useMetric("inventory_value_total", canSeeValue);
  const items = useMetric("items_in_stock");
  const lines = useMetric("stock_lines");
  const below = useBelowReorder({ offset: 0, limit: 1 });

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <Cell
        label="Inventory value"
        provenance={value.data?.provenance}
        warnings={value.data?.warnings}
        pending={canSeeValue && value.isPending}
        error={value.error}
        index={0}
        testId="kpi-value"
        footnote={canSeeValue ? "On-hand × source valuation price" : undefined}
      >
        {canSeeValue ? (
          <ul className="space-y-0.5">
            {(value.data?.data ?? []).map((r) => (
              <li key={String(r.currency)} className="figure text-[1.625rem] font-semibold leading-tight tracking-tight">
                {formatMoney(r.value as string, String(r.currency))}
              </li>
            ))}
            {value.data && value.data.data.length > 1 && (
              <li className="text-xs text-ink-3">Shown per currency — not converted or added.</li>
            )}
          </ul>
        ) : (
          <Restricted />
        )}
      </Cell>
      <Cell
        label="Items in stock"
        provenance={items.data?.provenance}
        pending={items.isPending}
        error={items.error}
        index={1}
        testId="kpi-items"
        footnote="Distinct items with quantity > 0"
      >
        <span className="figure text-[1.625rem] font-semibold leading-tight tracking-tight">{formatCount(firstNumber(items.data, "items"))}</span>
      </Cell>
      <Cell
        label="Stock lines"
        provenance={lines.data?.provenance}
        pending={lines.isPending}
        error={lines.error}
        index={2}
        testId="kpi-lines"
        footnote="Item × warehouse × location × lot"
      >
        <span className="figure text-[1.625rem] font-semibold leading-tight tracking-tight">{formatCount(firstNumber(lines.data, "lines"))}</span>
      </Cell>
      <Cell
        label="Below reorder level"
        provenance={below.data?.provenance}
        pending={below.isPending}
        error={below.error}
        tone="signal"
        index={3}
        testId="kpi-below"
        footnote={
          below.data?.summary
            ? `${formatCount(below.data.summary.pairs_without_policy)} item–warehouse ${
                Number(below.data.summary.pairs_without_policy) === 1 ? "pair has" : "pairs have"
              } no reorder policy`
            : undefined
        }
      >
        <span className="figure text-[1.625rem] font-semibold leading-tight tracking-tight">{formatCount(below.data?.summary?.flagged)}</span>
      </Cell>
    </div>
  );
}
