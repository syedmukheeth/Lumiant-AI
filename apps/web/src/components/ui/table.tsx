import { clsx } from "clsx";
import { ArrowDown, ArrowUp } from "lucide-react";

/**
 * The one table recipe. The wrapper bleeds to the panel edge and scrolls sideways on narrow screens; rows are 13 px
 * with a hairline between them and a quiet hover. Text is one step quieter than full ink; right-aligned cells (numbers)
 * and the name in a CodeName cell are full ink. Colour a value with a span inside the cell, not on the cell.
 *
 * Columns sit 24 px apart; the first and last cell keep the panel's own inset so the table lines up with the panel
 * title. A right-aligned cell never wraps: a number must not be split from its unit or currency.
 *
 * A long table scrolls inside its panel (at most 70 % of the window) and its header row stays in view. The wrapper is
 * the scroll container on both axes, so `position: sticky` on the header cells works against it; a wrapper that only
 * scrolled sideways would trap the header and let it scroll away with the page.
 */
const CELL_X = "px-3 first:pl-5 last:pr-5 sm:first:pl-6 sm:last:pr-6";
export function DataTable({
  minWidth,
  busy,
  testId,
  children,
}: {
  minWidth?: string;
  busy?: boolean;
  testId?: string;
  children: React.ReactNode;
}) {
  return (
    // Focusable so keyboard users can scroll a wide or tall table (WCAG 2.1.1; axe scrollable-region-focusable).
    <div
      className="-mx-5 max-h-[min(70vh,44rem)] overflow-auto overscroll-contain focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-accent sm:-mx-6"
      tabIndex={0}
    >
      <table className="w-full text-dense text-ink-2" style={{ minWidth }} aria-busy={busy} data-testid={testId}>
        {children}
      </table>
    </div>
  );
}

export function HeadRow({ children }: { children: React.ReactNode }) {
  return <tr>{children}</tr>;
}

type Sort = { active: boolean; dir: "asc" | "desc"; onSort: () => void };

export function Th({ align, sort, className, children }: { align?: "right"; sort?: Sort; className?: string; children?: React.ReactNode }) {
  return (
    <th
      scope="col"
      aria-sort={sort?.active ? (sort.dir === "asc" ? "ascending" : "descending") : undefined}
      className={clsx("eyebrow sticky top-0 z-1 bg-surface-2 py-2 shadow-[inset_0_1px_0_var(--line),inset_0_-1px_0_var(--line)]", CELL_X, align === "right" ? "text-right" : "text-left", className)}
    >
      {sort ? (
        <button
          type="button"
          onClick={sort.onSort}
          className={clsx("inline-flex items-center gap-1 rounded-[0.25rem] uppercase transition-colors hover:text-ink", sort.active && "text-ink")}
        >
          {children}
          {sort.active && (sort.dir === "asc" ? <ArrowUp size={12} /> : <ArrowDown size={12} />)}
        </button>
      ) : (
        children
      )}
    </th>
  );
}

export function Tr({ className, ...rest }: React.ComponentProps<"tr">) {
  return <tr className={clsx("border-b border-line/70 transition-colors last:border-b-0 hover:bg-surface-2/60", className)} {...rest} />;
}

export function Td({ align, className, ...rest }: React.ComponentProps<"td"> & { align?: "right" }) {
  return <td className={clsx("py-2.5 align-top", CELL_X, align === "right" && "text-right whitespace-nowrap text-ink", className)} {...rest} />;
}

/** Two-line identifier cell: the code in mono, the name under it. */
export function CodeName({ code, name, max = "max-w-72" }: { code: React.ReactNode; name: React.ReactNode; max?: string }) {
  return (
    <>
      <span className="code block text-xs text-ink-3">{code}</span>
      <span className={clsx("block truncate text-ink", max)} title={typeof name === "string" ? name : undefined}>
        {name ?? "–"}
      </span>
    </>
  );
}
