"use client";

import { clsx } from "clsx";
import { ArrowDown, ArrowUp, Search } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Pager } from "@/components/data/pager";
import { ErrorState, Panel, Skeleton } from "@/components/data/widget";
import type { Row } from "@/lib/api";
import { formatMoney, formatNumber, humanize } from "@/lib/format";
import { type BalanceQuery, useBalances, useInventoryFilters, usePageMe } from "@/lib/hooks";

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
    render: (r) => (
      <>
        <span className="figure block text-xs text-ink-3">{r["item.item_code"] ?? r.item_id}</span>
        <span className="block max-w-80 truncate text-ink" title={String(r["item.description"] ?? "")}>
          {r["item.description"] ?? "—"}
        </span>
      </>
    ),
  },
  { key: "group", label: "Group", sort: "item_group", render: (r) => humanize(r["item.item_group"] as string) },
  { key: "abc", label: "ABC", sort: "abc_class", field: "item.abc_class", render: (r) => <span className="figure">{r["item.abc_class"] ?? "—"}</span> },
  {
    key: "warehouse",
    label: "Warehouse",
    sort: "warehouse",
    render: (r) => (
      <>
        <span className="figure block text-xs text-ink-3">
          {r.warehouse_id} · {r.location_id}
        </span>
        <span className="block max-w-56 truncate text-ink-2">{r["warehouse.name"] ?? "—"}</span>
      </>
    ),
  },
  { key: "lot", label: "Lot", field: "lot_id", render: (r) => <span className="figure text-xs">{r.lot_id ?? "—"}</span> },
  {
    key: "status",
    label: "Stock status",
    field: "stock_status",
    render: (r) => <span className="text-xs text-ink-2">{humanize(r.stock_status as string)}</span>,
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

function Select({
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
    <label className="flex min-w-0 flex-col gap-1">
      <span className="eyebrow">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-9 rounded-sm border border-line bg-surface px-2 text-sm text-ink"
      >
        <option value="">All</option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
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

  const update = (patch: Partial<Record<keyof BalanceQuery, string | number | undefined>>) => {
    // Read the live URL, not the render-time snapshot: the debounced search can fire after another
    // filter changed, and must not overwrite it.
    const next = new URLSearchParams(window.location.search);
    for (const [k, v] of Object.entries(patch)) {
      if (v === undefined || v === "" || (k === "offset" && v === 0)) next.delete(k);
      else next.set(k, String(v));
    }
    if (!("offset" in patch)) next.delete("offset");
    router.replace(`${pathname}?${next.toString()}`, { scroll: false });
  };

  const [term, setTerm] = useState(query.q ?? "");
  useEffect(() => {
    const t = setTimeout(() => {
      if ((query.q ?? "") !== term.trim()) update({ q: term.trim() || undefined });
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
    <div className="mx-auto max-w-[96rem] space-y-5">
      <div className="rise">
        <p className="eyebrow">Inventory</p>
        <h1 className="mt-1 text-2xl font-bold tracking-tight text-ink sm:text-[1.75rem]">Stock on hand</h1>
        <p className="mt-1 text-sm text-ink-3">
          Every stock line in your scope, item × warehouse × location × lot.
          {!canSeeCost && " Cost columns are hidden for your role."}
        </p>
      </div>

      <div className="rise grid grid-cols-2 gap-3 rounded-md border border-line bg-surface p-4 md:grid-cols-6" style={{ animationDelay: "60ms" }}>
        <label className="col-span-2 flex flex-col gap-1">
          <span className="eyebrow">Search</span>
          <span className="flex h-9 items-center gap-2 rounded-sm border border-line bg-surface px-2">
            <Search size={14} className="text-ink-3" aria-hidden />
            <input
              value={term}
              onChange={(e) => setTerm(e.target.value)}
              maxLength={100}
              placeholder="Item code or description"
              className="h-full w-full bg-transparent text-sm text-ink outline-none placeholder:text-ink-3"
              aria-label="Search items"
            />
          </span>
        </label>
        <Select
          label="Warehouse"
          value={query.warehouse ?? ""}
          options={(f?.warehouses ?? []).map((w) => ({ value: w.id, label: w.name ? `${w.id} · ${w.name}` : w.id }))}
          onChange={(v) => update({ warehouse: v })}
        />
        <Select
          label="Item group"
          value={query.item_group ?? ""}
          options={(f?.item_groups ?? []).map((g) => ({ value: g, label: humanize(g) }))}
          onChange={(v) => update({ item_group: v })}
        />
        <Select
          label="ABC (assigned)"
          value={query.abc ?? ""}
          options={(f?.abc_classes ?? []).map((g) => ({ value: g, label: g }))}
          onChange={(v) => update({ abc: v })}
        />
        <Select
          label="Stage"
          value={query.stage ?? ""}
          options={(f?.stages ?? []).map((g) => ({ value: g, label: humanize(g) }))}
          onChange={(v) => update({ stage: v })}
        />
        {(f?.stock_statuses?.length ?? 0) > 0 && (
          <Select
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
        style={{ animationDelay: "120ms" }}
      >
        {balances.isPending ? (
          <Skeleton className="h-96 w-full" />
        ) : balances.error ? (
          <ErrorState error={balances.error} />
        ) : (
          <>
            <div className="-mx-4 overflow-x-auto sm:-mx-5">
              <table className="w-full min-w-[60rem] text-sm" aria-busy={balances.isFetching} data-testid="balances-table">
                <thead>
                  <tr className="border-y border-line">
                    {columns.map((c) => {
                      const active = c.sort && query.sort === c.sort;
                      return (
                        <th
                          key={c.key}
                          scope="col"
                          aria-sort={active ? (query.dir === "asc" ? "ascending" : "descending") : undefined}
                          className={clsx("eyebrow px-4 py-2 font-semibold sm:px-5", c.align === "right" ? "text-right" : "text-left")}
                        >
                          {c.sort ? (
                            <button
                              type="button"
                              onClick={() => sortBy(c)}
                              className={clsx("inline-flex items-center gap-1 uppercase hover:text-ink", active && "text-ink")}
                            >
                              {c.label}
                              {active && (query.dir === "asc" ? <ArrowUp size={12} /> : <ArrowDown size={12} />)}
                            </button>
                          ) : (
                            c.label
                          )}
                        </th>
                      );
                    })}
                  </tr>
                </thead>
                <tbody>
                  {balances.data?.data.length === 0 && (
                    <tr>
                      <td colSpan={columns.length} className="px-5 py-10 text-center text-sm text-ink-3">
                        No stock lines match these filters.
                      </td>
                    </tr>
                  )}
                  {balances.data?.data.map((r, i) => (
                    <tr key={`${r.item_id}-${r.warehouse_id}-${r.location_id}-${r.lot_id}-${i}`} className="border-b border-line/70 hover:bg-surface-2/60">
                      {columns.map((c) => (
                        <td key={c.key} className={clsx("px-4 py-2 align-top sm:px-5", c.align === "right" && "text-right")}>
                          {c.render(r)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {balances.data?.page && <Pager page={balances.data.page} onChange={(offset) => update({ offset })} />}
          </>
        )}
      </Panel>
    </div>
  );
}
