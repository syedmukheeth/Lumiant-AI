"use client";

import { useQuery } from "@tanstack/react-query";
import { clsx } from "clsx";
import { ArrowUpRight, Info, KeyRound, OctagonAlert, RefreshCw, Sparkles, TriangleAlert } from "lucide-react";
import Link from "next/link";

import { analyzableProps } from "@/components/analyst/analyzable";
import { analyze } from "@/components/analyst/store";
import { ErrorState, Skeleton } from "@/components/data/widget";
import { Button, buttonClass } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import type { Selection, SelectionKind } from "@/lib/agent";
import { api } from "@/lib/api";
import { formatCount, formatMoney, formatNumber, humanize } from "@/lib/format";
import { enterDelay } from "@/lib/motion";

type Metric = { kind: "money" | "pct" | "count"; label?: string; currency?: string; value: string | number };
type Insight = {
  id: string;
  severity: "critical" | "warning" | "info";
  category: string;
  title: string;
  detail: string;
  ask: string;
  metrics: Metric[];
  link: { page: string; filters?: Record<string, string> } | null;
  selection: { kind: SelectionKind; id: string } | null;
};
type Gap = { id: string; message: string; needs: string };
type FailedCheck = { id: string; label: string; code: string; message: string };
type Feed = { insights: Insight[]; gaps: Gap[]; failed: FailedCheck[]; complete: boolean; generated_at: string };

const SEVERITY = {
  critical: { icon: OctagonAlert, tone: "text-(--status-critical)", edge: "before:bg-(--status-critical)", label: "Critical" },
  warning: { icon: TriangleAlert, tone: "text-signal", edge: "before:bg-(--status-warning)", label: "Watch" },
  info: { icon: Info, tone: "text-accent", edge: "before:bg-accent", label: "Insight" },
} as const;

function metricText(m: Metric) {
  if (m.kind === "money") return formatMoney(String(m.value), m.currency, { compact: true });
  if (m.kind === "pct") return `${formatNumber(String(m.value), { maxFraction: 1 })}%`;
  return formatCount(String(m.value));
}

function href(link: Insight["link"]) {
  if (!link) return null;
  const qs = new URLSearchParams(link.filters ?? {}).toString();
  return `/${link.page}${qs ? `?${qs}` : ""}`;
}

export function useInsights() {
  return useQuery({ queryKey: ["insights"], queryFn: () => api.get<Feed>("/api/insights"), staleTime: 60_000 });
}

/** "What needs attention": ranked findings from the deterministic insight rules, each one a click from the Analyst. */
export function InsightsFeed() {
  const feed = useInsights();
  const items = feed.data?.insights ?? [];
  const failed = feed.data?.failed ?? [];
  return (
    <section aria-label="Insights" className="rise space-y-3" data-testid="insights-feed">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <h2 className="text-section font-semibold text-ink">What needs attention</h2>
        <Button variant="ghost" size="sm" onClick={() => void feed.refetch()} aria-label="Refresh insights">
          <RefreshCw size={12} className={clsx(feed.isFetching && "animate-spin")} aria-hidden />
          {feed.data ? `Checked ${new Date(feed.data.generated_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}` : "Checking…"}
        </Button>
      </div>

      {failed.length > 0 && (
        <div role="alert" className="panel flex items-start gap-2 border-signal/40 p-4 text-sm text-ink" data-testid="insights-incomplete">
          <TriangleAlert size={15} className="mt-0.5 shrink-0 text-signal" aria-hidden />
          <p>
            <strong className="font-semibold">
              {items.length === 0 ? "Your data could not be checked, so this does not mean all is well." : "This picture is incomplete."}
            </strong>{" "}
            <span className="text-ink-2">Not checked: {failed.map((f) => f.label).join(", ")}. Refresh to try again.</span>
          </p>
        </div>
      )}

      {feed.isPending ? (
        <div className="grid gap-3 @2xl:grid-cols-2 @7xl:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
      ) : feed.error ? (
        <div className="panel p-4">
          <ErrorState error={feed.error} />
        </div>
      ) : items.length === 0 ? (
        failed.length === 0 && <EmptyState title="Nothing stands out in the analyses available for your data." />
      ) : (
        <ol className="grid gap-3 @2xl:grid-cols-2 @7xl:grid-cols-3">
          {items.map((it, i) => {
            const s = SEVERITY[it.severity];
            const Icon = s.icon;
            const sel: Selection = it.selection ? { ...it.selection, label: humanize(it.selection.id) } : { kind: "insight", id: it.id, label: it.title };
            const to = href(it.link);
            return (
              <li
                key={it.id}
                {...analyzableProps({ kind: "insight", id: it.id, label: it.title.slice(0, 120) })}
                className={clsx(
                  "rise panel group/ins relative flex flex-col gap-2 overflow-hidden p-4 pl-5 transition-colors hover:border-line-strong sm:p-5 sm:pl-6",
                  "before:absolute before:inset-y-3 before:left-0 before:w-0.5 before:rounded-full",
                  s.edge,
                )}
                style={enterDelay(i)}
                data-testid="insight-card"
                onContextMenu={(e) => {
                  if (e.shiftKey) return;
                  e.preventDefault();
                  analyze(sel, { ask: it.ask });
                }}
              >
                <div className="flex items-center gap-2">
                  <Icon size={14} className={s.tone} aria-hidden />
                  <span className={clsx("text-xs font-medium", s.tone)}>{s.label}</span>
                  <span className="ml-auto truncate text-xs text-ink-3 first-letter:uppercase">{it.category}</span>
                </div>
                <p className="text-title leading-snug font-semibold text-ink">{it.title}</p>
                <p className="text-xs leading-relaxed text-ink-3">{it.detail}</p>
                {it.metrics.length > 0 && (
                  <div className="flex flex-wrap gap-x-5 gap-y-1 pt-1">
                    {it.metrics.map((m, j) => (
                      <span key={j} className="flex flex-col">
                        <span className="figure text-base font-semibold text-ink">{metricText(m)}</span>
                        <span className="text-caption text-ink-3">{m.label ?? (m.kind === "money" ? "Value" : "Count")}</span>
                      </span>
                    ))}
                  </div>
                )}
                <div className="mt-auto flex items-center gap-2 pt-2">
                  <Button variant="soft" size="sm" onClick={() => analyze(sel, { ask: it.ask })}>
                    <Sparkles size={12} aria-hidden /> Analyze
                  </Button>
                  {to && (
                    <Link href={to} className={buttonClass({ variant: "ghost", size: "sm" })}>
                      Open <ArrowUpRight size={12} aria-hidden />
                    </Link>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
      )}

      {(feed.data?.gaps.length ?? 0) > 0 && (
        <div className="panel flex flex-col gap-2 p-4" aria-label="Analyses waiting for data">
          <p className="flex items-center gap-1.5 text-dense font-medium text-ink-2">
            <KeyRound size={13} aria-hidden /> Unlock more analyses
          </p>
          <ul className="grid gap-2 text-xs @2xl:grid-cols-2">
            {feed.data?.gaps.map((g) => (
              <li key={g.id} className="rounded-control border border-dashed border-line-strong px-3 py-2">
                <span className="font-medium text-ink-2">{humanize(g.id)}</span>
                <span className="text-ink-3">: needs {g.needs || "more source data"}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
