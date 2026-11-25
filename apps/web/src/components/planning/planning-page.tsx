"use client";

import { ChevronDown, ChevronRight, HeartHandshake } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { DateCell, PlanningIssues, Qty, RecommendationNote, Stat } from "@/components/planning/shared";
import { SimpleTable, type SimpleColumn } from "@/components/data/simple-table";
import { ErrorState, Panel, Skeleton } from "@/components/data/widget";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { PageHeader } from "@/components/ui/page-header";
import { Tabs } from "@/components/ui/tabs";
import type { FulfilmentLine, PlannedOrder, Row } from "@/lib/api";
import { formatCount, formatQuantity } from "@/lib/format";
import { useBomExplosion, useFulfilment, useMaterialPlan, useMe } from "@/lib/hooks";
import { enterDelay } from "@/lib/motion";

const TABS = [
  { id: "fulfilment", label: "Order fulfilment", blurb: "Can each open customer order line be delivered on time: from stock, open purchase orders, approved alternates or new make/buy: and if not, why." },
  { id: "materials", label: "Material plan", blurb: "What to buy or make, how much and by when, from BOMs, usable stock and open supply. Shared components are planned once." },
  { id: "bom", label: "BOM explorer", blurb: "Every component needed to make a quantity of an item, through all levels, with scrap and yield." },
] as const;
type Tab = (typeof TABS)[number]["id"];

function FulfilmentLineRow({ line, canProtect }: { line: FulfilmentLine; canProtect: boolean }) {
  const [open, setOpen] = useState(false);
  const status = line.on_time ? (
    <Badge tone="ok">On time</Badge>
  ) : line.ready ? (
    <Badge tone="signal">{line.late_days} working days late</Badge>
  ) : (
    <Badge tone="signal">Cannot be dated</Badge>
  );
  return (
    <li className="py-3" data-testid={`line-${line.key}`}>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <button
          type="button"
          className="flex min-w-0 items-center gap-1 text-left text-sm font-medium text-ink"
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
          disabled={line.reasons.length === 0}
        >
          {line.reasons.length > 0 ? open ? <ChevronDown size={14} aria-hidden /> : <ChevronRight size={14} aria-hidden /> : <span className="w-3.5" />}
          <span className="code">{line.key}</span>
        </button>
        <span className="code text-xs text-ink-2">{line.item_id}</span>
        <span className="text-xs text-ink-3">{line.customer_id} · {line.warehouse_id}</span>
        <span className="ml-auto flex items-center gap-3">
          <span className="text-xs text-ink-3">due <span className="figure text-ink-2">{line.due}</span></span>
          {status}
          {canProtect && !line.on_time && (
            <Link
              href={`/commitments?order=${encodeURIComponent(line.key)}`}
              className="inline-flex items-center gap-1 text-xs font-medium text-accent hover:underline"
            >
              <HeartHandshake size={13} aria-hidden />
              Protect this order
            </Link>
          )}
        </span>
      </div>
      <dl className="mt-2 grid grid-cols-2 gap-x-6 gap-y-1 pl-5 text-xs sm:grid-cols-6">
        {(
          [
            ["Ordered", line.quantity],
            ["From stock", line.from_stock],
            ["Open POs", line.from_receipts],
            ["Alternates", line.from_alternates],
            ["To make / buy", line.from_planned],
          ] as const
        ).map(([k, v]) => (
          <div key={k}>
            <dt className="text-ink-3">{k}</dt>
            <dd><Qty value={v} /></dd>
          </div>
        ))}
        <div>
          <dt className="text-ink-3">Ready</dt>
          <dd><DateCell value={line.ready} late={!line.on_time} /></dd>
        </div>
      </dl>
      {open && (
        <ul className="mt-2 space-y-1 pl-5 text-xs text-ink-2" aria-label={`Why ${line.key} is late`}>
          {line.reasons.map((r) => (
            <li key={r}>• {r}</li>
          ))}
        </ul>
      )}
    </li>
  );
}

function FulfilmentView() {
  const { data, error, isPending } = useFulfilment();
  const canProtect = !!useMe().data?.sections.includes("procurement");
  if (isPending) return <Skeleton className="h-72 w-full" />;
  if (error) return <Panel title="Order fulfilment"><ErrorState error={error} /></Panel>;
  const lines = data.lines;
  const late = lines.filter((l) => !l.on_time);
  const undated = lines.filter((l) => !l.ready);
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Open order lines" value={formatCount(lines.length)} hint={`planned on ${data.today}`} />
        <Stat label="On time" value={formatCount(lines.length - late.length)} tone="ok" />
        <Stat label="Late" value={formatCount(late.length - undated.length)} tone={late.length ? "signal" : undefined} />
        <Stat label="Cannot be dated" value={formatCount(undated.length)} hint="a lead time or BOM is missing" tone={undated.length ? "signal" : undefined} />
      </div>
      <Panel title="Customer order lines" subtitle="Sorted as the allocation policy serves them. Open a late line to see why.">
        {lines.length === 0 ? (
          <p className="text-sm text-ink-3">No open customer orders in your scope.</p>
        ) : (
          <ul className="divide-y divide-line">
            {lines.map((l) => (
              <FulfilmentLineRow key={l.key} line={l} canProtect={canProtect} />
            ))}
          </ul>
        )}
        <div className="mt-3 space-y-2">
          <PlanningIssues issues={data.issues} />
          <RecommendationNote />
        </div>
      </Panel>
    </div>
  );
}

const PLAN_COLUMNS: SimpleColumn[] = [
  { key: "item", label: "Item", render: (r) => <><span className="code text-xs">{r.item_id}</span><span className="block text-xs text-ink-3">{r.warehouse_id}</span></> },
  { key: "action", label: "Make / buy", render: (r) => <Badge tone={r.action === "make" ? "accent" : "neutral"}>{r.action === "make" ? "Make" : "Buy"}</Badge> },
  { key: "qty", label: "Quantity", align: "right", render: (r) => <><Qty value={r.quantity as string} />{(r.excess as string) !== "0" && <span className="block text-xs text-ink-3">{formatQuantity(r.excess as string)} over need</span>}</> },
  { key: "release", label: "Release by", render: (r) => <DateCell value={r.release as string | null} late={!!r.release && (r.release as string) < (r.today as string)} /> },
  { key: "need", label: "Needed", render: (r) => <DateCell value={r.need as string} /> },
  { key: "ready", label: "Earliest ready", render: (r) => <DateCell value={r.ready as string | null} late={!!r.ready && (r.ready as string) > (r.need as string)} /> },
  { key: "for", label: "For", render: (r) => <span className="code text-xs text-ink-2">{(r.for_orders as unknown as string[]).slice(0, 3).join(", ")}{(r.for_orders as unknown as string[]).length > 3 ? " …" : ""}</span> },
  { key: "why", label: "Why", render: (r) => <span className="text-xs text-ink-2">{r.explanation as string}{(r.issues as unknown as string[]).length > 0 && <span className="block text-signal">{(r.issues as unknown as string[])[0]}</span>}</span> },
];

function MaterialPlanView() {
  const { data, error, isPending } = useMaterialPlan();
  if (isPending) return <Skeleton className="h-72 w-full" />;
  if (error) return <Panel title="Material plan"><ErrorState error={error} /></Panel>;
  const rows = data.planned_orders as PlannedOrder[];
  const overdue = rows.filter((r) => r.release && r.release < data.today);
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Planned orders" value={formatCount(rows.length)} hint={`planned on ${data.today}`} />
        <Stat label="To buy" value={formatCount(rows.filter((r) => r.action === "buy").length)} />
        <Stat label="To make" value={formatCount(rows.filter((r) => r.action === "make").length)} />
        <Stat label="Release overdue" value={formatCount(overdue.length)} hint="should already have been ordered" tone={overdue.length ? "signal" : undefined} />
      </div>
      <Panel title="Planned orders" subtitle="Net of usable stock and open supply; lot-sized; released lead-time working days before they are needed.">
        <SimpleTable
          columns={PLAN_COLUMNS}
          rows={rows.map((r) => ({ ...r, today: data.today }) as unknown as Row)}
          empty="Nothing needs to be bought or made for the open orders in your scope."
          rowKey={(r) => r.planned_order as string}
          minWidth="64rem"
        />
        <div className="mt-3 space-y-2">
          <PlanningIssues issues={data.issues} />
          <RecommendationNote>Planned orders are suggestions: no purchase or production order is created.</RecommendationNote>
        </div>
      </Panel>
      {data.excess_supply.length > 0 && (
        <Panel title="Supply no demand needs" subtitle="Open receipts and lot-size surplus not consumed by any open order: possible excess.">
          <ul className="divide-y divide-line text-sm">
            {data.excess_supply.map((e) => (
              <li key={`${e.reference}-${e.item_id}`} className="flex justify-between gap-3 py-2">
                <span><span className="code text-xs">{e.item_id}</span> <span className="text-xs text-ink-3">{e.warehouse_id} · {e.source === "receipt" ? "open PO" : "lot-size surplus"} {e.reference}</span></span>
                <Qty value={e.quantity} />
              </li>
            ))}
          </ul>
        </Panel>
      )}
    </div>
  );
}

function BomView() {
  const [draft, setDraft] = useState({ item: "", qty: "1" });
  const [query, setQuery] = useState({ item: "", qty: "1" });
  const { data, error, isFetching } = useBomExplosion(query.item, query.qty);
  return (
    <div className="space-y-4">
      <Panel title="Explode a bill of materials">
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            setQuery({ item: draft.item.trim(), qty: draft.qty });
          }}
        >
          <Field label="Item code" className="w-56">
            <Input value={draft.item} onChange={(e) => setDraft({ ...draft, item: e.target.value })} placeholder="e.g. FG-SKID-1" required maxLength={64} />
          </Field>
          <Field label="Quantity" className="w-32">
            <Input type="number" min="0.001" step="any" value={draft.qty} onChange={(e) => setDraft({ ...draft, qty: e.target.value })} required />
          </Field>
          <Button type="submit" variant="primary">Explode</Button>
        </form>
      </Panel>
      {query.item && (
        isFetching && !data ? (
          <Skeleton className="h-64 w-full" />
        ) : error ? (
          <Panel title="BOM"><ErrorState error={error} /></Panel>
        ) : data ? (
          <div className="grid gap-4 lg:grid-cols-[3fr_2fr]">
            <Panel title={`Structure of ${data.quantity} × ${data.item_id}`} subtitle="Subassemblies are expanded; phantom kits pass their parts through.">
              {data.lines.length === 0 ? (
                <p className="text-sm text-ink-3">No released BOM for this item on {data.today}.</p>
              ) : (
                <ul className="space-y-1 text-sm" aria-label="BOM tree">
                  {data.lines.map((l, i) => (
                    <li key={`${l.path.join("/")}-${l.component_id}-${i}`} className="flex items-baseline gap-2" style={{ paddingLeft: `${(l.level - 1) * 1.25}rem` }}>
                      <span className="code text-xs text-ink">{l.component_id}</span>
                      {l.phantom && <Badge>phantom</Badge>}
                      {l.subassembly && !l.phantom && <Badge tone="accent">subassembly</Badge>}
                      <span className="ml-auto figure text-xs">{formatQuantity(l.quantity)}</span>
                      <span className="hidden text-xs text-ink-3 xl:inline" title={l.explanation}>{l.bom}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
            <Panel title="Total requirement" subtitle="Leaf components to stock or buy.">
              <ul className="divide-y divide-line text-sm">
                {Object.entries(data.totals).map(([k, v]) => (
                  <li key={k} className="flex justify-between py-1.5"><span className="code text-xs">{k}</span><Qty value={v} /></li>
                ))}
              </ul>
              <div className="mt-3"><PlanningIssues issues={data.issues} /></div>
            </Panel>
          </div>
        ) : null
      )}
    </div>
  );
}

export function PlanningPage() {
  const [tab, setTab] = useState<Tab>("fulfilment");
  const current = TABS.find((t) => t.id === tab)!;
  return (
    <div className="mx-auto max-w-[96rem] space-y-5">
      <PageHeader
        title="Orders & materials"
        description="Deterministic planning from your customer orders, stock, open supply and bills of materials. Every number is calculated by the platform and traceable; nothing is executed."
      />
      <Tabs label="Planning views" tabs={TABS} value={tab} onChange={setTab} className="rise" style={enterDelay(1)} />
      <p className="text-sm text-ink-2">{current.blurb}</p>
      {tab === "fulfilment" && <FulfilmentView />}
      {tab === "materials" && <MaterialPlanView />}
      {tab === "bom" && <BomView />}
    </div>
  );
}
