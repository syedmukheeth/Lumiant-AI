"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { clsx } from "clsx";
import { CheckCircle2, CircleAlert, MinusCircle } from "lucide-react";
import { useState } from "react";

import { SimpleTable, type SimpleColumn } from "@/components/data/simple-table";
import { ErrorState, Panel, Skeleton } from "@/components/data/widget";
import { api, ApiError, type Me, type Row } from "@/lib/api";
import { formatTimestamp } from "@/lib/format";
import { useMe } from "@/lib/hooks";

type SchemaResult = {
  healthy: boolean;
  verdict: "ok" | "drift";
  totals: Record<string, number>;
  note: string;
  datasets: {
    dataset: string;
    source: string;
    status: string;
    problems: { kind: string; field?: string; column?: string; expected?: string; found?: string }[];
    unmapped: { column: string; type: string }[];
  }[];
};
type Capability = { id: string; title: string; available: boolean; explanation: string | null };
type ReconLine = { warehouse_id: string; currency: string; platform: string | null; customer: string | null; difference: string | null; status: string };
type Recon = { passed: boolean; counts: Record<string, number>; lines: ReconLine[]; tolerance: string; note: string };

const TABS = [
  { id: "schema", label: "Connection and schema" },
  { id: "capabilities", label: "Capabilities" },
  { id: "reconciliation", label: "Reconciliation" },
  { id: "audit", label: "Audit log" },
] as const;
type Tab = (typeof TABS)[number]["id"];

function SchemaPanel() {
  const q = useQuery({ queryKey: ["admin-schema"], queryFn: () => api.get<SchemaResult>("/api/admin/schema"), retry: false });
  return (
    <Panel title="Source connection and mapping check" subtitle="Compares what the mapping expects with what the source exposes (metadata only; no data is read)">
      {q.isPending ? (
        <Skeleton className="h-48 w-full" />
      ) : q.error ? (
        <ErrorState error={q.error} />
      ) : (
        <div className="space-y-3" data-testid="schema-result">
          <p className={clsx("flex items-center gap-2 text-sm font-semibold", q.data.verdict === "ok" ? "text-ok" : "text-signal")}>
            {q.data.verdict === "ok" ? <CheckCircle2 size={16} aria-hidden /> : <CircleAlert size={16} aria-hidden />}
            {q.data.verdict === "ok" ? "Mapping matches the source" : "The source has drifted from the mapping"} · connection {q.data.healthy ? "healthy" : "unavailable"}
          </p>
          <ul className="divide-y divide-line">
            {q.data.datasets.map((d) => (
              <li key={d.dataset} className="py-2 text-sm">
                <div className="flex items-baseline justify-between gap-3">
                  <span>
                    <span className="font-medium text-ink">{d.dataset}</span> <span className="figure text-xs text-ink-3">{d.source}</span>
                  </span>
                  <span className={clsx("text-xs font-semibold", d.status === "ok" ? "text-ok" : "text-signal")}>{d.status}</span>
                </div>
                {d.problems.map((p, i) => (
                  <p key={i} className="figure text-xs text-signal">
                    {p.kind}: {p.field ?? p.column ?? ""} {p.expected ? `(expected ${p.expected}, found ${p.found})` : ""}
                  </p>
                ))}
                {d.unmapped.length > 0 && (
                  <p className="figure text-xs text-ink-3">Unmapped columns to review: {d.unmapped.map((u) => u.column).join(", ")}</p>
                )}
              </li>
            ))}
          </ul>
          <p className="text-xs text-ink-3">{q.data.note}</p>
        </div>
      )}
    </Panel>
  );
}

function CapabilitiesPanel() {
  const q = useQuery({ queryKey: ["admin-caps"], queryFn: () => api.get<{ capabilities: Capability[] }>("/api/admin/capabilities"), retry: false });
  return (
    <Panel title="Capability readiness" subtitle="What this tenant's mapping unlocks, and exactly what is missing for the rest">
      {q.isPending ? (
        <Skeleton className="h-48 w-full" />
      ) : q.error ? (
        <ErrorState error={q.error} />
      ) : (
        <ul className="divide-y divide-line" data-testid="capabilities">
          {q.data.capabilities.map((c) => (
            <li key={c.id} className="flex items-start gap-3 py-2.5">
              {c.available ? <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-ok" aria-hidden /> : <MinusCircle size={16} className="mt-0.5 shrink-0 text-ink-3" aria-hidden />}
              <div>
                <p className="text-sm text-ink">{c.title}</p>
                {c.explanation && <p className="text-xs text-ink-3">{c.explanation}</p>}
              </div>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

const SAMPLE = "warehouse_id,currency,value\n";

function ReconciliationPanel() {
  const [text, setText] = useState(SAMPLE);
  const [tolerance, setTolerance] = useState("0.01");
  const run = useMutation({
    mutationFn: () => {
      const rows = text
        .split(/\r?\n/)
        .map((l) => l.trim())
        .filter((l) => l && !l.toLowerCase().startsWith("warehouse_id"))
        .map((l) => {
          const [warehouse_id, currency, value] = l.split(",").map((x) => x.trim());
          return { warehouse_id, currency, value };
        });
      return api.post<Recon>("/api/admin/reconciliation", { tolerance, rows });
    },
  });
  const cols: SimpleColumn[] = [
    { key: "w", label: "Warehouse", render: (r) => <span className="figure text-xs">{r.warehouse_id}</span> },
    { key: "c", label: "Currency", render: (r) => <span className="figure text-xs">{r.currency}</span> },
    { key: "p", label: "Platform", align: "right", render: (r) => <span className="figure">{r.platform ?? "—"}</span> },
    { key: "u", label: "Customer report", align: "right", render: (r) => <span className="figure">{r.customer ?? "—"}</span> },
    { key: "d", label: "Difference", align: "right", render: (r) => <span className="figure">{r.difference ?? "—"}</span> },
    { key: "s", label: "Status", render: (r) => <span className={clsx("text-xs font-semibold", r.status === "match" ? "text-ok" : "text-signal")}>{String(r.status).replaceAll("_", " ")}</span> },
  ];
  return (
    <Panel title="Reconciliation against the customer's report" subtitle="Paste the authoritative inventory-value report (warehouse, currency, value). Currencies are compared separately, never converted.">
      <div className="grid gap-3 sm:grid-cols-[1fr_12rem]">
        <label className="flex flex-col gap-1">
          <span className="eyebrow">CSV rows: warehouse_id,currency,value</span>
          <textarea value={text} onChange={(e) => setText(e.target.value)} rows={6} className="figure rounded-sm border border-line bg-surface p-2 text-xs" aria-label="Customer report rows" />
        </label>
        <label className="flex flex-col gap-1">
          <span className="eyebrow">Tolerance (per line)</span>
          <input value={tolerance} onChange={(e) => setTolerance(e.target.value)} className="figure h-9 rounded-sm border border-line bg-surface px-2 text-sm" aria-label="Tolerance" />
          <button type="button" onClick={() => run.mutate()} disabled={run.isPending} className="mt-2 h-9 rounded-sm bg-ink px-4 text-sm font-medium text-surface disabled:opacity-40">
            Reconcile
          </button>
        </label>
      </div>
      {run.error && (
        <p role="alert" className="mt-3 text-sm text-signal">
          {run.error instanceof ApiError ? run.error.message : "Reconciliation failed."}
        </p>
      )}
      {run.data && (
        <div className="mt-4 space-y-3" data-testid="recon-result">
          <p className={clsx("text-sm font-semibold", run.data.passed ? "text-ok" : "text-signal")}>
            {run.data.passed ? "Go-live gate passed: every line matches within the tolerance." : "Go-live gate NOT passed."}{" "}
            <span className="figure text-xs font-normal text-ink-3">{Object.entries(run.data.counts).map(([k, v]) => `${k.replaceAll("_", " ")}: ${v}`).join(" · ")}</span>
          </p>
          <SimpleTable columns={cols} rows={run.data.lines as unknown as Row[]} empty="No lines." rowKey={(r) => `${r.warehouse_id}-${r.currency}`} minWidth="38rem" />
          <p className="text-xs text-ink-3">{run.data.note}</p>
        </div>
      )}
    </Panel>
  );
}

type AuditEvent = { id: number; occurred_at: string; user_id: string; action: string; decision: string; reason: string | null; rows: number | null; duration_ms: number | null; status: string };

function AuditPanel({ me }: { me?: Me }) {
  const [decision, setDecision] = useState("");
  const [action, setAction] = useState("");
  const allowed = me?.permissions.includes("audit:read");
  const q = useQuery({
    queryKey: ["admin-audit", decision, action],
    queryFn: () => api.get<{ events: AuditEvent[] }>("/api/admin/audit", { limit: 50, decision: decision || undefined, action: action || undefined }),
    enabled: Boolean(allowed),
    retry: false,
  });
  const cols: SimpleColumn[] = [
    { key: "t", label: "When", render: (r) => <span className="figure text-xs">{formatTimestamp(r.occurred_at as string)}</span> },
    { key: "u", label: "User", render: (r) => <span className="figure text-xs">{r.user_id}</span> },
    { key: "a", label: "Action", render: (r) => <span className="figure text-xs">{r.action}</span> },
    { key: "d", label: "Decision", render: (r) => <span className={clsx("text-xs font-semibold", r.decision === "deny" ? "text-signal" : "text-ink-2")}>{r.decision}{r.reason ? ` (${r.reason})` : ""}</span> },
    { key: "n", label: "Rows", align: "right", render: (r) => <span className="figure">{r.rows ?? "—"}</span> },
    { key: "m", label: "ms", align: "right", render: (r) => <span className="figure">{r.duration_ms ?? "—"}</span> },
  ];
  return (
    <Panel title="Audit log" subtitle="Who asked for what, and whether it was allowed. Result values and filter values are never stored.">
      {!allowed ? (
        <p className="text-sm text-ink-3">Your role cannot view the audit log.</p>
      ) : (
        <>
          <div className="mb-3 flex flex-wrap gap-3">
            <select value={decision} onChange={(e) => setDecision(e.target.value)} className="h-9 rounded-sm border border-line bg-surface px-2 text-sm" aria-label="Decision">
              <option value="">All decisions</option>
              <option value="allow">Allowed</option>
              <option value="deny">Denied</option>
            </select>
            <input value={action} onChange={(e) => setAction(e.target.value.replace(/[^A-Za-z0-9_:.-]/g, ""))} placeholder="Action prefix, e.g. export:" maxLength={40} className="figure h-9 rounded-sm border border-line bg-surface px-2 text-sm" aria-label="Action prefix" />
          </div>
          {q.isPending ? <Skeleton className="h-48 w-full" /> : q.error ? <ErrorState error={q.error} /> : <SimpleTable columns={cols} rows={q.data.events as unknown as Row[]} empty="No events." rowKey={(r) => String(r.id)} minWidth="40rem" />}
        </>
      )}
    </Panel>
  );
}

export function AdminPage() {
  const me = useMe();
  const [tab, setTab] = useState<Tab>("schema");
  return (
    <div className="mx-auto max-w-[96rem] space-y-5">
      <div className="rise">
        <p className="eyebrow">Administration</p>
        <h1 className="mt-1 text-2xl font-bold tracking-tight text-ink sm:text-[1.75rem]">Onboarding and oversight</h1>
        <p className="mt-1 text-sm text-ink-3">Check a data source against its mapping, see what is unlocked, prove numbers against the customer&apos;s own reports, and review access.</p>
      </div>
      <div role="tablist" aria-label="Administration" className="flex flex-wrap gap-1 border-b border-line">
        {TABS.map((t) => (
          <button key={t.id} role="tab" aria-selected={t.id === tab} onClick={() => setTab(t.id)} className={clsx("-mb-px border-b-2 px-3 py-2 text-sm", t.id === tab ? "border-ink font-semibold text-ink" : "border-transparent text-ink-3 hover:text-ink")}>
            {t.label}
          </button>
        ))}
      </div>
      {tab === "schema" && <SchemaPanel />}
      {tab === "capabilities" && <CapabilitiesPanel />}
      {tab === "reconciliation" && <ReconciliationPanel />}
      {tab === "audit" && <AuditPanel me={me.data} />}
    </div>
  );
}
