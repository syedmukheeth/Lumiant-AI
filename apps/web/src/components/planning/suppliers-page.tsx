"use client";

import { Trophy } from "lucide-react";
import { useState } from "react";

import { DateCell, PlanningIssues, RecommendationNote } from "@/components/planning/shared";
import { ErrorState, Panel, Skeleton } from "@/components/data/widget";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Input, Select } from "@/components/ui/field";
import { PageHeader } from "@/components/ui/page-header";
import { CodeName, DataTable, HeadRow, Td, Th, Tr } from "@/components/ui/table";
import type { SupplierOfferView } from "@/lib/api";
import { formatMoney, formatNumber, formatQuantity } from "@/lib/format";
import { type SupplierQuery, useSupplierComparison } from "@/lib/hooks";

const POLICIES = [
  { id: "balanced", label: "Balanced", hint: "40% cost · 30% quality · 20% on-time · 10% lead time" },
  { id: "urgent", label: "Urgent", hint: "earliest delivery among eligible suppliers" },
  { id: "lowest_cost", label: "Lowest cost", hint: "lowest known cost per unit you need (MOQ excess counts)" },
  { id: "quality_critical", label: "Quality critical", hint: "lowest rejection rate; above 3% rejected is not eligible" },
] as const;

function pct(v: string | null, lots: number) {
  if (v === null) return <span className="text-xs text-ink-3" title={`${lots} received deliveries`}>insufficient evidence</span>;
  return <span className="figure">{formatNumber(v, { maxFraction: 1 })}%<span className="block text-xs text-ink-3">{lots} deliveries</span></span>;
}

function OfferRow({ o, best }: { o: SupplierOfferView; best: boolean }) {
  return (
    <Tr>
      <Td>
        <div className="flex items-start gap-2">
          {best && <Trophy size={14} className="mt-0.5 text-brand-gold" aria-label="Recommended" />}
          <div>
            <CodeName code={o.supplier_id} name={o.supplier_name} />
            {o.eligible ? (
              <Badge tone="ok" className="mt-1">{o.rank ? `Rank ${o.rank}` : "Eligible"}</Badge>
            ) : (
              <Badge tone="signal" className="mt-1">Not eligible</Badge>
            )}
          </div>
        </div>
      </Td>
      <Td align="right">
        {o.effective_unit_cost ? <span className="figure">{formatMoney(o.effective_unit_cost, o.currency)}</span> : <span className="text-ink-3">–</span>}
        {o.unit_price && o.landed_unit_cost !== o.unit_price && (
          <span className="block text-xs text-ink-3">price {formatMoney(o.unit_price, o.currency)}</span>
        )}
        {o.unknown_charges.length > 0 && <span className="block text-xs text-signal">excl. unknown {o.unknown_charges.join(" & ")}</span>}
      </Td>
      <Td align="right">
        <span className="figure">{formatQuantity(o.order_quantity)}</span>
        {o.excess_quantity !== "0" && <span className="block text-xs text-signal">+{formatQuantity(o.excess_quantity)} over need</span>}
      </Td>
      <Td>
        <DateCell value={o.earliest_delivery} late={o.meets_need_date === false} />
        <span className="block text-xs text-ink-3">{o.lead_days === null ? "lead time not maintained" : `${o.lead_days} working days`}</span>
      </Td>
      <Td align="right">{pct(o.rejection_pct, o.evidence_lots)}</Td>
      <Td align="right">{pct(o.on_time_pct, o.evidence_lots)}</Td>
      <Td align="right">
        {o.price_vs_last_pct === null ? <span className="text-ink-3">–</span> : (
          <span className={Number(o.price_vs_last_pct) > 0 ? "figure text-signal" : "figure"}>{Number(o.price_vs_last_pct) > 0 ? "+" : ""}{o.price_vs_last_pct}%</span>
        )}
      </Td>
      <Td align="right">{o.score ? <span className="figure">{o.score}</span> : <span className="text-xs text-ink-3">not scored</span>}</Td>
      <Td>
        <ul className="space-y-0.5 text-xs">
          {o.reasons.map((r) => (
            <li key={r} className="text-signal">{r}</li>
          ))}
          {o.notes.slice(0, 3).map((n) => (
            <li key={n} className="text-ink-3">{n}</li>
          ))}
          {o.fx_note && <li className="text-ink-3">{o.fx_note}</li>}
        </ul>
      </Td>
    </Tr>
  );
}

export function SuppliersPage() {
  const [draft, setDraft] = useState<SupplierQuery>({ item: "", qty: "", need_date: "", policy: "balanced" });
  const [query, setQuery] = useState<SupplierQuery | null>(null);
  const { data, error, isFetching } = useSupplierComparison(query);
  const policy = POLICIES.find((p) => p.id === draft.policy)!;
  return (
    <div className="mx-auto max-w-[96rem] space-y-5">
      <PageHeader
        title="Supplier comparison"
        description="Before a purchase order: is this supplier offering the right item at a reasonable landed cost, with an acceptable quality and delivery record, in time? Ranked by your policy: there is no universal winner."
      />
      <Panel title="What do you need?">
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            setQuery({ ...draft, item: draft.item.trim(), need_date: draft.need_date || undefined });
          }}
        >
          <Field label="Item code" className="w-52">
            <Input value={draft.item} onChange={(e) => setDraft({ ...draft, item: e.target.value })} placeholder="e.g. RM-IMPELLER" required maxLength={64} />
          </Field>
          <Field label="Quantity needed" className="w-36">
            <Input type="number" min="0.001" step="any" value={draft.qty} onChange={(e) => setDraft({ ...draft, qty: e.target.value })} required />
          </Field>
          <Field label="Needed by (optional)" className="w-44">
            <Input type="date" value={draft.need_date ?? ""} onChange={(e) => setDraft({ ...draft, need_date: e.target.value })} />
          </Field>
          <Field label="Ranking policy" hint={policy.hint} className="w-60">
            <Select value={draft.policy} onChange={(e) => setDraft({ ...draft, policy: e.target.value })}>
              {POLICIES.map((p) => (
                <option key={p.id} value={p.id}>{p.label}</option>
              ))}
            </Select>
          </Field>
          <Button type="submit" variant="primary">Compare</Button>
        </form>
      </Panel>

      {query && (isFetching && !data ? (
        <Skeleton className="h-72 w-full" />
      ) : error ? (
        <Panel title="Offers"><ErrorState error={error} /></Panel>
      ) : data ? (
        <Panel
          title={`Offers for ${formatQuantity(data.quantity)} × ${data.item_id}`}
          subtitle={`${POLICIES.find((p) => p.id === data.policy)?.label ?? data.policy} policy${data.need_date ? ` · needed by ${data.need_date}` : ""} · planned on ${data.today}`}
        >
          <div className="mb-4 rounded-control border border-accent/30 bg-accent-soft/40 p-3 text-sm text-ink" data-testid="supplier-recommendation">
            {data.recommendation}
            {data.gaps.map((g) => (
              <p key={g} className="mt-1 text-signal">{g}</p>
            ))}
          </div>
          {data.offers.length > 0 && (
            <DataTable minWidth="72rem">
              <thead>
                <HeadRow>
                  <Th>Supplier</Th>
                  <Th align="right">Cost per unit needed</Th>
                  <Th align="right">Order qty</Th>
                  <Th>Earliest delivery</Th>
                  <Th align="right">Rejected</Th>
                  <Th align="right">On time</Th>
                  <Th align="right">vs last price</Th>
                  <Th align="right">Score</Th>
                  <Th>Why</Th>
                </HeadRow>
              </thead>
              <tbody>
                {data.offers.map((o) => (
                  <OfferRow key={o.supplier_id} o={o} best={o.eligible && o.rank === 1} />
                ))}
              </tbody>
            </DataTable>
          )}
          {data.split.length > 0 && (
            <p className="mt-3 text-sm text-ink-2">
              Suggested split: {data.split.map((s) => `${s.supplier_name} ${formatQuantity(s.allocated)}`).join(" · ")}
            </p>
          )}
          <div className="mt-3 space-y-2">
            <p className="text-xs text-ink-3">
              Quality and on-time figures come from received deliveries of this item; fewer than 3 deliveries is shown as insufficient evidence, never a guessed score. Unknown freight or duty is listed, never treated as zero.
            </p>
            <PlanningIssues issues={data.issues} />
            <RecommendationNote>Recommendation for review: no purchase order is created or approved, and no supplier sees another supplier&apos;s quote.</RecommendationNote>
          </div>
        </Panel>
      ) : null)}
    </div>
  );
}
