"use client";

import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, CircleAlert, Copy, MinusCircle, TriangleAlert } from "lucide-react";
import { useState } from "react";

import { ErrorState, Panel, Skeleton } from "@/components/data/widget";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { formatCount, humanize } from "@/lib/format";

export type Suggestion = {
  dataset: string;
  source: string | null;
  confidence: "high" | "medium" | "low" | "none";
  score: number;
  fields: Record<string, string>;
  missing_required: string[];
  reasons: string[];
  alternatives: string[];
  current_source?: string | null;
  agrees?: boolean;
};
export type Suggestions = { datasets: Suggestion[]; yaml: string; tables_read: number };

const TONE = { high: "ok", medium: "accent", low: "signal", none: "neutral" } as const;

/** One row per canonical dataset: which table fits, how sure, which fields matched, what is still missing. */
export function SuggestionTable({ data, compare = false }: { data: Suggestions; compare?: boolean }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="space-y-4">
      <ul className="divide-y divide-line rounded-panel border border-line" data-testid="mapping-suggestions">
        {data.datasets.map((d) => (
          <li key={d.dataset} className="grid gap-2 px-4 py-3 md:grid-cols-[12rem_1fr_auto] md:items-center">
            <span className="text-sm font-medium text-ink">{humanize(d.dataset)}</span>
            <span className="min-w-0 text-sm text-ink-2">
              {d.source ? <span className="code text-ink">{d.source}</span> : <span className="text-ink-3">No table fits</span>}
              {d.source && (
                <span className="ml-2 text-xs text-ink-3">
                  {Object.keys(d.fields).length} fields matched
                  {d.missing_required.length > 0 && <span className="text-signal"> · missing {d.missing_required.join(", ")}</span>}
                </span>
              )}
              {d.alternatives.length > 0 && <span className="block text-xs text-ink-3">Also possible: {d.alternatives.join(", ")}</span>}
            </span>
            <span className="flex flex-wrap items-center gap-2 md:justify-end">
              <Badge tone={TONE[d.confidence]}>{d.confidence === "none" ? "Not found" : `${humanize(d.confidence)} confidence`}</Badge>
              {compare && d.current_source !== undefined && (
                d.agrees ? (
                  <Badge tone="ok">
                    <CheckCircle2 size={12} aria-hidden /> Matches current
                  </Badge>
                ) : d.current_source ? (
                  <Badge tone="signal">
                    <TriangleAlert size={12} aria-hidden /> Differs from {d.current_source}
                  </Badge>
                ) : (
                  <Badge>
                    <MinusCircle size={12} aria-hidden /> Not mapped now
                  </Badge>
                )
              )}
            </span>
          </li>
        ))}
      </ul>
      <details className="rounded-panel border border-line bg-surface-2">
        <summary className="cursor-pointer px-4 py-3 text-sm font-medium text-ink">Draft mapping (YAML) for review</summary>
        <div className="relative border-t border-line">
          <Button
            size="sm"
            variant="ghost"
            className="absolute top-2 right-2"
            onClick={() => {
              void navigator.clipboard?.writeText(data.yaml);
              setCopied(true);
            }}
          >
            <Copy size={13} aria-hidden /> {copied ? "Copied" : "Copy"}
          </Button>
          <pre className="code max-h-96 overflow-auto p-4 text-xs text-ink-2" tabIndex={0}>
            {data.yaml}
          </pre>
        </div>
      </details>
    </div>
  );
}

/** Admin › Mapping: a second opinion on the mapping in force, from the source's names alone. */
export function MappingPanel() {
  const q = useQuery({ queryKey: ["admin-mapping-suggest"], queryFn: () => api.get<Suggestions>("/api/admin/mapping/suggest") });
  return (
    <Panel
      title="Mapping review"
      subtitle="Lumiant reads only table and column names and suggests where each part of the inventory model lives. A person approves every line; nothing changes until the configuration is updated and reconciliation passes."
    >
      {q.isPending ? (
        <Skeleton className="h-64 w-full" />
      ) : q.error ? (
        <ErrorState error={q.error} />
      ) : (
        <div className="space-y-3">
          <p className="text-sm text-ink-2">
            {formatCount(q.data.tables_read)} tables read ·{" "}
            {formatCount(q.data.datasets.filter((d) => d.agrees).length)} of {formatCount(q.data.datasets.filter((d) => d.current_source).length)} mapped
            datasets agree with the suggestion
          </p>
          <SuggestionTable data={q.data} compare />
        </div>
      )}
    </Panel>
  );
}

type Check = { id: string; title: string; status: "ok" | "issue" | "not_run"; count: number | null; total: number | null; detail: string };

/** Admin › Validation: keys unique, no orphans, required values present: the structure a mapping must pass. */
export function ValidationPanel() {
  const q = useQuery({ queryKey: ["admin-validation"], queryFn: () => api.get<{ passed: boolean; checks: Check[] }>("/api/admin/validation") });
  return (
    <Panel title="Structural validation" subtitle="Run before go-live and after every mapping change. Counts only; no values leave the source.">
      {q.isPending ? (
        <Skeleton className="h-64 w-full" />
      ) : q.error ? (
        <ErrorState error={q.error} />
      ) : (
        <div className="space-y-4" data-testid="validation-result">
          <p className="flex items-center gap-2 text-sm font-medium text-ink">
            {q.data.passed ? (
              <>
                <CheckCircle2 size={16} className="text-ok" aria-hidden /> All structural checks passed
              </>
            ) : (
              <>
                <CircleAlert size={16} className="text-signal" aria-hidden /> Some checks need attention
              </>
            )}
          </p>
          <ul className="divide-y divide-line rounded-panel border border-line">
            {q.data.checks.map((c) => (
              <li key={c.id} className="flex items-start gap-3 px-4 py-3">
                {c.status === "ok" ? (
                  <CheckCircle2 size={15} className="mt-0.5 shrink-0 text-ok" aria-hidden />
                ) : c.status === "issue" ? (
                  <CircleAlert size={15} className="mt-0.5 shrink-0 text-signal" aria-hidden />
                ) : (
                  <MinusCircle size={15} className="mt-0.5 shrink-0 text-ink-3" aria-hidden />
                )}
                <span className="min-w-0 flex-1">
                  <span className="block text-sm text-ink">{c.title}</span>
                  <span className="block text-xs text-ink-3">{c.detail}</span>
                </span>
                <span className="figure shrink-0 text-sm text-ink-2">
                  {c.status === "not_run" ? "Not run" : c.status === "ok" ? "OK" : `${formatCount(c.count)} of ${formatCount(c.total)}`}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Panel>
  );
}
