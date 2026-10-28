"use client";

import { Crosshair, X } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useEffect } from "react";

import { readSelection } from "@/components/analyst/analyzable";
import { analyze, setLens, useAnalyst } from "@/components/analyst/store";
import { DUR, EASE, REDUCED_DUR } from "@/lib/motion";

/**
 * Lens mode: the page becomes pickable. A click on anything analyzable selects it for the Analyst (Shift adds it to a
 * comparison) instead of doing what the click normally does; everything else keeps working. Esc leaves the lens.
 */
export function Lens() {
  const { lens, selections } = useAnalyst();
  const reduce = useReducedMotion();

  useEffect(() => {
    if (!lens) return;
    const onClick = (e: MouseEvent) => {
      const target = e.target instanceof Element ? e.target : null;
      if (!target || target.closest("[data-lens-ui]")) return;
      const sel = readSelection(target);
      if (!sel) return;
      e.preventDefault();
      e.stopPropagation();
      analyze(sel, { additive: e.shiftKey });
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setLens(false);
    };
    document.addEventListener("click", onClick, true);
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("click", onClick, true);
      window.removeEventListener("keydown", onKey);
    };
  }, [lens]);

  return (
    <AnimatePresence>
      {lens && (
        <motion.div
          data-lens-ui
          role="status"
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: reduce ? REDUCED_DUR : DUR.base, ease: EASE.out }}
          className="pointer-events-auto fixed top-3 left-1/2 z-(--z-overlay) flex -translate-x-1/2 items-center gap-3 rounded-full border border-accent/40 bg-glass-strong px-4 py-2 text-xs text-ink shadow-e3 backdrop-blur-xl"
          data-testid="lens-banner"
        >
          <Crosshair size={14} className="text-accent" aria-hidden />
          <span>
            <strong className="font-semibold">Lens</strong> — click anything to analyze · <kbd>Shift</kbd>-click to compare
            {selections.length > 1 && <span className="text-accent"> · {selections.length} selected</span>}
          </span>
          <button type="button" onClick={() => setLens(false)} className="rounded-full p-0.5 text-ink-3 hover:bg-surface-2 hover:text-ink" aria-label="Leave lens mode (Esc)">
            <X size={14} aria-hidden />
          </button>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
