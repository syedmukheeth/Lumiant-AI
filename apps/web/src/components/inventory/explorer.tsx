"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { AnalyzeButton, analyzableProps } from "@/components/analyst/analyzable";
import { analyze } from "@/components/analyst/store";
import { Pager } from "@/components/data/pager";
import { ErrorState, Panel, Skeleton } from "@/components/data/widget";
import { Field, SearchInput, Select } from "@/components/ui/field";
import { PageHeader } from "@/components/ui/page-header";
import { CodeName, DataTable, HeadRow, Td, Th, Tr } from "@/components/ui/table";
import type { Selection } from "@/lib/agent";
import type { Row } from "@/lib/api";
import { formatMoney, formatNumber, humanize } from "@/lib/format";
import { type BalanceQuery, useBalances, useInventoryFilters, usePageMe } from "@/lib/hooks";
import { enterDelay } from "@/lib/motion";

const LIMIT = 50;

type Col = {
  key: string;
  label: string;
  sort?: string;
  align?: "right";
  render: (r: Row) => React.ReactNode;
  cost?: boolean;
  /** Result field the column needs; the column is hidden when the tenant's source does not provide it. */
  field?: string;
};

const COLUMNS: Col[] = [
  {
    key: "item",
    label: "Item",
    sort: "item_code",
    render: (r) => <CodeName code={r["item.item_code"] ?? r.item_id} name={r["item.description"] as string | null} max="max-w-80" />,
  },
  { key: "group", label: "Group", sort: "item_group", render: (r) => humanize(r["item.item_group"] as string) },
  { key: "abc", label: "ABC", sort: "abc_class", field: "item.abc_class", render: (r) => r["item.abc_class"] ?? "–" },
  {
    key: "warehouse",
    label: "Warehouse",
    sort: "warehouse",
    render: (r) => (
      <>
        <span className="code block text-xs text-ink-3">
          {r.warehouse_id} · {r.location_id}
        </span>
        <span className="block max-w-56 truncate">{r["warehouse.name"] ?? "–"}</span>
      </>
    ),
  },
  { key: "lot", label: "Lot", field: "lot_id", render: (r) => <span className="code text-xs">{r.lot_id ?? "–"}</span> },
  {
    key: "status",
    label: "Stock status",
    field: "stock_status",
    render: (r) => <span className="text-xs">{humanize(r.stock_status as string)}</span>,
  },
  {
    key: "qty",
    label: "Quantity",
    sort: "quantity",
    align: "right",
    render: (r) => (
      <span className="figure">
        {formatNumber(r.quantity as string, { maxFraction: 3 })} <span className="text-ink-3">{r.uom}</span>
      </span>
    ),
  },
  {
    key: "price",
    label: "Valuation price",
    align: "right",
    cost: true,
    render: (r) =>
      r.valuation_price === null ? (
        <span className="text-xs text-signal">missing in source</span>
      ) : (
        <span className="figure">{formatMoney(r.valuation_price as string, r.currency as string)}</span>
      ),
  },
  {
    key: "value",
    label: "Value",
    sort: "value",
    align: "right",
    cost: true,
    render: (r) => <span className="figure">{formatMoney(r.stock_value as string, r.currency as string)}</span>,
  },
];

function FilterSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (v: string) => void;
}) {
  return (
    <Field label={label}>
      <Select value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">All</option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </Select>
    </Field>
  );
}

export function InventoryExplorer() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const me = usePageMe();
  const filters = useInventoryFilters();
  const canSeeCost = me?.permissions.includes("cost:read") ?? false;

  const query: BalanceQuery = {
    warehouse: params.get("warehouse") ?? undefined,
    item_group: params.get("item_group") ?? undefined,
    abc: params.get("abc") ?? undefined,
    stage: params.get("stage") ?? undefined,
    status: params.get("status") ?? undefined,
    q: params.get("q") ?? undefined,
    sort: params.get("sort") ?? "item_code",
    dir: params.get("dir") === "desc" ? "desc" : "asc",
    offset: Number(params.get("offset") ?? 0) || 0,
    limit: LIMIT,
  };
  const balances = useBalances(query);

  // The URL most recently requested from the router, until the router has committed it. router.replace is a
  // transition: window.location can lag behind it, so a debounced search firing meanwhile must build on this one.
  const pendingQs = useRef<string | null>(null);
  useEffect(() => {
    if (pendingQs.current !== null && pendingQs.current === params.toString()) pendingQs.current = null;
  }, [params]);

  const update = (patch: Partial<Record<keyof BalanceQuery, string | number | undefined>>) => {
    // Never the render-time snapshot: the debounced search can fire after another filter changed and must not
    // overwrite it (ISSUES #12).
    const next = new URLSearchParams(pendingQs.current ?? window.location.search);
    for (const [k, v] of Object.entries(patch)) {
      if (v === undefined || v === "" || (k === "offset" && v === 0)) next.delete(k);
      else next.set(k, String(v));
    }
    if (!("offset" in patch)) next.delete("offset");
    pendingQs.current = next.toString();
    router.replace(`${pathname}?${next.toString()}`, { scroll: false });
  };

  const [term, setTerm] = useState(query.q ?? "");
  // When the URL's search changes from outside this box (command palette, back button), show it in the box. A change
  // this box made itself is skipped, so typing during the round trip is never overwritten.
  const [pushedQ, setPushedQ] = useState(query.q);
  const [seenQ, setSeenQ] = useState(query.q);
  if (query.q !== seenQ) {
    setSeenQ(query.q);
    if (query.q !== pushedQ) {
      setPushedQ(query.q);
      setTerm(query.q ?? "");
    }
  }
  useEffect(() => {
    const t = setTimeout(() => {
      if ((query.q ?? "") !== term.trim()) {
        setPushedQ(term.trim() || undefined);
        update({ q: term.trim() || undefined });
      }
    }, 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [term]);

  const returned = balances.data ? new Set(balances.data.columns.map((c) => c.name)) : null;
  const columns = COLUMNS.filter((c) => (!c.cost || canSeeCost) && (!c.field || !returned || returned.has(c.field)));
  const sortBy = (col: Col) => {
    if (!col.sort) return;
    const dir = query.sort === col.sort && query.dir === "asc" ? "desc" : "asc";
    update({ sort: col.sort, dir });
  };

  const f = filters.data;
  return (
    <div className="mx-auto max-w-[96rem] space-y-8">
      <PageHeader
        title="Stock on hand"
        description={
          <>
            Every stock line in your scope, item × warehouse × location × lot.
            {!canSeeCost && " Cost columns are hidden for your role."}
          </>
        }
      />

      <div className="rise panel grid grid-cols-2 gap-x-3 gap-y-4 p-4 md:grid-cols-6 sm:p-5" style={enterDelay(1)}>
        <Field label="Search" className="col-span-2">
          <SearchInput value={term} onChange={(e) => setTerm(e.target.value)} maxLength={100} placeholder="Item code or description" aria-label="Search items" />
        </Field>
        <FilterSelect
          label="Warehouse"
          value={query.warehouse ?? ""}
          options={(f?.warehouses ?? []).map((w) => ({ value: w.id, label: w.name ? `${w.id} · ${w.name}` : w.id }))}
          onChange={(v) => update({ warehouse: v })}
        />
        <FilterSelect
          label="Item group"
          value={query.item_group ?? ""}
          options={(f?.item_groups ?? []).map((g) => ({ value: g, label: humanize(g) }))}
          onChange={(v) => update({ item_group: v })}
        />
        <FilterSelect
          label="ABC (assigned)"
          value={query.abc ?? ""}
          options={(f?.abc_classes ?? []).map((g) => ({ value: g, label: g }))}
          onChange={(v) => update({ abc: v })}
        />
        <FilterSelect
          label="Stage"
          value={query.stage ?? ""}
          options={(f?.stages ?? []).map((g) => ({ value: g, label: humanize(g) }))}
          onChange={(v) => update({ stage: v })}
        />
        {(f?.stock_statuses?.length ?? 0) > 0 && (
          <FilterSelect
            label="Stock status"
            value={query.status ?? ""}
            options={(f?.stock_statuses ?? []).map((g) => ({ value: g, label: humanize(g) }))}
            onChange={(v) => update({ status: v })}
          />
        )}
      </div>

      <Panel
        title="Stock lines"
        subtitle={balances.data?.page ? `${formatNumber(balances.data.page.total)} lines match` : undefined}
        provenance={balances.data?.provenance}
        warnings={balances.data?.warnings.filter((w) => w.code !== "auto_grouped" && w.code !== "truncated")}
        style={enterDelay(2)}
      >
        {balances.isPending ? (
          <Skeleton className="h-96 w-full" />
        ) : balances.error ? (
          <ErrorState error={balances.error} />
        ) : (
          <>
            <DataTable minWidth="60rem" busy={balances.isFetching} testId="balances-table">
              <thead>
                <HeadRow>
                  {columns.map((c) => (
                    <Th
                      key={c.key}
                      align={c.align}
                      sort={c.sort ? { active: query.sort === c.sort, dir: query.dir === "asc" ? "asc" : "desc", onSort: () => sortBy(c) } : undefined}
                    >
                      {c.label}
                    </Th>
                  ))}
                </HeadRow>
              </thead>
              <tbody>
                {balances.data?.data.length === 0 && (
                  <tr>
                    <td colSpan={columns.length} className="px-5 py-10 text-center text-sm text-ink-3">
                      No stock lines match these filters.
                    </td>
                  </tr>
                )}
                {balances.data?.data.map((r, i) => {
                  const sel: Selection = { kind: "item", id: String(r.item_id), label: [r.item_code, r.description].filter(Boolean).join(" · ") };
                  return (
                    <Tr
                      key={`${r.item_id}-${r.warehouse_id}-${r.location_id}-${r.lot_id}-${i}`}
                      className="group/row"
                      {...analyzableProps(sel)}
                      onContextMenu={(e) => {
                        if (e.shiftKey) return;
                        e.preventDefault();
                        analyze(sel);
                      }}
                    >
                      {columns.map((c, ci) => (
                        <Td key={c.key} align={c.align}>
                          {ci === 0 ? (
                            <div className="flex items-start gap-1">
                              <div className="min-w-0 flex-1">{c.render(r)}</div>
                              <AnalyzeButton sel={sel} className="-mt-0.5 opacity-0 group-hover/row:opacity-100 focus-visible:opacity-100" />
                            </div>
                          ) : (
                            c.render(r)
                          )}
                        </Td>
                      ))}
                    </Tr>
                  );
                })}
              </tbody>
            </DataTable>
            {balances.data?.page && <Pager page={balances.data.page} onChange={(offset) => update({ offset })} />}
          </>
        )}
      </Panel>
    </div>
  );
}
