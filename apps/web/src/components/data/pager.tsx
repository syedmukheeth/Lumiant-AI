"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";

import { formatCount } from "@/lib/format";

export function Pager({
  page,
  onChange,
}: {
  page: { offset: number; limit: number; total: number };
  onChange: (offset: number) => void;
}) {
  const { offset, limit, total } = page;
  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + limit, total);
  const btn =
    "inline-flex items-center rounded-sm border border-line px-2 py-1 text-xs text-ink-2 hover:bg-surface-2 disabled:opacity-40 disabled:hover:bg-transparent";
  return (
    <nav aria-label="Pagination" className="mt-3 flex items-center justify-between gap-3 text-xs text-ink-3">
      <span className="figure" data-testid="pager-range">
        {formatCount(from)}–{formatCount(to)} of {formatCount(total)}
      </span>
      <span className="flex gap-1.5">
        <button type="button" className={btn} disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - limit))}>
          <ChevronLeft size={14} aria-hidden /> Prev
        </button>
        <button type="button" className={btn} disabled={to >= total} onClick={() => onChange(offset + limit)}>
          Next <ChevronRight size={14} aria-hidden />
        </button>
      </span>
    </nav>
  );
}
