"use client";

import { useState } from "react";

import { ErrorState, Panel, Skeleton } from "@/components/data/widget";
import { Pager } from "@/components/data/pager";
import { formatNumber, formatQuantity } from "@/lib/format";
import { useBelowReorder } from "@/lib/hooks";

const PAGE = 12;

function Coverage({ pct }: { pct: number }) {
  const width = Math.max(0, Math.min(100, pct));
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-surface-2" aria-hidden>
        <div className="h-full rounded-full bg-signal" style={{ width: `${width}%` }} />
      </div>
      <span className="figure w-12 text-right text-xs text-ink-2">{formatNumber(pct, { maxFraction: 0 })}%</span>
    </div>
  );
}

export function BelowReorderPanel() {
  const [offset, setOffset] = useState(0);
  const { data, error, isPending, isFetching } = useBelowReorder({ offset, limit: PAGE });
  const rows = data?.data ?? [];

  return (
    <Panel
      title="Items below reorder level"
      subtitle="Customer reorder policy vs on-hand in your scope · lowest coverage first"
      provenance={data?.provenance}
      warnings={data?.warnings}
      style={{ animationDelay: "320ms" }}
    >
      {isPending ? (
        <Skeleton className="h-64 w-full" />
      ) : error ? (
        <ErrorState error={error} />
      ) : rows.length === 0 ? (
        <p className="text-sm text-ink-3">Nothing below its reorder level in your scope.</p>
      ) : (
        <>
          <div className="-mx-4 overflow-x-auto sm:-mx-5">
            <table className="w-full min-w-[46rem] text-sm" aria-busy={isFetching}>
              <thead>
                <tr className="border-y border-line text-left">
                  {["Item", "Warehouse", "ABC", "On hand", "Reorder level", "Shortfall", "Coverage"].map((h, i) => (
                    <th key={h} scope="col" className={`eyebrow px-4 py-2 font-semibold sm:px-5 ${i >= 3 && i <= 5 ? "text-right" : ""}`}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={`${r.item_id}-${r.warehouse_id}`} className="border-b border-line/70 hover:bg-surface-2/60">
                    <td className="max-w-72 px-4 py-2 sm:px-5">
                      <span className="figure block text-xs text-ink-3">{r.item_code ?? r.item_id}</span>
                      <span className="block truncate text-ink" title={String(r.description ?? "")}>
                        {r.description ?? "—"}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-ink-2 sm:px-5">
                      <span className="figure text-xs">{r.warehouse_id}</span>
                      <span className="block truncate text-xs text-ink-3">{r.warehouse_name}</span>
                    </td>
                    <td className="figure px-4 py-2 sm:px-5">{r.abc_class ?? "—"}</td>
                    <td className="figure px-4 py-2 text-right sm:px-5">{formatQuantity(r.on_hand as string, String(r.uom ?? ""))}</td>
                    <td className="figure px-4 py-2 text-right sm:px-5">{formatQuantity(r.reorder_level as string)}</td>
                    <td className="figure px-4 py-2 text-right text-signal sm:px-5">{formatQuantity(r.shortfall as string)}</td>
                    <td className="px-4 py-2 sm:px-5">
                      <Coverage pct={Number(r.coverage_pct ?? 0)} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {data?.page && <Pager page={data.page} onChange={setOffset} />}
        </>
      )}
    </Panel>
  );
}
