"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { formatCount } from "@/lib/format";

/** Rows rendered per step in long review lists: enough to scan, few enough that the page stays light. */
export const SHOW_STEP = 100;

/** The first `step` items, and more on request. Long lists (hundreds of pairs or order lines) never render at once. */
export function useShowMore<T>(items: readonly T[], step = SHOW_STEP) {
  const [count, setCount] = useState(step);
  return { visible: items.slice(0, count), rest: Math.max(0, items.length - count), more: () => setCount((c) => c + step), step };
}

export function ShowMore({ rest, step, onMore }: { rest: number; step: number; onMore: () => void }) {
  if (rest <= 0) return null;
  return (
    <div className="mt-3 flex justify-center">
      <Button variant="ghost" size="sm" onClick={onMore} data-testid="show-more">
        Show {formatCount(String(Math.min(rest, step)))} more · {formatCount(String(rest))} not shown
      </Button>
    </div>
  );
}
