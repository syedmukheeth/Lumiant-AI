"use client";

import { CheckCircle2, Split, Trophy, XCircle } from "lucide-react";
import { useSearchParams } from "next/navigation";

import { DateCell, PlanningIssues, RecommendationNote, Stat } from "@/components/planning/shared";
import { ErrorState, Panel, Skeleton } from "@/components/data/widget";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/ui/page-header";
import { DataTable, HeadRow, Td, Th, Tr } from "@/components/ui/table";
import type { CommitmentAnalysis, CommitmentAtRisk, SourcingOption } from "@/lib/api";
import { formatMoney, formatNumber, formatQuantity } from "@/lib/format";
import { useCommitment, useCommitments } from "@/lib/hooks";

const money = (v: string | null | undefined, cur: string) => (v === null || v === undefined ? null : formatMoney(v, cur));

function AtRiskList({ rows, selected, onSelect }: { rows: CommitmentAtRisk[]; selected: string | null; onSelect: (key: string) => void }) {
  if (!rows.length) {
    return <p className="text-sm text-ink-2">Every open order line in your scope can be delivered on time, so there is nothing to protect.</p>;
  }
  return (
    <DataTable minWidth="52rem">
      <thead>
        <HeadRow>
          <Th>Order line</Th>
          <Th>Customer</Th>
          <Th align="right">Qty</Th>
          <Th>Due</Th>
          <Th>Planned delivery</Th>
          <Th align="right">Order value</Th>
        </HeadRow>
      </thead>
      <tbody>
        {rows.map((r) => {
          const active = r.key === selected;
          return (
            <Tr key={r.key} className={active ? "bg-accent-soft/50" : undefined} data-testid={`risk-${r.key}`}>
              <Td>
                <button
                  type="button"
                  className="code text-left text-sm font-medium text-ink underline-offset-2 hover:text-accent hover:underline"
                  aria-pressed={active}
                  onClick={() => onSelect(r.key)}
                >
                  {r.key}
                </button>
                <span className="code block text-xs text-ink-3">{r.item_id}</span>
              </Td>
              <Td><span className="text-xs text-ink-2">{r.customer_id}</span></Td>
              <Td align="right"><span className="figure">{formatQuantity(r.quantity)}</span></Td>
              <Td><span className="figure text-xs">{r.due}</span></Td>
              <Td>
                <DateCell value={r.delivery} late />
                {r.late_days !== null && <span className="block text-xs text-signal">{r.late_days} working days late</span>}
              </Td>
              <Td align="right">
                {r.order_value ? <span className="figure">{formatMoney(r.order_value, r.currency)}</span> : <span className="text-xs text-ink-3">not provided</span>}
              </Td>
            </Tr>
          );
        })}
      </tbody>
    </DataTable>
  );
}

function Feasibility({ o }: { o: SourcingOption }) {
  if (!o.eligible) {
    return (
      <div>
        <Badge tone="signal"><XCircle size={12} aria-hidden />Not eligible</Badge>
        <ul className="mt-1 space-y-0.5 text-xs text-signal">
          {o.reasons.slice(0, 2).map((r) => <li key={r}>{r}</li>)}
        </ul>
      </div>
    );
  }
  return o.meets_deadline ? (
    <Badge tone="ok"><CheckCircle2 size={12} aria-hidden />Meets deadline</Badge>
  ) : (
    <Badge tone="signal"><XCircle size={12} aria-hidden />Misses deadline</Badge>
  );
}

function OptionsTable({ a }: { a: CommitmentAnalysis }) {
  const multi = new Set(a.options.map((o) => o.material_id)).size > 1;
  return (
    <DataTable minWidth="74rem">
      <thead>
        <HeadRow>
          <Th>Option</Th>
          <Th>Material arrival</Th>
          <Th>Production completion</Th>
          <Th>Customer delivery</Th>
          <Th align="right">Total cost</Th>
          <Th align="right">vs cheapest eligible</Th>
          <Th>Feasibility</Th>
        </HeadRow>
      </thead>
      <tbody>
        {a.options.map((o, i) => (
          <Tr key={`${o.material_id}-${o.label}-${i}`} className={o.recommended ? "bg-accent-soft/40" : undefined} data-testid="commitment-option">
            <Td>
              <div className="flex items-start gap-2">
                {o.recommended ? <Trophy size={14} className="mt-0.5 shrink-0 text-brand-gold" aria-label="Recommended" /> : o.kind === "split" ? <Split size={14} className="mt-0.5 shrink-0 text-ink-3" aria-hidden /> : <span className="w-3.5 shrink-0" />}
                <div className="min-w-0">
                  <span className="text-sm font-medium text-ink">{o.label}</span>
                  <span className="block text-xs text-ink-3">
                    {multi && <span className="code">{o.material_id} · </span>}
                    {formatQuantity(o.quantity)} units{o.lead_days !== null ? ` · ${o.lead_days} working days lead time` : " · lead time not maintained"}
                  </span>
                  {o.recommended && <Badge tone="accent" className="mt-1">Recommended</Badge>}
                </div>
              </div>
            </Td>
            <Td>
              <DateCell value={o.material_arrival} late={!!o.material_arrival && o.material_arrival > o.material_needed_by} />
              <span className="block text-xs text-ink-3">needed by {o.material_needed_by}</span>
            </Td>
            <Td><DateCell value={o.production_complete} /></Td>
            <Td>
              <DateCell value={o.customer_delivery} late={!!o.customer_delivery && o.customer_delivery > a.due} />
              <span className="block text-xs text-ink-3">deadline {a.due}</span>
            </Td>
            <Td align="right">{o.total_cost ? <span className="figure">{formatMoney(o.total_cost, o.currency)}</span> : <span className="text-xs text-ink-3">price unknown</span>}</Td>
            <Td align="right">
              {o.incremental_cost === null ? (
                <span className="text-ink-3">–</span>
              ) : (
                <span className={Number(o.incremental_cost) > 0 ? "figure text-signal" : "figure"}>
                  {Number(o.incremental_cost) > 0 ? "+" : ""}{formatMoney(o.incremental_cost, o.currency)}
                </span>
              )}
            </Td>
            <Td><Feasibility o={o} /></Td>
          </Tr>
        ))}
      </tbody>
    </DataTable>
  );
}

function Analysis({ a }: { a: CommitmentAnalysis }) {
  const e = a.exposure;
  const cur = e.currency;
  return (
    <div className="space-y-5" data-testid="commitment-analysis">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Order value at stake" value={money(e.order_value, cur) ?? "not provided"} hint={`${formatQuantity(a.quantity)} × ${a.item_id} for ${a.customer_id}`} />
        <Stat label="Margin at stake" value={money(e.margin_value, cur) ?? "not provided"} />
        <Stat
          label="Delivery-first premium"
          value={money(e.premium, cur) ?? "–"}
          hint={e.premium_pct_of_margin !== null ? `${formatNumber(e.premium_pct_of_margin, { maxFraction: 1 })}% of the margin` : undefined}
          tone={e.premium !== null && Number(e.premium) > 0 ? "signal" : undefined}
        />
        <Stat
          label="Late penalty"
          value={e.penalty_per_day ? `${money(e.penalty_per_day, cur)} / day` : "no penalty on record"}
          hint={e.penalty_if_cheapest ? `about ${money(e.penalty_if_cheapest, cur)} if the cheapest option is chosen` : undefined}
        />
      </div>

      <Panel
        title={a.feasible ? `${a.order_key} can be protected` : a.at_risk ? `${a.order_key} cannot meet ${a.due}` : `${a.order_key} is on time`}
        subtitle={`Due ${a.due} · current plan delivers ${a.baseline.delivery ?? "an undated day"}${a.recommended_delivery ? ` · protected delivery ${a.recommended_delivery}` : ""} · planned on ${a.today}`}
      >
        <div
          className={`rounded-control border p-3 text-sm text-ink ${a.feasible ? "border-accent/30 bg-accent-soft/40" : "border-signal/35 bg-signal-soft/50"}`}
          data-testid="commitment-recommendation"
        >
          {!a.at_risk ? (
            <p>The current plan already meets the customer date; no premium sourcing is proposed.</p>
          ) : (
            a.explanation.map((x) => <p key={x} className="mt-1 first:mt-0">{x}</p>)
          )}
          {a.fallbacks.length > 0 && (
            <>
              <p className="mt-2 font-medium">Fallbacks to discuss</p>
              <ul className="mt-1 list-disc space-y-0.5 pl-5" data-testid="commitment-fallbacks">
                {a.fallbacks.map((f) => <li key={f}>{f}</li>)}
              </ul>
            </>
          )}
        </div>

        {a.critical.length > 0 && (
          <p className="mt-3 text-xs text-ink-2">
            Critical material{a.critical.length > 1 ? "s" : ""}:{" "}
            {a.critical.map((c) => `${formatQuantity(c.quantity)} ${c.item_id} needed by ${c.needed_by} (${c.reason})`).join(" · ")}
          </p>
        )}
        {a.options.length > 0 && <div className="mt-4"><OptionsTable a={a} /></div>}

        <div className="mt-4 space-y-2">
          <p className="text-xs text-ink-3">
            Timeline per option: supplier lead time + receiving and inspection → production lead time → shipping days → customer. Premiums are measured against the cheapest <em>eligible</em> offer; unapproved, uncertified or failing suppliers are shown but never recommended.
          </p>
          {e.missing.length > 0 && <p className="text-xs text-signal">Not calculated because data is missing: {e.missing.join("; ")}.</p>}
          {a.limitations.map((l) => <p key={l} className="text-xs text-ink-3">{l}</p>)}
          <PlanningIssues issues={a.issues} />
          <RecommendationNote>Recommendation for a buyer to approve: no purchase order is created, and no customer date is changed.</RecommendationNote>
        </div>
      </Panel>
    </div>
  );
}

export function CommitmentsPage() {
  const params = useSearchParams();
  const list = useCommitments();
  const rows = list.data?.at_risk ?? [];
  const byValue = [...rows].sort((x, y) => Number(y.order_value ?? 0) - Number(x.order_value ?? 0));
  const selected = params.get("order") ?? byValue[0]?.key ?? null;
  const detail = useCommitment(list.data ? selected : null);
  return (
    <div className="mx-auto max-w-[96rem] space-y-8">
      <PageHeader
        title="Commitment protection"
        description="Delivery-first procurement for late customer orders: which supplier or split still meets the customer date across supplier lead time, receiving, production and shipping: what it costs against the cheapest eligible offer, and the revenue, margin and penalties at stake."
      />
      <Panel title="Customer order lines at risk" subtitle="Open lines the current plan delivers late or cannot date, highest order value first. Select one to compare sourcing options.">
        {list.isPending ? <Skeleton className="h-40 w-full" /> : list.error ? <ErrorState error={list.error} /> : (
          <AtRiskList rows={byValue} selected={selected} onSelect={(key) => window.history.replaceState(null, "", `/commitments?order=${encodeURIComponent(key)}`)} />
        )}
      </Panel>
      {selected && (detail.isPending ? (
        <Skeleton className="h-96 w-full" />
      ) : detail.error ? (
        <Panel title={selected}><ErrorState error={detail.error} /></Panel>
      ) : detail.data ? (
        <Analysis a={detail.data} />
      ) : null)}
    </div>
  );
}
