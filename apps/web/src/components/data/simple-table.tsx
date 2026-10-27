"use client";

import { clsx } from "clsx";

import type { Row } from "@/lib/api";

export type SimpleColumn = {
  key: string;
  label: string;
  align?: "right";
  render: (row: Row) => React.ReactNode;
};

export function SimpleTable({
  columns,
  rows,
  empty,
  busy,
  rowKey,
  minWidth = "44rem",
}: {
  columns: SimpleColumn[];
  rows: Row[];
  empty: string;
  busy?: boolean;
  rowKey: (row: Row, index: number) => string;
  minWidth?: string;
}) {
  if (rows.length === 0) return <p className="text-sm text-ink-3">{empty}</p>;
  return (
    <div className="-mx-4 overflow-x-auto sm:-mx-5">
      <table className="w-full text-sm" style={{ minWidth }} aria-busy={busy}>
        <thead>
          <tr className="border-y border-line">
            {columns.map((c) => (
              <th
                key={c.key}
                scope="col"
                className={clsx("eyebrow px-4 py-2 font-semibold sm:px-5", c.align === "right" ? "text-right" : "text-left")}
              >
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={rowKey(r, i)} className="border-b border-line/70 hover:bg-surface-2/60">
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
  );
}

export function ItemCell({ row }: { row: Row }) {
  const code = (row["item.item_code"] ?? row.item_code ?? row.item_id) as string;
  const description = (row["item.description"] ?? row.description) as string | null;
  return (
    <>
      <span className="figure block text-xs text-ink-3">{code}</span>
      <span className="block max-w-72 truncate text-ink" title={description ?? ""}>
        {description ?? "—"}
      </span>
    </>
  );
}
