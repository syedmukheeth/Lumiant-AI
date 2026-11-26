"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { clsx } from "clsx";
import { CheckCircle2, CircleAlert, MinusCircle, TriangleAlert } from "lucide-react";
import { useState } from "react";

import { SimpleTable, type SimpleColumn } from "@/components/data/simple-table";
import { ErrorState, Panel, Skeleton } from "@/components/data/widget";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/field";
import { PageHeader } from "@/components/ui/page-header";
import { Tabs } from "@/components/ui/tabs";
import { api, ApiError, type Me, type Row } from "@/lib/api";
import { formatNumber, formatTimestamp } from "@/lib/format";
import { useMe } from "@/lib/hooks";

type SchemaResult = {
  healthy: boolean;
  verdict: "ok" | "drift";
  totals: Record<string, number>;
  /** Warehouse ids in the source stock data that the tenant configuration does not list. */
  unconfigured_warehouses: string[];
  /** Stock rows with no warehouse id. */
  rows_without_warehouse: number;
  note: string;
  datasets: {
    dataset: string;
    source: string;
    status: string;
    problems: { kind: string; field?: string; column?: string; expected?: string; found?: string }[];
    unmapped: { column: string; type: string }[];
  }[];
};
/** A source id with stray spaces must not look like a configured one: quote it, and name a blank one. */
const warehouseLabel = (id: string) => (id.trim() === "" ? "(blank)" : id === id.trim() ? id : JSON.stringify(id));

type Capability = { id: string; title: string; available: boolean; explanation: string | null };
/** Reconciliation compares exact amounts: group the digits but keep every decimal the source sent (up to 8). */
const exact = (v: unknown) => formatNumber(typeof v === "string" || typeof v === "number" ? v : null, { minFraction: 2, maxFraction: 8 });

type ReconLine = { warehouse_id: string; currency: string; platform: string | null; customer: string | null; difference: string | null; status: string };
type Recon = { passed: boolean; counts: Record<string, number>; lines: ReconLine[]; tolerance: string; note: string };

const TABS = [
  { id: "schema", label: "Connection and schema" },
  { id: "capabilities", label: "Capabilities" },
  { id: "reconciliation", label: "Reconciliation" },
  { id: "audit", label: "Audit log" },
  { id: "demo", label: "Demo requests" },
] as const;
type Tab = (typeof TABS)[number]["id"];

function SchemaPanel() {
  const q = useQuery({ queryKey: ["admin-schema"], queryFn: () => api.get<SchemaResult>("/api/admin/schema"), retry: false });
  return (
    <Panel
      title="Source connection and mapping check"
      subtitle="Compares what the mapping expects with what the source exposes, and checks that every warehouse in the stock data is configured (reads warehouse ids only)"
    >
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
          {q.data.unconfigured_warehouses.length > 0 && (
            <div className="rounded-panel border border-signal/35 bg-signal-soft p-3 text-sm" data-testid="unconfigured-warehouses">
              <p className="flex items-center gap-2 font-semibold text-signal">
                <TriangleAlert size={16} aria-hidden />
                {q.data.unconfigured_warehouses.length === 1 ? "1 warehouse is" : `${q.data.unconfigured_warehouses.length} warehouses are`} missing from the tenant configuration
              </p>
              <p className="mt-1 text-xs text-ink-2">
                They are counted in totals for users who see all warehouses and are invisible to everyone else. Add them to the tenant configuration or exclude them from the source.
              </p>
              <ul className="mt-2 flex flex-wrap gap-1.5" aria-label="Unconfigured warehouses">
                {q.data.unconfigured_warehouses.map((id) => (
                  <li key={id}>
                    <Badge tone="signal" className="code">
                      {warehouseLabel(id)}
                    </Badge>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {q.data.rows_without_warehouse > 0 && (
            <div className="rounded-panel border border-signal/35 bg-signal-soft p-3 text-sm" data-testid="rows-without-warehouse">
              <p className="flex items-center gap-2 font-semibold text-signal">
                <TriangleAlert size={16} aria-hidden />
                {q.data.rows_without_warehouse === 1 ? "1 stock row has" : `${formatNumber(q.data.rows_without_warehouse)} stock rows have`} no warehouse
              </p>
              <p className="mt-1 text-xs text-ink-2">
                They are counted in totals for users who see all warehouses and are invisible to everyone else. Fill in the warehouse in the source or exclude those rows.
              </p>
            </div>
          )}
          <ul className="divide-y divide-line">
            {q.data.datasets.map((d) => (
              <li key={d.dataset} className="py-2.5 text-sm">
                <div className="flex items-baseline justify-between gap-3">
                  <span>
                    <span className="font-medium text-ink">{d.dataset}</span> <span className="code text-xs text-ink-3">{d.source}</span>
                  </span>
                  <span className={clsx("text-xs font-semibold", d.status === "ok" ? "text-ok" : "text-signal")}>{d.status}</span>
                </div>
                {d.problems.map((p, i) => (
                  <p key={i} className="code text-xs text-signal">
                    {p.kind}: {p.field ?? p.column ?? ""} {p.expected ? `(expected ${p.expected}, found ${p.found})` : ""}
                  </p>
                ))}
                {d.unmapped.length > 0 && (
                  <p className="code text-xs text-ink-3">Unmapped columns to review: {d.unmapped.map((u) => u.column).join(", ")}</p>
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
    { key: "w", label: "Warehouse", render: (r) => <span className="code text-xs">{r.warehouse_id}</span> },
    { key: "c", label: "Currency", render: (r) => <span className="text-xs">{r.currency}</span> },
    { key: "p", label: "Platform", align: "right", render: (r) => <span className="figure">{exact(r.platform)}</span> },
    { key: "u", label: "Customer report", align: "right", render: (r) => <span className="figure">{exact(r.customer)}</span> },
    { key: "d", label: "Difference", align: "right", render: (r) => <span className="figure">{exact(r.difference)}</span> },
    { key: "s", label: "Status", render: (r) => <span className={clsx("text-xs font-semibold", r.status === "match" ? "text-ok" : "text-signal")}>{String(r.status).replaceAll("_", " ")}</span> },
  ];
  return (
    <Panel title="Reconciliation against the customer's report" subtitle="Paste the authoritative inventory-value report (warehouse, currency, value). Currencies are compared separately, never converted.">
      <div className="grid gap-3 sm:grid-cols-[1fr_12rem]">
        <Field label="CSV rows: warehouse_id,currency,value">
          <Textarea value={text} onChange={(e) => setText(e.target.value)} rows={6} className="code" aria-label="Customer report rows" />
        </Field>
        <div className="flex flex-col gap-3">
          <Field label="Tolerance (per line)">
            <Input value={tolerance} onChange={(e) => setTolerance(e.target.value)} className="figure" aria-label="Tolerance" />
          </Field>
          <Button variant="primary" onClick={() => run.mutate()} disabled={run.isPending}>
            Reconcile
          </Button>
        </div>
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
    { key: "u", label: "User", render: (r) => <span className="code text-xs">{r.user_id}</span> },
    { key: "a", label: "Action", render: (r) => <span className="code text-xs">{r.action}</span> },
    { key: "d", label: "Decision", render: (r) => <span className={clsx("text-xs font-semibold", r.decision === "deny" ? "text-signal" : "text-ink-2")}>{r.decision}{r.reason ? ` (${r.reason})` : ""}</span> },
    { key: "n", label: "Rows", align: "right", render: (r) => <span className="figure">{r.rows ?? "–"}</span> },
    { key: "m", label: "ms", align: "right", render: (r) => <span className="figure">{r.duration_ms ?? "–"}</span> },
  ];
  return (
    <Panel title="Audit log" subtitle="Who asked for what, and whether it was allowed. Result values and filter values are never stored.">
      {!allowed ? (
        <p className="text-sm text-ink-3">Your role cannot view the audit log.</p>
      ) : (
        <>
          <div className="mb-3 flex flex-wrap gap-3">
            <Select value={decision} onChange={(e) => setDecision(e.target.value)} className="w-44" aria-label="Decision">
              <option value="">All decisions</option>
              <option value="allow">Allowed</option>
              <option value="deny">Denied</option>
            </Select>
            <div className="w-64">
              <Input value={action} onChange={(e) => setAction(e.target.value.replace(/[^A-Za-z0-9_:.-]/g, ""))} placeholder="Action prefix, e.g. export:" maxLength={40} className="code" aria-label="Action prefix" />
            </div>
          </div>
          {q.isPending ? <Skeleton className="h-48 w-full" /> : q.error ? <ErrorState error={q.error} /> : <SimpleTable columns={cols} rows={q.data.events as unknown as Row[]} empty="No events." rowKey={(r) => String(r.id)} minWidth="40rem" />}
        </>
      )}
    </Panel>
  );
}

type DemoRequestRow = { id: number; received_at: string; name: string; email: string; company: string; role: string | null; systems: string | null; message: string | null };

/** Demo requests from the public landing page. Platform data: shown to platform administrators only. */
function DemoRequestsPanel({ me }: { me?: Me }) {
  const allowed = !!me?.roles.includes("super_admin");
  const q = useQuery({
    queryKey: ["admin-demo-requests"],
    queryFn: () => api.get<{ requests: DemoRequestRow[] }>("/api/admin/demo-requests"),
    enabled: allowed,
    retry: false,
  });
  const cols: SimpleColumn[] = [
    { key: "t", label: "Received", render: (r) => <span className="figure text-xs">{formatTimestamp(String(r.received_at))}</span> },
    { key: "n", label: "Name", render: (r) => String(r.name) },
    { key: "c", label: "Company", render: (r) => String(r.company) },
    { key: "e", label: "Email", render: (r) => <span className="code text-xs">{String(r.email)}</span> },
    { key: "s", label: "Systems", render: (r) => (r.systems ? String(r.systems) : <span className="text-ink-3">–</span>) },
    { key: "m", label: "Message", render: (r) => (r.message ? <span className="block max-w-80 truncate" title={String(r.message)}>{String(r.message)}</span> : <span className="text-ink-3">–</span>) },
  ];
  return (
    <Panel title="Demo requests" subtitle="Sent from the public landing page. Personal details: use them only to arrange the demo.">
      {!allowed ? (
        <p className="text-sm text-ink-3">Only platform administrators can view demo requests.</p>
      ) : q.isPending ? (
        <Skeleton className="h-32 w-full" />
      ) : q.error ? (
        <ErrorState error={q.error} />
      ) : (
        <SimpleTable columns={cols} rows={q.data.requests as unknown as Row[]} empty="No demo requests yet." rowKey={(r) => String(r.id)} minWidth="48rem" />
      )}
    </Panel>
  );
}

export function AdminPage() {
  const me = useMe();
  const [tab, setTab] = useState<Tab>("schema");
  return (
    <div className="mx-auto max-w-[96rem] space-y-8">
      <PageHeader
        title="Onboarding and oversight"
        description="Check a data source against its mapping, see what is unlocked, prove numbers against the customer's own reports, and review access."
      />
      <Tabs label="Administration" tabs={TABS} value={tab} onChange={setTab} />
      {tab === "schema" && <SchemaPanel />}
      {tab === "capabilities" && <CapabilitiesPanel />}
      {tab === "reconciliation" && <ReconciliationPanel />}
      {tab === "audit" && <AuditPanel me={me.data} />}
      {tab === "demo" && <DemoRequestsPanel me={me.data} />}
    </div>
  );
}
