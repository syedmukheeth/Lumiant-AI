"use client";

import { useQuery } from "@tanstack/react-query";
import { CalendarClock, Package, ShoppingCart, SlidersHorizontal, Warehouse, X } from "lucide-react";
import { useEffect, useRef } from "react";

import { ErrorState, Skeleton } from "@/components/data/widget";
import { SimpleTable, type SimpleColumn } from "@/components/data/simple-table";
import { Badge } from "@/components/ui/badge";
import { IconButton } from "@/components/ui/button";
import { api, type Row } from "@/lib/api";
import { formatMoney, formatNumber, humanize } from "@/lib/format";

type Section = { available: true; rows: Row[]; truncated: boolean } | { available: false; reason: string };
type Item360 = {
  item_id: string;
  master: Section;
  stock: Section;
  lots: Section;
  movements: Section;
  policies: Section;
  purchases: Section;
  cost_visible: boolean;
};

const qty = (r: Row, key = "quantity") => (
  <span className="figure">
    {formatNumber(r[key] as string, { maxFraction: 3 })} <span className="text-ink-3">{r.uom as string}</span>
  </span>
);

function Block({ icon: Icon, title, section, children }: { icon: typeof Package; title: string; section: Section; children: (rows: Row[]) => React.ReactNode }) {
  return (
    <section className="space-y-3">
      <h3 className="flex items-center gap-2 text-title font-semibold text-ink">
        <Icon size={15} className="text-ink-3" aria-hidden /> {title}
      </h3>
      {section.available ? children(section.rows) : <p className="text-sm text-ink-3">{section.reason}</p>}
      {section.available && section.truncated && <p className="text-xs text-ink-3">Showing the first rows only.</p>}
    </section>
  );
}

/** Material 360: one item's master data, stock by warehouse, lots, movements, reorder rules and purchases (V4). */
export function ItemSheet({ itemId, onClose }: { itemId: string; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const q = useQuery({ queryKey: ["item-360", itemId], queryFn: () => api.get<Item360>(`/api/items/${encodeURIComponent(itemId)}`) });

  useEffect(() => {
    const dialog = ref.current;
    if (dialog && !dialog.open) dialog.showModal();
    return () => dialog?.close();
  }, []);

  const master = q.data?.master.available ? q.data.master.rows[0] : undefined;
  const cost = q.data?.cost_visible ?? false;
  const stockCols: SimpleColumn[] = [
    { key: "wh", label: "Warehouse", render: (r) => <><span className="code text-xs text-ink-3">{r.warehouse_id as string}</span> {(r["warehouse.name"] as string) ?? ""}</> },
    { key: "q", label: "On hand", align: "right", render: (r) => qty(r) },
    ...(cost ? [{ key: "v", label: "Value", align: "right" as const, render: (r: Row) => <span className="figure">{formatMoney(r.value as string, (r.currency as string) ?? undefined)}</span> }] : []),
  ];

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(e) => e.target === ref.current && onClose()}
      aria-labelledby="item-sheet-title"
      className="m-0 ml-auto h-dvh max-h-dvh w-full max-w-3xl overflow-y-auto border-l border-line bg-canvas p-0 text-ink shadow-e3 backdrop:bg-(--scrim)"
      data-testid="item-sheet"
    >
      <div className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-line bg-canvas/95 px-6 py-5 backdrop-blur">
        <div className="min-w-0">
          <p className="eyebrow">Material 360</p>
          <h2 id="item-sheet-title" className="mt-1 font-display text-2xl leading-tight font-medium text-ink">
            {(master?.description as string) ?? itemId}
          </h2>
          <p className="code mt-1 text-xs text-ink-3">{(master?.item_code as string) ?? itemId}</p>
          {master && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {master.item_group ? <Badge>{humanize(master.item_group as string)}</Badge> : null}
              {master.inventory_stage ? <Badge>{humanize(master.inventory_stage as string)}</Badge> : null}
              {master.abc_class ? <Badge tone="accent">ABC {master.abc_class as string}</Badge> : null}
              {master.critical ? <Badge tone="signal">Critical spare</Badge> : null}
              {master.lifecycle_status ? <Badge>{humanize(master.lifecycle_status as string)}</Badge> : null}
            </div>
          )}
        </div>
        <IconButton aria-label="Close item details" onClick={onClose}>
          <X size={16} aria-hidden />
        </IconButton>
      </div>

      <div className="space-y-8 px-6 py-6">
        {q.isPending ? (
          <Skeleton className="h-96 w-full" />
        ) : q.error ? (
          <ErrorState error={q.error} />
        ) : (
          <>
            <Block icon={Warehouse} title="Stock by warehouse" section={q.data.stock}>
              {(rows) => <SimpleTable columns={stockCols} rows={rows} empty="No stock in your warehouses." rowKey={(r) => String(r.warehouse_id)} minWidth="24rem" />}
            </Block>
            <Block icon={CalendarClock} title="Lots on hand" section={q.data.lots}>
              {(rows) => (
                <SimpleTable
                  columns={[
                    { key: "lot", label: "Lot", render: (r) => <span className="code text-xs">{r.lot_id as string}</span> },
                    { key: "wh", label: "Warehouse", render: (r) => <span className="code text-xs">{r.warehouse_id as string}</span> },
                    { key: "exp", label: "Expires", render: (r) => <span className="figure">{(r["lot.expiry_date"] as string) ?? "–"}</span> },
                    { key: "q", label: "Quantity", align: "right", render: (r) => qty(r) },
                  ]}
                  rows={rows}
                  empty="No lots on hand."
                  rowKey={(r, i) => `${r.lot_id}-${r.warehouse_id}-${i}`}
                  minWidth="28rem"
                />
              )}
            </Block>
            <Block icon={Package} title="Latest movements" section={q.data.movements}>
              {(rows) => (
                <SimpleTable
                  columns={[
                    { key: "d", label: "Posted", render: (r) => <span className="figure">{r.posting_date as string}</span> },
                    { key: "t", label: "Type", render: (r) => humanize(r.txn_type as string) },
                    { key: "wh", label: "Warehouse", render: (r) => <span className="code text-xs">{r.warehouse_id as string}</span> },
                    { key: "q", label: "Quantity", align: "right", render: (r) => qty(r) },
                  ]}
                  rows={rows}
                  empty="No movements recorded."
                  rowKey={(r, i) => `${r.txn_id}-${i}`}
                  minWidth="28rem"
                />
              )}
            </Block>
            <Block icon={SlidersHorizontal} title="Reorder rules" section={q.data.policies}>
              {(rows) => (
                <SimpleTable
                  columns={[
                    { key: "wh", label: "Warehouse", render: (r) => <span className="code text-xs">{r.warehouse_id as string}</span> },
                    { key: "rl", label: "Reorder at", align: "right", render: (r) => <span className="figure">{formatNumber(r.reorder_level as string)}</span> },
                    { key: "min", label: "Minimum", align: "right", render: (r) => <span className="figure">{formatNumber(r.min_stock as string)}</span> },
                    { key: "max", label: "Maximum", align: "right", render: (r) => <span className="figure">{formatNumber(r.max_stock as string)}</span> },
                  ]}
                  rows={rows}
                  empty="No reorder rule for this item."
                  rowKey={(r) => String(r.warehouse_id)}
                  minWidth="26rem"
                />
              )}
            </Block>
            <Block icon={ShoppingCart} title="Purchase orders" section={q.data.purchases}>
              {(rows) => (
                <SimpleTable
                  columns={[
                    { key: "po", label: "Order", render: (r) => <span className="code text-xs">{r.po_id as string}</span> },
                    { key: "d", label: "Ordered", render: (r) => <span className="figure">{(r.order_date as string) ?? "–"}</span> },
                    { key: "s", label: "Status", render: (r) => humanize(r.status as string) },
                    { key: "sup", label: "Supplier", render: (r) => <span className="code text-xs">{(r.supplier_id as string) ?? "–"}</span> },
                    { key: "q", label: "Quantity", align: "right", render: (r) => qty(r) },
                  ]}
                  rows={rows}
                  empty="No purchase orders for this item."
                  rowKey={(r, i) => `${r.po_id}-${i}`}
                  minWidth="32rem"
                />
              )}
            </Block>
          </>
        )}
      </div>
    </dialog>
  );
}
