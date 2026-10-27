"use client";

import { clsx } from "clsx";
import { CheckCircle2, CircleAlert, Lock, MinusCircle } from "lucide-react";
import { useState } from "react";

import { ItemCell, SimpleTable, type SimpleColumn } from "@/components/data/simple-table";
import { Pager } from "@/components/data/pager";
import { ErrorState, Panel, Skeleton } from "@/components/data/widget";
import type { DataQualityCheck } from "@/lib/api";
import { formatCount, formatNumber, formatQuantity, formatTimestamp, humanize } from "@/lib/format";
import { type RiskKind, useDataQuality, useRisk } from "@/lib/hooks";

const PAGE = 25;

const TABS = [
  { id: "excess-stock", label: "Excess stock", blurb: "On hand is above the customer's maximum-stock policy." },
  { id: "dormant", label: "Dormant stock", blurb: "Stock on hand with no issue movement for the chosen number of days." },
  { id: "expiring-lots", label: "Expiring lots", blurb: "Lots on hand that are expired or expire soon." },
  { id: "data-quality", label: "Data quality", blurb: "Gaps in master data that limit what the platform can calculate." },
] as const;
type Tab = (typeof TABS)[number]["id"];

const EXCESS: SimpleColumn[] = [
  { key: "item", label: "Item", render: (r) => <ItemCell row={r} /> },
  { key: "wh", label: "Warehouse", render: (r) => <><span className="figure text-xs">{r.warehouse_id}</span><span className="block text-xs text-ink-3">{r.warehouse_name}</span></> },
  { key: "oh", label: "On hand", align: "right", render: (r) => <span className="figure">{formatQuantity(r.on_hand as string, r.uom as string)}</span> },
  { key: "max", label: "Maximum", align: "right", render: (r) => <span className="figure">{formatQuantity(r.max_stock as string)}</span> },
  { key: "ex", label: "Excess", align: "right", render: (r) => <span className="figure text-signal">{formatQuantity(r.excess as string)}</span> },
  { key: "pct", label: "Of maximum", align: "right", render: (r) => <span className="figure">{formatNumber(r.coverage_pct as string, { maxFraction: 0 })}%</span> },
];

const DORMANT: SimpleColumn[] = [
  { key: "item", label: "Item", render: (r) => <ItemCell row={r} /> },
  { key: "grp", label: "Group", render: (r) => humanize(r.item_group as string) },
  { key: "wh", label: "Warehouse", render: (r) => <span className="figure text-xs">{r.warehouse_id}</span> },
  { key: "oh", label: "On hand", align: "right", render: (r) => <span className="figure">{formatQuantity(r.on_hand as string, r.uom as string)}</span> },
  { key: "last", label: "Last issue", render: (r) => <span className="figure text-xs">{(r.last_issue as string) ?? "never in history"}</span> },
  { key: "days", label: "Days idle", align: "right", render: (r) => <span className="figure">{r.days_since_issue === null ? "—" : formatCount(r.days_since_issue as number)}</span> },
];

const EXPIRING: SimpleColumn[] = [
  { key: "item", label: "Item", render: (r) => <ItemCell row={r} /> },
  { key: "wh", label: "Warehouse", render: (r) => <span className="figure text-xs">{r.warehouse_id}</span> },
  { key: "lot", label: "Lot", render: (r) => <span className="figure text-xs">{r.lot_id}</span> },
  { key: "qty", label: "Quantity", align: "right", render: (r) => <span className="figure">{formatQuantity(r.quantity as string, r.uom as string)}</span> },
  { key: "exp", label: "Expires", render: (r) => <span className="figure text-xs">{r["lot.expiry_date"]}</span> },
  {
    key: "left",
    label: "Status",
    render: (r) =>
      r.status === "expired" ? (
        <span className="rounded-sm bg-signal-soft px-1.5 py-0.5 text-xs font-semibold text-signal">Expired {Math.abs(r.days_to_expiry as number)} d ago</span>
      ) : (
        <span className="figure text-xs">{formatCount(r.days_to_expiry as number)} d left</span>
      ),
  },
];

function RiskTable({ kind, columns, days, empty }: { kind: RiskKind; columns: SimpleColumn[]; days?: number; empty: string }) {
  const [offset, setOffset] = useState(0);
  const params: Record<string, string | number> = { limit: PAGE, ...(kind !== "expiring-lots" ? { offset } : {}), ...(days ? { days } : {}) };
  const { data, error, isPending, isFetching } = useRisk(kind, params);
  const summary = data?.summary;
  return (
    <Panel
      title={TABS.find((t) => t.id === kind)?.label ?? kind}
      subtitle={
        summary?.flagged !== undefined
          ? `${formatCount(summary.flagged)} flagged`
          : kind === "expiring-lots" && summary
            ? `${formatCount(summary.expired)} expired · ${formatCount(summary.expiring)} expiring within ${summary.days} days`
            : undefined
      }
      provenance={data?.provenance}
      warnings={data?.warnings.filter((w) => w.code !== "auto_grouped")}
    >
      {isPending ? (
        <Skeleton className="h-64 w-full" />
      ) : error ? (
        <ErrorState error={error} />
      ) : (
        <>
          <SimpleTable
            columns={columns}
            rows={data?.data ?? []}
            empty={empty}
            busy={isFetching}
            rowKey={(r, i) => `${r.item_id}-${r.warehouse_id}-${r.lot_id ?? ""}-${i}`}
          />
          {data?.page && <Pager page={data.page} onChange={setOffset} />}
        </>
      )}
    </Panel>
  );
}

const STATUS_ICON: Record<DataQualityCheck["status"], { icon: typeof CheckCircle2; className: string; label: string }> = {
  ok: { icon: CheckCircle2, className: "text-ok", label: "No gaps found" },
  issue: { icon: CircleAlert, className: "text-signal", label: "Needs attention" },
  not_mapped: { icon: MinusCircle, className: "text-ink-3", label: "Field not mapped for this tenant — cannot be checked" },
  restricted: { icon: Lock, className: "text-ink-3", label: "Hidden: your role cannot view cost information" },
  no_rules: { icon: MinusCircle, className: "text-ink-3", label: "No item-code rules configured for this tenant" },
};

function DataQualityPanel() {
  const { data, error, isPending } = useDataQuality();
  return (
    <Panel
      title="Master-data quality"
      subtitle={data ? `${formatCount(data.total_items)} items in the item master` : undefined}
      warnings={data?.warnings}
    >
      {isPending ? (
        <Skeleton className="h-64 w-full" />
      ) : error ? (
        <ErrorState error={error} />
      ) : (
        <ul className="divide-y divide-line">
          {data?.checks.map((c) => {
            const s = STATUS_ICON[c.status];
            const Icon = s.icon;
            return (
              <li key={c.id} className="flex items-start gap-3 py-3" data-testid={`dq-${c.id}`}>
                <Icon size={16} className={clsx("mt-0.5 shrink-0", s.className)} aria-hidden />
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-ink">{c.title}</p>
                  <p className="text-xs text-ink-3">{s.label}</p>
                  {c.examples && c.examples.length > 0 && (
                    <ul className="figure mt-1 space-y-0.5 text-xs text-ink-2">
                      {c.examples.map((e) => (
                        <li key={e.item_id}>
                          {e.item_code} <span className="text-ink-3">({e.problems.join(", ")})</span>
                        </li>
                      ))}
                    </ul>
                  )}
                  {c.partial && <p className="mt-1 text-xs text-signal">Only the first {formatCount(c.checked)} items were checked.</p>}
                </div>
                <span className={clsx("figure text-lg font-semibold", c.status === "issue" ? "text-signal" : "text-ink")}>
                  {c.count === null ? "—" : formatCount(c.count)}
                </span>
              </li>
            );
          })}
        </ul>
      )}
      {data?.data_as_of && <p className="mt-3 text-xs text-ink-3">Data as of {formatTimestamp(data.data_as_of)}</p>}
    </Panel>
  );
}

export function RisksPage() {
  const [tab, setTab] = useState<Tab>("excess-stock");
  const [dormantDays, setDormantDays] = useState(270);
  const [expiryDays, setExpiryDays] = useState(60);
  const current = TABS.find((t) => t.id === tab)!;
  return (
    <div className="mx-auto max-w-[96rem] space-y-5">
      <div className="rise">
        <p className="eyebrow">Risks</p>
        <h1 className="mt-1 text-2xl font-bold tracking-tight text-ink sm:text-[1.75rem]">Inventory risks</h1>
        <p className="mt-1 text-sm text-ink-3">
          Every flag explains why it was raised and which data it used. Definitions are drafts until your organisation approves them.
        </p>
      </div>

      <div role="tablist" aria-label="Risk views" className="rise flex flex-wrap gap-1 border-b border-line" style={{ animationDelay: "60ms" }}>
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={t.id === tab}
            onClick={() => setTab(t.id)}
            className={clsx(
              "-mb-px border-b-2 px-3 py-2 text-sm",
              t.id === tab ? "border-ink font-semibold text-ink" : "border-transparent text-ink-3 hover:text-ink",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>
      <p className="text-sm text-ink-2">{current.blurb}</p>

      {tab === "dormant" && (
        <label className="flex items-center gap-2 text-sm text-ink-2">
          No issue for at least
          <select value={dormantDays} onChange={(e) => setDormantDays(Number(e.target.value))} className="h-8 rounded-sm border border-line bg-surface px-2">
            {[90, 180, 270, 365].map((d) => (
              <option key={d} value={d}>{d} days</option>
            ))}
          </select>
        </label>
      )}
      {tab === "expiring-lots" && (
        <label className="flex items-center gap-2 text-sm text-ink-2">
          Expiring within
          <select value={expiryDays} onChange={(e) => setExpiryDays(Number(e.target.value))} className="h-8 rounded-sm border border-line bg-surface px-2">
            {[30, 60, 90, 180].map((d) => (
              <option key={d} value={d}>{d} days</option>
            ))}
          </select>
        </label>
      )}

      {tab === "excess-stock" && <RiskTable key="x" kind="excess-stock" columns={EXCESS} empty="Nothing is above its maximum in your scope." />}
      {tab === "dormant" && <RiskTable key={`d${dormantDays}`} kind="dormant" columns={DORMANT} days={dormantDays} empty="No dormant stock in your scope." />}
      {tab === "expiring-lots" && <RiskTable key={`e${expiryDays}`} kind="expiring-lots" columns={EXPIRING} days={expiryDays} empty="No lots expire in this window." />}
      {tab === "data-quality" && <DataQualityPanel />}
    </div>
  );
}
