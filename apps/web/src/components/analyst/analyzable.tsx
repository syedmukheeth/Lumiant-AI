"use client";

import { clsx } from "clsx";
import { Sparkles } from "lucide-react";

import { analyze, sameSelection, useAnalyst } from "@/components/analyst/store";
import type { Selection } from "@/lib/agent";

/** Attributes that make any element pickable by the Lens (read by lens.tsx on click). */
export function analyzableProps(sel: Selection, selected = false) {
  return { "data-analyzable": "", "data-sel": JSON.stringify(sel), ...(selected ? { "data-selected": "" } : {}) };
}

export function readSelection(el: Element | null): Selection | null {
  const raw = el?.closest("[data-analyzable]")?.getAttribute("data-sel");
  if (!raw) return null;
  try {
    const sel = JSON.parse(raw) as Selection;
    return typeof sel?.kind === "string" && typeof sel?.id === "string" ? sel : null;
  } catch {
    return null;
  }
}

/** Small spark button: "Analyze this" (Shift-click adds it to the comparison). */
export function AnalyzeButton({ sel, className, label }: { sel: Selection; className?: string; label?: string }) {
  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        analyze(sel, { additive: e.shiftKey });
      }}
      aria-label={`Analyze ${sel.label ?? sel.id}`}
      title="Analyze with the Analyst (Shift-click to compare)"
      className={clsx(
        "inline-flex items-center gap-1 rounded-md p-1 text-ink-3 transition-colors hover:bg-accent-soft hover:text-accent focus-visible:text-accent",
        className,
      )}
    >
      <Sparkles size={13} aria-hidden />
      {label && <span className="text-xs font-medium">{label}</span>}
    </button>
  );
}

/**
 * Wrap anything the user may want to ask about. Right-click or the spark button opens the Analyst with it selected;
 * in Lens mode a click selects it. Keyboard: focus the element and press A.
 */
export function Analyzable({
  sel,
  children,
  className,
  button = true,
}: {
  sel: Selection;
  children: React.ReactNode;
  className?: string;
  button?: boolean;
}) {
  const { selections } = useAnalyst();
  const selected = selections.some((s) => sameSelection(s, sel));
  return (
    <div
      {...analyzableProps(sel, selected)}
      className={clsx("group/an relative", className)}
      onContextMenu={(e) => {
        if (e.shiftKey) return; // Shift + right-click keeps the browser menu
        e.preventDefault();
        analyze(sel);
      }}
      onKeyDown={(e) => {
        if (e.key.toLowerCase() === "a" && !e.metaKey && !e.ctrlKey && !e.altKey && e.target === e.currentTarget) {
          e.preventDefault();
          analyze(sel, { additive: e.shiftKey });
        }
      }}
    >
      {children}
      {button && (
        <AnalyzeButton
          sel={sel}
          className="absolute right-2 bottom-2 z-10 bg-surface-2/80 opacity-0 shadow-e1 backdrop-blur group-focus-within/an:opacity-100 group-hover/an:opacity-100"
        />
      )}
    </div>
  );
}
