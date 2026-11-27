"use client";

import { useState } from "react";

import { ErrorState, Panel, Skeleton } from "@/components/data/widget";
import { Pager } from "@/components/data/pager";
import { CodeName, DataTable, HeadRow, Td, Th, Tr } from "@/components/ui/table";
import { enterDelay } from "@/lib/motion";
import { formatNumber, formatQuantity } from "@/lib/format";
import { OVERVIEW_BELOW_REORDER, useBelowReorder } from "@/lib/hooks";

const PAGE = OVERVIEW_BELOW_REORDER.limit;

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
      style={enterDelay(8)}
    >
      {isPending ? (
        <Skeleton className="h-64 w-full" />
      ) : error ? (
        <ErrorState error={error} />
      ) : rows.length === 0 ? (
        <p className="text-sm text-ink-3">Nothing below its reorder level in your scope.</p>
      ) : (
        <>
          <DataTable minWidth="46rem" busy={isFetching}>
            <thead>
              <HeadRow>
                {["Item", "Warehouse", "ABC", "On hand", "Reorder level", "Shortfall", "Coverage"].map((h, i) => (
                  <Th key={h} align={i >= 3 && i <= 5 ? "right" : undefined}>
                    {h}
                  </Th>
                ))}
              </HeadRow>
            </thead>
            <tbody>
              {rows.map((r) => (
                <Tr key={`${r.item_id}-${r.warehouse_id}`}>
                  <Td>
                    <CodeName code={r.item_code ?? r.item_id} name={r.description as string | null} />
                  </Td>
                  <Td>
                    <span className="code text-xs">{r.warehouse_id}</span>
                    <span className="block truncate text-xs text-ink-3">{r.warehouse_name}</span>
                  </Td>
                  <Td>{r.abc_class ?? "–"}</Td>
                  <Td align="right" className="figure">
                    {formatQuantity(r.on_hand as string, String(r.uom ?? ""))}
                  </Td>
                  <Td align="right" className="figure">
                    {formatQuantity(r.reorder_level as string)}
                  </Td>
                  <Td align="right">
                    <span className="figure text-signal">{formatQuantity(r.shortfall as string)}</span>
                  </Td>
                  <Td>
                    <Coverage pct={Number(r.coverage_pct ?? 0)} />
                  </Td>
                </Tr>
              ))}
            </tbody>
          </DataTable>
          {data?.page && <Pager page={data.page} onChange={setOffset} />}
        </>
      )}
    </Panel>
  );
}
