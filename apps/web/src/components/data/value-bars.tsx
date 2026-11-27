"use client";

import { useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { analyzableProps } from "@/components/analyst/analyzable";
import { analyze } from "@/components/analyst/store";
import { ErrorState, Panel, Skeleton } from "@/components/data/widget";
import { Segmented } from "@/components/ui/tabs";
import type { SelectionKind } from "@/lib/agent";
import { formatMoney, humanize, toChartNumber } from "@/lib/format";
import { useMetric } from "@/lib/hooks";
import { enterDelay } from "@/lib/motion";
import { Treemap } from "@/components/viz/treemap";

type Props = {
  metricId: string;
  title: string;
  /** Row field holding the category label. */
  labelField: string;
  /** Optional field shown before the label (e.g. warehouse id). */
  codeField?: string;
  humanizeLabels?: boolean;
  /** Position in the grid (entrance stagger). */
  index?: number;
  /** What a bar stands for; clicking it (or picking it in Lens mode) points the Analyst at that category. */
  selectKind?: SelectionKind;
  /** `treemap` shows share of the whole (many categories); `bars` (default) ranks them. */
  variant?: "bars" | "treemap";
};

type Datum = { label: string; value: number; exact: string; id: string };

/** One-line category label in the UI sans (Recharts would wrap it by its own text measurement). */
function CategoryTick({ x, y, payload }: { x?: number | string; y?: number | string; payload?: { value?: unknown } }) {
  const v = String(payload?.value ?? "");
  return (
    <text x={x} y={y} dy="0.35em" textAnchor="end" fill="var(--ink-2)" fontSize={11} fontFamily="var(--font-sans)">
      <title>{v}</title>
      {v.length > 30 ? `${v.slice(0, 29)}…` : v}
    </text>
  );
}

/**
 * Horizontal bars of a value metric. Amounts in different currencies are shown one currency at a time;
 * bar lengths use numbers for geometry only — every printed amount is the exact decimal string.
 */
export function ValueBars({ metricId, title, labelField, codeField, humanizeLabels, index = 0, selectKind, variant = "bars" }: Props) {
  const [hover, setHover] = useState<number | null>(null);
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
            id: String((codeField ? r[codeField] : raw) ?? ""),
          };
        }),
    [data, currency, labelField, codeField, humanizeLabels],
  );

  const switcher = currencies.length > 1 && currency ? <Segmented label="Currency" options={currencies} value={currency} onChange={setPicked} /> : null;

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
      style={enterDelay(4 + index)}
      analyze={{ kind: "metric", id: metricId, label: title }}
    >
      {isPending ? (
        <Skeleton className="h-48 w-full" />
      ) : error ? (
        <ErrorState error={error} />
      ) : rows.length === 0 ? (
        <p className="text-sm text-ink-3">No stock in your scope.</p>
      ) : variant === "treemap" ? (
        <Treemap
          label={`${title}, ${currency ?? ""}: larger blocks hold more value`}
          height={Math.min(340, Math.max(220, rows.length * 28))}
          items={rows.map((r) => ({ id: r.id, label: r.label, value: r.value, exact: formatMoney(r.exact, currency) }))}
          onSelect={selectKind ? (it) => it.id && analyze({ kind: selectKind, id: it.id, label: it.label }) : undefined}
        />
      ) : (
        <div
          style={{ height: Math.max(140, rows.length * 34 + 24) }}
          className="figure text-caption"
          {...(selectKind && hover !== null && rows[hover]?.id
            ? analyzableProps({ kind: selectKind, id: rows[hover].id, label: rows[hover].label })
            : {})}
        >
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={rows}
              layout="vertical"
              margin={{ top: 0, right: 12, bottom: 0, left: 0 }}
              barCategoryGap={6}
              onMouseMove={(s) => setHover(s?.activeTooltipIndex != null ? Number(s.activeTooltipIndex) : null)}
              onMouseLeave={() => setHover(null)}
            >
              <CartesianGrid horizontal={false} stroke="var(--viz-grid)" />
              <XAxis
                type="number"
                tickFormatter={(v: number) => formatMoney(v, currency, { compact: true })}
                stroke="var(--ink-3)"
                tick={{ fill: "var(--ink-3)" }}
                tickLine={false}
                axisLine={false}
                tickCount={4}
                minTickGap={28}
              />
              <YAxis
                type="category"
                dataKey="label"
                width={196}
                tick={CategoryTick}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip
                cursor={{ fill: "var(--viz-cursor)" }}
                contentStyle={{
                  background: "var(--surface-3)",
                  border: "1px solid var(--line-strong)",
                  borderRadius: "var(--r-control)",
                  boxShadow: "var(--elev-2)",
                  fontSize: 12,
                }}
                itemStyle={{ color: "var(--ink-2)" }}
                formatter={(_v, _n, item) => [formatMoney((item.payload as Datum).exact, currency), "Value"]}
                labelStyle={{ color: "var(--ink)" }}
              />
              {/* Single series: categorical slot 1, 4 px rounded data end. Recharts animation stays off: it runs on frames, which a hidden tab never produces (ISSUES #10). */}
              <Bar
                dataKey="value"
                fill="var(--viz-1)"
                radius={[0, 4, 4, 0]}
                isAnimationActive={false}
                cursor={selectKind ? "pointer" : undefined}
                onClick={(d) => {
                  const datum = (d as { payload?: Datum }).payload;
                  if (selectKind && datum?.id) analyze({ kind: selectKind, id: datum.id, label: datum.label });
                }}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </Panel>
  );
}
