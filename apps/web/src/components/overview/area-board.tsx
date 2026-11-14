"use client";

import { ArrowRight, Boxes, type LucideIcon, ShieldAlert, ShieldCheck, Sparkles, Truck } from "lucide-react";
import Link from "next/link";

import { ask, clearSelections } from "@/components/analyst/store";
import { ErrorState, Skeleton } from "@/components/data/widget";
import { Chip } from "@/components/ui/badge";
import { ApiError, type Me } from "@/lib/api";
import { formatCount, formatMoney, formatNumber, humanize } from "@/lib/format";
import { useBelowReorder, useDataQuality, useMetric, useRisk } from "@/lib/hooks";
import { enterDelay } from "@/lib/motion";

/**
 * The four areas that cover inventory management. Each shows its standing figures without the user asking anything,
 * and offers the drill-down questions that area usually leads to; a question opens the Analyst and asks it.
 */

const DORMANT_DAYS = 180;
const EXPIRY_DAYS = 60;

type Figure = { label: string; value?: React.ReactNode; pending?: boolean; error?: unknown; testId?: string };

function Area({
  index,
  icon: Icon,
  title,
  question,
  figures,
  questions,
  canAsk,
  href,
  linkLabel,
  testId,
}: {
  index: number;
  icon: LucideIcon;
  title: string;
  question: string;
  figures: Figure[];
  questions: string[];
  canAsk: boolean;
  href?: string;
  linkLabel: string;
  testId: string;
}) {
  return (
    <section className="rise panel flex min-w-0 flex-col gap-4 p-4 sm:p-5" style={enterDelay(index)} aria-label={title} data-testid={testId}>
      <header className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span className="flex size-8 shrink-0 items-center justify-center rounded-control border border-line bg-surface-2 text-accent">
            <Icon size={16} aria-hidden />
          </span>
          <div>
            <h2 className="text-title font-semibold text-ink">{title}</h2>
            <p className="text-xs text-ink-3">{question}</p>
          </div>
        </div>
        {href && (
          <Link href={href} className="flex shrink-0 items-center gap-1 rounded-control text-xs font-medium text-ink-3 transition-colors hover:text-accent">
            {linkLabel} <ArrowRight size={12} aria-hidden />
          </Link>
        )}
      </header>

      <dl className="grid grid-cols-2 gap-4">
        {figures.map((f) => (
          <div key={f.label} className="min-w-0" data-testid={f.testId}>
            <dt className="text-xs text-ink-3">{f.label}</dt>
            <dd className="mt-1 min-h-7">
              {f.pending ? <Skeleton className="h-6 w-24" /> : f.error ? <FigureError error={f.error} /> : f.value}
            </dd>
          </div>
        ))}
      </dl>

      {/* No questions where the data cannot answer them: they would only lead to a refusal. */}
      {canAsk && !figures.every((f) => f.error) && (
        <div className="mt-auto border-t border-line pt-3">
          <p className="mb-2 flex items-center gap-1.5 text-xs text-ink-3">
            <Sparkles size={12} className="text-accent" aria-hidden /> Ask next
          </p>
          <ul className="flex flex-wrap gap-1.5" aria-label={`Questions about ${title.toLowerCase()}`}>
            {questions.map((q) => (
              <li key={q}>
                <Chip
                  size="sm"
                  onClick={() => {
                    // A general question: drop anything pointed at earlier, so its chip doesn't sit above an
                    // unrelated answer (and the question isn't narrowed to it).
                    clearSelections();
                    void ask(q);
                  }}
                >
                  {q}
                </Chip>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

const Big = ({ children, tone }: { children: React.ReactNode; tone?: "signal" }) => (
  <span className={`figure text-xl font-semibold leading-tight tracking-[-0.015em] ${tone === "signal" ? "text-signal" : "text-ink"}`}>{children}</span>
);
const Small = ({ children }: { children: React.ReactNode }) => <span className="block text-xs text-ink-3">{children}</span>;
const Unavailable = () => <span className="text-xs text-ink-3">Not in your access</span>;

/** A tenant whose data lacks the fields an analysis needs gets a plain note, not an error screen. */
function FigureError({ error }: { error: unknown }) {
  if (error instanceof ApiError && error.status >= 400 && error.status < 500 && error.status !== 401 && error.status !== 403) {
    return (
      <>
        <span className="text-sm text-ink-2">Needs more data</span>
        <Small>{error.message}</Small>
      </>
    );
  }
  return <ErrorState error={error} />;
}

/** The largest category by value, in the first currency; amounts in other currencies are never added in. */
function largest(rows: Record<string, unknown>[], labelField: string, nice = false) {
  const currency = [...new Set(rows.map((r) => String(r.currency ?? "")))].filter(Boolean).sort()[0];
  const same = rows.filter((r) => r.currency === currency);
  const total = same.reduce((s, r) => s + Number(r.value ?? 0), 0);
  const top = same.reduce<Record<string, unknown> | null>((best, r) => (!best || Number(r.value) > Number(best.value) ? r : best), null);
  if (!top || total <= 0) return null;
  const label = String(top[labelField] || top.warehouse_id || "Not set");
  return { name: nice ? humanize(label) : label, value: formatMoney(String(top.value), String(currency)), share: (Number(top.value) / total) * 100 };
}

function useLargest(label: string, metric: string, labelField: string, canSeeValue: boolean, nice = false): Figure {
  const { data, isPending, error } = useMetric(metric, canSeeValue);
  if (!canSeeValue) return { label, value: <Small>Your role cannot view values</Small> };
  const top = largest(data?.data ?? [], labelField, nice);
  return {
    label,
    pending: isPending,
    error,
    value: top ? (
      <>
        <span className="block truncate text-sm font-medium text-ink" title={top.name}>
          {top.name}
        </span>
        <Small>
          {top.value} · {formatNumber(top.share, { maxFraction: 0 })}% of value
        </Small>
      </>
    ) : (
      <Small>No valued stock</Small>
    ),
  };
}

export function AreaBoard({ me, canSeeValue }: { me: Me; canSeeValue: boolean }) {
  const sections = new Set(me.sections);
  const canAsk = sections.has("assistant");
  const seesRisks = sections.has("risks");

  const topWarehouse = useLargest("Largest warehouse", "inventory_value_by_warehouse", "warehouse.name", canSeeValue);
  const topGroup = useLargest("Largest item group", "inventory_value_by_item_group", "item.item_group", canSeeValue, true);
  const below = useBelowReorder({ offset: 0, limit: 1 });
  // Risk analyses belong to the Risks section: a role without it is not asked for them at all.
  const excess = useRisk("excess-stock", { limit: 1, offset: 0 }, seesRisks);
  const dormant = useRisk("dormant", { limit: 1, offset: 0, days: DORMANT_DAYS }, seesRisks);
  const expiring = useRisk("expiring-lots", { limit: 1, days: EXPIRY_DAYS }, seesRisks);
  const quality = useDataQuality(seesRisks);
  const gated = (f: Figure): Figure => (seesRisks ? f : { label: f.label, value: <Unavailable /> });

  const issues = quality.data?.checks.filter((c) => c.status === "issue") ?? [];
  const exp = expiring.data?.summary;

  return (
    <div className="space-y-3" data-testid="area-board">
      <div>
        <h2 className="text-section font-semibold text-ink">Inventory at a glance</h2>
        <p className="mt-1 text-sm text-ink-3">Four areas cover the whole of inventory management. Start from any of them and ask the next question.</p>
      </div>
      <div className="grid grid-cols-1 gap-4 @3xl:grid-cols-2">
        <Area
          index={0}
          testId="area-position"
          icon={Boxes}
          title="Stock position"
          question="What do we hold, where, and what is it worth?"
          href="/inventory"
          linkLabel="Inventory"
          canAsk={canAsk}
          figures={[topWarehouse, topGroup]}
          questions={[
            "Which warehouse holds the most stock?",
            "Break stock down by item group",
            ...(canSeeValue ? ["Show the highest-value items", "Which items make up most of the value?"] : []),
          ]}
        />
        <Area
          index={1}
          testId="area-replenishment"
          icon={Truck}
          title="Replenishment"
          question="What do we need to order, and where do we hold too much?"
          href="#below-reorder"
          linkLabel="Reorder list"
          canAsk={canAsk}
          figures={[
            gated({
              label: "Above maximum stock",
              pending: excess.isPending,
              error: excess.error,
              value: (
                <>
                  <Big>{formatCount(excess.data?.summary?.flagged)}</Big>
                  <Small>item–warehouse pairs</Small>
                </>
              ),
            }),
            {
              label: "No reorder policy",
              pending: below.isPending,
              error: below.error,
              value: (
                <>
                  <Big tone="signal">{formatCount(below.data?.summary?.pairs_without_policy)}</Big>
                  <Small>item–warehouse pairs never flagged</Small>
                </>
              ),
            },
          ]}
          questions={[
            "Which items are below reorder level?",
            "Which items have excess stock?",
          ]}
        />
        <Area
          index={2}
          testId="area-health"
          icon={ShieldAlert}
          title="Stock health"
          question="What is at risk of becoming waste?"
          href={seesRisks ? "/risks" : undefined}
          linkLabel="Risks"
          canAsk={canAsk}
          figures={[
            gated({
              label: `No issues in ${DORMANT_DAYS} days`,
              pending: dormant.isPending,
              error: dormant.error,
              value: (
                <>
                  <Big tone="signal">{formatCount(dormant.data?.summary?.flagged)}</Big>
                  <Small>dormant item–warehouse pairs</Small>
                </>
              ),
            }),
            gated({
              label: "Lots expired",
              pending: expiring.isPending,
              error: expiring.error,
              value: (
                <>
                  <Big tone="signal">{formatCount(exp?.expired)}</Big>
                  <Small>
                    {formatCount(exp?.expiring)} more expire within {EXPIRY_DAYS} days
                  </Small>
                </>
              ),
            }),
          ]}
          questions={[
            `Which stock has not moved in ${DORMANT_DAYS} days?`,
            "Which lots have already expired?",
            "Which lots expire in the next 30 days?",
          ]}
        />
        <Area
          index={3}
          testId="area-trust"
          icon={ShieldCheck}
          title="Cost and data trust"
          question="Can we rely on the numbers, and where does the value sit?"
          href={sections.has("costs") ? "/costs" : seesRisks ? "/risks" : undefined}
          linkLabel={sections.has("costs") ? "Costs" : "Data quality"}
          canAsk={canAsk}
          figures={[
            gated({
              label: "Data checks needing attention",
              pending: quality.isPending,
              error: quality.error,
              value: (
                <>
                  <Big tone={issues.length ? "signal" : undefined}>{formatCount(issues.length)}</Big>
                  <Small>{issues.length ? `First: ${issues[0].title}` : "No gaps found"}</Small>
                </>
              ),
            }),
            gated({
              label: "Items in item master",
              pending: quality.isPending,
              error: quality.error,
              value: <Big>{formatCount(quality.data?.total_items)}</Big>,
            }),
          ]}
          questions={[
            "Which items have incomplete master data?",
            "What should I look at first?",
          ]}
        />
      </div>
    </div>
  );
}
