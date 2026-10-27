"use client";

import { useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { ErrorState, Panel, Skeleton } from "@/components/data/widget";
import { formatMoney, humanize, toChartNumber } from "@/lib/format";
import { useMetric } from "@/lib/hooks";

type Props = {
  metricId: string;
  title: string;
  /** Row field holding the category label. */
  labelField: string;
  /** Optional field shown before the label (e.g. warehouse id). */
  codeField?: string;
  humanizeLabels?: boolean;
  delay?: number;
};

type Datum = { label: string; value: number; exact: string };

/**
 * Horizontal bars of a value metric. Amounts in different currencies are shown one currency at a time;
 * bar lengths use numbers for geometry only — every printed amount is the exact decimal string.
 */
export function ValueBars({ metricId, title, labelField, codeField, humanizeLabels, delay = 0 }: Props) {
  const { data, error, isPending } = useMetric(metricId);
  const currencies = useMemo(
    () => Array.from(new Set((data?.data ?? []).map((r) => String(r.currency ?? "")))).filter(Boolean).sort(),
    [data],
  );
  const [picked, setPicked] = useState<string | null>(null);
  const currency = picked && currencies.includes(picked) ? picked : currencies[0];

  const rows: Datum[] = useMemo(
    () =>
      (data?.data ?? [])
        .filter((r) => r.currency === currency)
        .map((r) => {
          const raw = r[labelField];
          const base = raw === null || raw === undefined || raw === "" ? "Not set" : String(raw);
          const label = humanizeLabels ? humanize(base) : base;
          return {
            label: codeField && r[codeField] ? `${r[codeField]} · ${label}` : label,
            value: toChartNumber(r.value as string),
            exact: String(r.value ?? ""),
          };
        }),
    [data, currency, labelField, codeField, humanizeLabels],
  );

  const switcher =
    currencies.length > 1 ? (
      <div role="tablist" aria-label="Currency" className="flex rounded-sm border border-line p-0.5">
        {currencies.map((c) => (
          <button
            key={c}
            role="tab"
            aria-selected={c === currency}
            onClick={() => setPicked(c)}
            className={`figure rounded-[2px] px-1.5 py-0.5 text-[0.6875rem] ${c === currency ? "bg-ink text-surface" : "text-ink-3 hover:text-ink"}`}
          >
            {c}
          </button>
        ))}
      </div>
    ) : null;

  return (
    <Panel
      title={title}
      subtitle={
        currency
          ? [
              `Amounts in ${currency}`,
              currencies.length > 1 ? "currencies are never combined" : null,
              data?.provenance.excluded_lines ? `${data.provenance.excluded_lines} lines without valuation price excluded` : null,
            ]
              .filter(Boolean)
              .join(" · ")
          : undefined
      }
      provenance={data?.provenance}
      warnings={data?.warnings.filter((w) => w.code !== "auto_grouped" && w.code !== "missing_valuation_price")}
      actions={switcher}
      style={{ animationDelay: `${delay}ms` }}
    >
      {isPending ? (
        <Skeleton className="h-48 w-full" />
      ) : error ? (
        <ErrorState error={error} />
      ) : rows.length === 0 ? (
        <p className="text-sm text-ink-3">No stock in your scope.</p>
      ) : (
        <div style={{ height: Math.max(140, rows.length * 34 + 24) }} className="figure text-[0.6875rem]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={rows} layout="vertical" margin={{ top: 0, right: 12, bottom: 0, left: 0 }} barCategoryGap={6}>
              <CartesianGrid horizontal={false} stroke="var(--line)" strokeDasharray="2 3" />
              <XAxis
                type="number"
                tickFormatter={(v: number) => formatMoney(v, currency, { compact: true })}
                stroke="var(--ink-3)"
                tickLine={false}
                axisLine={false}
                tickCount={4}
                minTickGap={28}
              />
              <YAxis
                type="category"
                dataKey="label"
                width={196}
                tick={{ fill: "var(--ink-2)" }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v: string) => (v.length > 30 ? `${v.slice(0, 29)}…` : v)}
              />
              <Tooltip
                cursor={{ fill: "var(--surface-2)" }}
                contentStyle={{
                  background: "var(--surface)",
                  border: "1px solid var(--line-strong)",
                  borderRadius: 4,
                  fontSize: 12,
                }}
                formatter={(_v, _n, item) => [formatMoney((item.payload as Datum).exact, currency), "Value"]}
                labelStyle={{ color: "var(--ink)" }}
              />
              <Bar dataKey="value" fill="var(--accent)" radius={[0, 2, 2, 0]} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </Panel>
  );
}
