"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, CircleAlert, Database, Lock, PlugZap, ShieldCheck, TriangleAlert } from "lucide-react";
import { useState } from "react";

import { ErrorState, Panel, Skeleton } from "@/components/data/widget";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { api } from "@/lib/api";
import { formatCount, formatTimestamp, humanize } from "@/lib/format";

import { SuggestionTable, type Suggestions } from "./mapping-panel";

type Source = {
  kind: "duckdb" | "sql";
  engine: string;
  healthy: boolean;
  data_as_of: string | null;
  stale: boolean;
  stale_after_hours: number;
  classification: string;
  datasets: { dataset: string; source_object: string; rows: number | null }[];
};

type Probe =
  | { ok: false; code: string; message: string }
  | {
      ok: true;
      backend: string;
      read_only: { status: "proved" | "writable" | "not_checked"; detail: string };
      object_count: number;
      objects: { schema: string | null; name: string; kind: string }[];
      truncated: boolean;
    };

const ENGINES = [
  ["PostgreSQL", "postgresql+psycopg://reader:•••@host:5432/erp"],
  ["SQL Server", "mssql+pyodbc://reader:•••@host/erp?driver=ODBC+Driver+18+for+SQL+Server"],
  ["MySQL", "mysql+pymysql://reader:•••@host:3306/erp"],
  ["Oracle", "oracle+oracledb://reader:•••@host:1521/?service_name=ERP"],
] as const;

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <p className="eyebrow">{label}</p>
      <div className="mt-1 text-sm text-ink">{children}</div>
    </div>
  );
}

/** Admin › Data source: the tenant's current source, and a read-only test for a new one (V1 Connect step). */
type Saved = { saved: boolean; store_available: boolean; in_use?: boolean; backend?: string; saved_by?: string; saved_at?: string };

export function SourcePanel() {
  const source = useQuery({ queryKey: ["admin-source"], queryFn: () => api.get<Source>("/api/admin/source") });
  const saved = useQuery({ queryKey: ["admin-source-saved"], queryFn: () => api.get<Saved>("/api/admin/source/saved") });
  return (
    <div className="space-y-6">
      <Panel title="Current data source" subtitle="What this workspace reads, how fresh it is, and how much each mapped table holds. No values are shown.">
        {source.isPending ? (
          <Skeleton className="h-40 w-full" />
        ) : source.error ? (
          <ErrorState error={source.error} />
        ) : (
          <div className="space-y-6" data-testid="source-status">
            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
              <Fact label="Source">
                <span className="inline-flex items-center gap-2">
                  <Database size={15} className="text-ink-3" aria-hidden />
                  {source.data.kind === "duckdb" ? "Local file (DuckDB)" : humanize(source.data.engine)}
                </span>
              </Fact>
              <Fact label="Status">
                {source.data.healthy ? (
                  <Badge tone="ok">
                    <CheckCircle2 size={12} aria-hidden /> Answering
                  </Badge>
                ) : (
                  <Badge tone="signal">
                    <CircleAlert size={12} aria-hidden /> Not reachable
                  </Badge>
                )}
              </Fact>
              <Fact label="Data as of">
                <span className={source.data.stale ? "text-signal" : undefined}>
                  {formatTimestamp(source.data.data_as_of)}
                  {source.data.stale && ` · older than ${source.data.stale_after_hours} h`}
                </span>
              </Fact>
              <Fact label="Classification">{humanize(source.data.classification)}</Fact>
            </div>
            {saved.data && (
              <p className="flex flex-wrap items-center gap-2 text-sm text-ink-2" data-testid="source-saved-status">
                <Lock size={14} className="text-ink-3" aria-hidden />
                {saved.data.saved
                  ? `A ${humanize(saved.data.backend ?? "")} connection is saved, encrypted, by ${saved.data.saved_by} (${formatTimestamp(saved.data.saved_at ?? null)})${saved.data.in_use ? " and in use." : "; not in use until the workspace configuration says secret_ref: store."}`
                  : saved.data.store_available
                    ? "No saved connection. Test one below and save it, encrypted."
                    : "Saving connections is off: the server has no encryption key (LUMIANT_SECRET_KEY)."}
              </p>
            )}
            <ul className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
              {source.data.datasets.map((d) => (
                <li key={d.dataset} className="flex items-center justify-between gap-3 rounded-control border border-line bg-surface-2 px-3 py-2">
                  <span className="min-w-0">
                    <span className="block truncate text-sm text-ink">{humanize(d.dataset)}</span>
                    <span className="code block truncate text-caption text-ink-3">{d.source_object}</span>
                  </span>
                  <span className="figure shrink-0 text-sm text-ink-2">{d.rows === null ? "–" : `${formatCount(d.rows)} rows`}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </Panel>
      <TestConnection />
    </div>
  );
}

function TestConnection() {
  const [url, setUrl] = useState("");
  const test = useMutation({ mutationFn: (u: string) => api.post<Probe>("/api/admin/source/test", { url: u }) });
  const qc = useQueryClient();
  const save = useMutation({
    mutationFn: (u: string) => api.post<{ ok: boolean; saved?: boolean; message?: string }>("/api/admin/source/save", { url: u }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["admin-source-saved"] }),
  });
  const suggest = useMutation({
    mutationFn: (u: string) => api.post<({ ok: true } & Suggestions) | { ok: false; message: string }>("/api/admin/source/suggest", { url: u }),
  });
  const result = test.data;
  return (
    <Panel
      title="Test a new connection"
      subtitle="Lumiant connects read-only, checks the account cannot change data, and lists the tables it can see. The address is used once and never stored or logged."
    >
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          if (url.trim()) test.mutate(url.trim());
        }}
      >
        <Field label="Connection URL" hint="Use an account that can only read the approved views.">
          <Input
            type="password"
            autoComplete="off"
            spellCheck={false}
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="postgresql+psycopg://reader:password@host:5432/erp"
            data-testid="source-url"
          />
        </Field>
        <div className="flex flex-wrap items-center gap-3">
          <Button type="submit" variant="primary" disabled={!url.trim() || test.isPending} data-testid="source-test">
            <PlugZap size={15} aria-hidden /> {test.isPending ? "Testing…" : "Test connection"}
          </Button>
          <span className="text-xs text-ink-3">Formats:</span>
          {ENGINES.map(([name, example]) => (
            <button key={name} type="button" className="text-xs text-accent hover:underline" onClick={() => setUrl(example)}>
              {name}
            </button>
          ))}
        </div>
      </form>

      {test.error && (
        <div className="mt-4">
          <ErrorState error={test.error} />
        </div>
      )}
      {result && !result.ok && (
        <p role="alert" className="mt-4 flex items-start gap-2 text-sm text-ink" data-testid="source-result">
          <TriangleAlert size={15} className="mt-0.5 shrink-0 text-signal" aria-hidden />
          {result.message}
        </p>
      )}
      {result?.ok && (
        <div className="mt-5 space-y-4" data-testid="source-result">
          <div className="flex flex-wrap items-center gap-2 text-sm text-ink">
            <Badge tone="ok">
              <CheckCircle2 size={12} aria-hidden /> Connected to {humanize(result.backend)}
            </Badge>
            {result.read_only.status === "proved" ? (
              <Badge tone="ok">
                <ShieldCheck size={12} aria-hidden /> Read-only confirmed
              </Badge>
            ) : (
              <Badge tone="signal">
                <TriangleAlert size={12} aria-hidden /> {result.read_only.status === "writable" ? "Account can write" : "Read-only not checked"}
              </Badge>
            )}
            <span className="text-ink-2">
              {formatCount(result.object_count)} tables and views visible{result.truncated && ", first 300 listed"}
            </span>
          </div>
          <p className="text-sm text-ink-2">{result.read_only.detail}</p>
          <ul className="flex max-h-48 flex-wrap gap-1.5 overflow-auto" tabIndex={0} aria-label="Tables and views found">
            {result.objects.map((o) => (
              <li key={`${o.schema}.${o.name}`} className="code rounded-control border border-line bg-surface-2 px-2 py-0.5 text-caption text-ink-2">
                {o.schema ? `${o.schema}.` : ""}
                {o.name}
              </li>
            ))}
          </ul>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="primary"
              onClick={() => save.mutate(url.trim())}
              disabled={save.isPending || result.read_only.status === "writable"}
              data-testid="source-save"
            >
              <Lock size={14} aria-hidden /> {save.isPending ? "Saving…" : "Save this connection"}
            </Button>
            <Button onClick={() => suggest.mutate(url.trim())} disabled={suggest.isPending} data-testid="source-suggest">
              {suggest.isPending ? "Reading names…" : "Suggest a mapping"}
            </Button>
            <span className="text-xs text-ink-3">Reads table and column names only, never values.</span>
          </div>
          {save.error && <ErrorState error={save.error} />}
          {save.data?.saved && (
            <p role="status" className="flex items-center gap-2 text-sm text-ink" data-testid="source-saved">
              <ShieldCheck size={15} className="text-ok" aria-hidden /> Saved, encrypted, for this workspace. It is used once the workspace
              configuration says <span className="code">secret_ref: store</span>.
            </p>
          )}
          {suggest.data && !suggest.data.ok && <p className="text-sm text-signal">{suggest.data.message}</p>}
          {suggest.data?.ok && <SuggestionTable data={suggest.data} />}
          <div className="rounded-panel border border-line bg-surface-2 p-4 text-sm text-ink-2">
            <p className="font-medium text-ink">Next: map the tables</p>
            <p className="mt-1">
              Put this URL in the server environment (for example <span className="code">LUMIANT_SOURCE_URL</span>), point the workspace at it with{" "}
              <span className="code">connection: {"{type: sql, secret_ref: env:LUMIANT_SOURCE_URL}"}</span>, and map its tables to the inventory model. Then
              check the totals on the Reconciliation tab before anyone relies on them.
            </p>
          </div>
        </div>
      )}
    </Panel>
  );
}
