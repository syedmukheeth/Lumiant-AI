"use client";

import { useQuery } from "@tanstack/react-query";
import { Download, Printer } from "lucide-react";
import { useState } from "react";

import { SimpleTable, type SimpleColumn } from "@/components/data/simple-table";
import { ErrorState, Panel, Skeleton } from "@/components/data/widget";
import { api, type Provenance, type ResultWarning, type Row } from "@/lib/api";
import { formatMoney, formatNumber, formatQuantity } from "@/lib/format";
import { useMe } from "@/lib/hooks";

type ReportInfo = { id: string; title: string; description: string; params: string[] };
type Built = {
  report: { id: string; title: string };
  columns: { key: string; label: string }[];
  rows: Row[];
  metadata: {
    title: string;
    tenant: string;
    generated_at: string;
    data_as_of: string;
    filters: string[];
    access_scope: string;
    rows: number;
    truncated: boolean;
    notices: string[];
    currency_note: string;
    user: string;
  };
  warnings: ResultWarning[];
  provenance: Provenance;
};

const MONEY_KEYS = new Set(["value", "valuation_price", "stock_value"]);
const QTY_KEYS = new Set(["quantity", "on_hand", "reorder_level", "shortfall", "max_stock", "excess"]);

function render(key: string, row: Row) {
  const v = row[key];
  if (v === null || v === undefined || v === "") return <span className="text-ink-3">—</span>;
  if (MONEY_KEYS.has(key)) return <span className="figure">{formatMoney(v as string, row.currency as string | undefined)}</span>;
  if (QTY_KEYS.has(key)) return <span className="figure">{formatQuantity(v as string, row.uom as string | undefined)}</span>;
  if (typeof v === "number") return <span className="figure">{formatNumber(v, { maxFraction: 0 })}</span>;
  return <span>{String(v)}</span>;
}

export function ReportsPage() {
  const me = useMe();
  const list = useQuery({
    queryKey: ["reports"],
    queryFn: () => api.get<{ reports: ReportInfo[]; can_export: boolean }>("/api/reports"),
  });
  const [selected, setSelected] = useState("");
  const [days, setDays] = useState(180);
  const current = list.data?.reports.find((r) => r.id === selected);
  const usesDays = current?.params.includes("days") ?? false;
  const built = useQuery({
    queryKey: ["report", selected, usesDays ? days : null],
    queryFn: () => api.get<Built>(`/api/reports/${selected}${usesDays ? `?days=${days}` : ""}`),
    enabled: Boolean(selected),
    retry: false,
  });
  const columns: SimpleColumn[] = (built.data?.columns ?? []).map((c) => ({
    key: c.key,
    label: c.label,
    align: MONEY_KEYS.has(c.key) || QTY_KEYS.has(c.key) ? "right" : undefined,
    render: (r) => render(c.key, r),
  }));
  const exportUrl = (fmt: string) => `/api/reports/${selected}/export?format=${fmt}${usesDays ? `&days=${days}` : ""}`;
  const meta = built.data?.metadata;
  const linkClass = "inline-flex h-9 items-center gap-1.5 rounded-sm border border-line-strong px-3 text-sm hover:bg-surface-2";

  return (
    <div className="mx-auto max-w-[96rem] space-y-5">
      <div className="rise no-print">
        <p className="eyebrow">Reports</p>
        <h1 className="mt-1 text-2xl font-bold tracking-tight text-ink sm:text-[1.75rem]">Reports and exports</h1>
        <p className="mt-1 text-sm text-ink-3">
          Every report uses the same checked queries as the dashboards, honours your access scope, and carries its filters, data time and source.
        </p>
      </div>

      <div className="no-print grid gap-3 rounded-md border border-line bg-surface p-4 sm:grid-cols-[1fr_auto_auto]">
        <label className="flex flex-col gap-1">
          <span className="eyebrow">Report</span>
          <select value={selected} onChange={(e) => setSelected(e.target.value)} className="h-9 rounded-sm border border-line bg-surface px-2 text-sm" aria-label="Report">
            <option value="">Choose a report…</option>
            {(list.data?.reports ?? []).map((r) => (
              <option key={r.id} value={r.id}>
                {r.title}
              </option>
            ))}
          </select>
        </label>
        {usesDays && (
          <label className="flex flex-col gap-1">
            <span className="eyebrow">Window (days)</span>
            <select value={days} onChange={(e) => setDays(Number(e.target.value))} className="h-9 rounded-sm border border-line bg-surface px-2 text-sm" aria-label="Window in days">
              {[30, 60, 90, 180, 270, 365].map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
          </label>
        )}
        <div className="flex items-end gap-2">
          {list.data?.can_export && selected && (
            <>
              <a href={exportUrl("csv")} download className={linkClass}>
                <Download size={14} aria-hidden /> CSV
              </a>
              <a href={exportUrl("xlsx")} download className={linkClass}>
                <Download size={14} aria-hidden /> Excel
              </a>
            </>
          )}
          {selected && (
            <button type="button" onClick={() => window.print()} className={linkClass}>
              <Printer size={14} aria-hidden /> Print
            </button>
          )}
        </div>
      </div>
      {list.data && !list.data.can_export && <p className="no-print text-xs text-ink-3">Your role can view reports but not export them.</p>}
      {current && <p className="no-print text-sm text-ink-2">{current.description}</p>}

      {selected && (
        <Panel
          title={meta?.title ?? current?.title ?? "Report"}
          provenance={built.data?.provenance}
          warnings={built.data?.warnings}
          subtitle={meta ? `${meta.rows} rows${meta.truncated ? " (truncated)" : ""}` : undefined}
        >
          {built.isPending ? (
            <Skeleton className="h-64 w-full" />
          ) : built.error ? (
            <ErrorState error={built.error} />
          ) : (
            <div data-testid="report-view">
              {meta && (
                <dl className="mb-3 grid grid-cols-1 gap-x-6 gap-y-1 text-xs text-ink-2 sm:grid-cols-2" data-testid="report-meta">
                  <div>
                    <dt className="inline text-ink-3">Organisation: </dt>
                    <dd className="inline">{meta.tenant}</dd>
                  </div>
                  <div>
                    <dt className="inline text-ink-3">Data as of: </dt>
                    <dd className="inline">{meta.data_as_of}</dd>
                  </div>
                  <div>
                    <dt className="inline text-ink-3">Generated: </dt>
                    <dd className="inline">
                      {meta.generated_at} by {meta.user}
                    </dd>
                  </div>
                  <div>
                    <dt className="inline text-ink-3">Access scope: </dt>
                    <dd className="inline">{meta.access_scope}</dd>
                  </div>
                  <div className="sm:col-span-2">
                    <dt className="inline text-ink-3">Filters: </dt>
                    <dd className="inline">{meta.filters.join("; ")}</dd>
                  </div>
                  <div className="text-ink-3 sm:col-span-2">{meta.currency_note}</div>
                  {meta.notices.map((n) => (
                    <div key={n} className="font-semibold text-signal sm:col-span-2">
                      {n}
                    </div>
                  ))}
                </dl>
              )}
              <SimpleTable columns={columns} rows={built.data?.rows ?? []} empty="This report has no rows in your scope." rowKey={(_, i) => String(i)} minWidth="40rem" />
              {meta && meta.rows >= 200 && <p className="mt-2 text-xs text-ink-3">The on-screen preview shows up to 200 rows; exports include up to the tenant row limit.</p>}
            </div>
          )}
        </Panel>
      )}
      <p className="hidden text-xs print:block">Printed from Lumiant · {me.data?.tenant.display_name}</p>
    </div>
  );
}
