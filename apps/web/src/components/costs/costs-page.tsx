"use client";

import { clsx } from "clsx";
import { Search } from "lucide-react";
import { useState } from "react";

import { SimpleTable, type SimpleColumn } from "@/components/data/simple-table";
import { ErrorState, Panel, Skeleton } from "@/components/data/widget";
import type { CostComparison, Row } from "@/lib/api";
import { formatMoney, formatQuantity, humanize } from "@/lib/format";
import { useAbc, useCostComparison, useInventoryFilters } from "@/lib/hooks";

function Figure({ label, value, note, tone }: { label: string; value: string; note?: string; tone?: "signal" }) {
  return (
    <div className="min-w-0 rounded-sm border border-line bg-surface-2/50 p-3">
      <p className="eyebrow">{label}</p>
      <p className={clsx("figure mt-1 text-lg font-semibold", tone === "signal" && "text-signal")}>{value}</p>
      {note && <p className="mt-0.5 text-xs text-ink-3">{note}</p>}
    </div>
  );
}

function ComparisonResult({ data }: { data: CostComparison }) {
  const cur = data.currency;
  const m = data.methods;
  const unit = (v?: string | null) => (v ? formatMoney(v, cur, { locale: undefined }) : "—");
  const rec = data.reconciliation;
  return (
    <div className="space-y-4" data-testid="cost-result">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Figure label="Moving weighted average" value={unit(m.moving_weighted_average?.unit_cost)} note={`Value ${formatMoney(m.moving_weighted_average?.value, cur)}`} />
        <Figure label="FIFO (remaining layers)" value={unit(m.fifo?.unit_cost)} note={`Value ${formatMoney(m.fifo?.value, cur)}`} />
        <Figure label="Latest receipt cost" value={unit(m.latest_receipt_cost?.unit_cost)} note={m.latest_receipt_cost ? `${m.latest_receipt_cost.date} · ${m.latest_receipt_cost.reference}` : "No receipts"} />
        <Figure
          label="Latest valid purchase price"
          value={unit(m.latest_valid_purchase_price?.unit_price)}
          note={m.latest_valid_purchase_price ? `${m.latest_valid_purchase_price.order_date} · ${m.latest_valid_purchase_price.reference}` : "No qualifying purchase line"}
        />
      </div>

      <div className="rounded-sm border border-line p-3 text-sm">
        <p className="eyebrow">Reconciliation with the source valuation</p>
        <p className="mt-1 text-ink-2">
          Source: <span className="figure">{unit(m.source_valuation.unit_cost)}</span> per {data.uom ?? "unit"} on{" "}
          <span className="figure">{formatQuantity(m.source_valuation.quantity, data.uom)}</span>.{" "}
          {rec.status === "match" && <strong className="text-ok">Recomputed average matches.</strong>}
          {rec.status === "differs" && (
            <strong className="text-signal">
              Differs by {formatMoney(rec.difference_unit_cost, cur)} per unit
              {rec.quantity_matches === false ? " and the quantities differ" : ""}.
            </strong>
          )}
          {rec.status === "not_computable" && <strong>Cannot be compared.</strong>}
        </p>
        {rec.tolerance && <p className="mt-1 text-xs text-ink-3">Tolerance {rec.tolerance}: source prices carry four decimals.</p>}
      </div>

      {Object.keys(data.errors).length > 0 && (
        <ul className="text-sm text-signal">
          {Object.entries(data.errors).map(([k, v]) => (
            <li key={k}>
              {humanize(k)}: {v}
            </li>
          ))}
        </ul>
      )}

      {m.fifo && m.fifo.layers.length > 0 && (
        <div>
          <p className="eyebrow mb-1">Remaining FIFO layers (oldest first)</p>
          <SimpleTable
            columns={[
              { key: "d", label: "Received", render: (r) => <span className="figure text-xs">{r.receipt_date}</span> },
              { key: "r", label: "Reference", render: (r) => <span className="figure text-xs">{r.source}</span> },
              { key: "q", label: "Quantity", align: "right", render: (r) => <span className="figure">{formatQuantity(r.quantity as string, data.uom)}</span> },
              { key: "c", label: "Unit cost", align: "right", render: (r) => <span className="figure">{formatMoney(r.unit_cost as string, cur)}</span> },
            ]}
            rows={m.fifo.layers as unknown as Row[]}
            empty="No layers."
            rowKey={(r) => String(r.source)}
            minWidth="28rem"
          />
        </div>
      )}
      {data.lots.length > 0 && (
        <div>
          <p className="eyebrow mb-1">Lots on hand — lot cost</p>
          <SimpleTable
            columns={[
              { key: "l", label: "Lot", render: (r) => <span className="figure text-xs">{r.lot_id}</span> },
              { key: "d", label: "Received", render: (r) => <span className="figure text-xs">{r.receipt_date ?? "—"}</span> },
              { key: "q", label: "On hand", align: "right", render: (r) => <span className="figure">{formatQuantity(r.quantity as string, data.uom)}</span> },
              { key: "c", label: "Lot unit cost", align: "right", render: (r) => <span className="figure">{formatMoney(r.unit_cost as string, cur)}</span> },
            ]}
            rows={data.lots as unknown as Row[]}
            empty="No lots."
            rowKey={(r) => String(r.lot_id)}
            minWidth="28rem"
          />
        </div>
      )}
      <details className="text-xs text-ink-3">
        <summary className="cursor-pointer">Definitions used ({data.status})</summary>
        <ul className="mt-1 space-y-1">
          {Object.entries(data.rules).map(([k, v]) => (
            <li key={k}>
              <span className="text-ink-2">{humanize(k)}:</span> {v}
            </li>
          ))}
        </ul>
      </details>
    </div>
  );
}

function CostComparisonPanel() {
  const filters = useInventoryFilters();
  const [item, setItem] = useState("");
  const [warehouse, setWarehouse] = useState("");
  const [submitted, setSubmitted] = useState({ item: "", warehouse: "" });
  const cost = useCostComparison(submitted.item, submitted.warehouse);
  return (
    <Panel title="Cost comparison" subtitle="One item in one warehouse: four ways to cost it, reconciled with the source" provenance={cost.data?.provenance} warnings={cost.data?.warnings}>
      <form
        className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-[1fr_16rem_auto]"
        onSubmit={(e) => {
          e.preventDefault();
          setSubmitted({ item: item.trim(), warehouse });
        }}
      >
        <label className="flex flex-col gap-1">
          <span className="eyebrow">Item id</span>
          <span className="flex h-9 items-center gap-2 rounded-sm border border-line bg-surface px-2">
            <Search size={14} className="text-ink-3" aria-hidden />
            <input value={item} onChange={(e) => setItem(e.target.value)} maxLength={64} placeholder="e.g. 2119000124" className="figure h-full w-full bg-transparent text-sm outline-none" aria-label="Item id" />
          </span>
        </label>
        <label className="flex flex-col gap-1">
          <span className="eyebrow">Warehouse</span>
          <select value={warehouse} onChange={(e) => setWarehouse(e.target.value)} className="h-9 rounded-sm border border-line bg-surface px-2 text-sm" aria-label="Warehouse">
            <option value="">Choose…</option>
            {(filters.data?.warehouses ?? []).map((w) => (
              <option key={w.id} value={w.id}>
                {w.id} · {w.name}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" disabled={!item.trim() || !warehouse} className="h-9 self-end rounded-sm bg-ink px-4 text-sm font-medium text-surface disabled:opacity-40">
          Compare
        </button>
      </form>
      {!submitted.item ? (
        <p className="text-sm text-ink-3">Enter an item id (see the Inventory page) and choose a warehouse.</p>
      ) : cost.isFetching ? (
        <Skeleton className="h-40 w-full" />
      ) : cost.error ? (
        <ErrorState error={cost.error} />
      ) : cost.data ? (
        <ComparisonResult data={cost.data} />
      ) : null}
    </Panel>
  );
}

const ABC_COLUMNS: SimpleColumn[] = [
  { key: "i", label: "Item", render: (r) => <span className="figure text-xs">{r.item_id}</span> },
  { key: "v", label: "On-hand value", align: "right", render: (r) => <span className="figure">{r.value}</span> },
  { key: "c", label: "Computed", render: (r) => <span className="figure">{r.computed ?? "—"}</span> },
  { key: "a", label: "Assigned in source", render: (r) => <span className="figure">{r.assigned ?? "—"}</span> },
  { key: "d", label: "", render: (r) => (r.differs ? <span className="text-xs font-semibold text-signal">differs</span> : null) },
];

function AbcPanel() {
  const [a, setA] = useState("0.80");
  const [b, setB] = useState("0.95");
  const [currency, setCurrency] = useState("");
  const [run, setRun] = useState<{ a: string; b: string; currency: string } | null>(null);
  const abc = useAbc(run?.a ?? "", run?.b ?? "", run?.currency ?? "");
  return (
    <Panel title="Computed ABC vs assigned" subtitle="Draft method: on-hand value ranking. You choose the cutoffs — there are no defaults." provenance={run ? abc.data?.provenance : undefined} warnings={abc.data?.warnings}>
      <form
        className="mb-4 flex flex-wrap items-end gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          setRun({ a, b, currency });
        }}
      >
        <label className="flex flex-col gap-1">
          <span className="eyebrow">A covers up to</span>
          <input value={a} onChange={(e) => setA(e.target.value)} className="figure h-9 w-24 rounded-sm border border-line bg-surface px-2 text-sm" aria-label="A cutoff" inputMode="decimal" />
        </label>
        <label className="flex flex-col gap-1">
          <span className="eyebrow">B covers up to</span>
          <input value={b} onChange={(e) => setB(e.target.value)} className="figure h-9 w-24 rounded-sm border border-line bg-surface px-2 text-sm" aria-label="B cutoff" inputMode="decimal" />
        </label>
        <label className="flex flex-col gap-1">
          <span className="eyebrow">Currency (if several)</span>
          <input value={currency} onChange={(e) => setCurrency(e.target.value.toUpperCase())} maxLength={3} placeholder="USD" className="figure h-9 w-24 rounded-sm border border-line bg-surface px-2 text-sm" aria-label="Currency" />
        </label>
        <button type="submit" className="h-9 rounded-sm bg-ink px-4 text-sm font-medium text-surface">
          Classify
        </button>
      </form>
      {!run ? (
        <p className="text-sm text-ink-3">Choose cutoffs and classify. Values in different currencies are never combined.</p>
      ) : abc.isFetching ? (
        <Skeleton className="h-40 w-full" />
      ) : abc.error ? (
        <ErrorState error={abc.error} />
      ) : abc.data ? (
        <div className="space-y-3" data-testid="abc-result">
          <p className="text-sm text-ink-2">
            {abc.data.item_count} items ranked in <span className="figure">{abc.data.currency}</span>;{" "}
            <strong className={abc.data.differences ? "text-signal" : "text-ok"}>{abc.data.differences} differ from the class assigned in the source</strong>.
          </p>
          <div className="figure flex flex-wrap gap-4 text-xs text-ink-2">
            {Object.entries(abc.data.matrix).map(([computed, row]) => (
              <span key={computed}>
                computed {computed}: {Object.entries(row).map(([assigned, n]) => `${assigned}×${n}`).join(" ")}
              </span>
            ))}
          </div>
          <SimpleTable columns={ABC_COLUMNS} rows={abc.data.items.slice(0, 40) as unknown as Row[]} empty="No items." rowKey={(r) => String(r.item_id)} minWidth="32rem" />
          <p className="text-xs text-ink-3">Showing the 40 highest-value items. {abc.data.rule}</p>
        </div>
      ) : null}
    </Panel>
  );
}

export function CostsPage() {
  return (
    <div className="mx-auto max-w-[96rem] space-y-5">
      <div className="rise">
        <p className="eyebrow">Costs</p>
        <h1 className="mt-1 text-2xl font-bold tracking-tight text-ink sm:text-[1.75rem]">Cost analysis</h1>
        <p className="mt-1 text-sm text-ink-3">
          Deterministic calculations on source movements. These definitions are drafts: they become your policy only when your organisation approves them.
        </p>
      </div>
      <CostComparisonPanel />
      <AbcPanel />
    </div>
  );
}
