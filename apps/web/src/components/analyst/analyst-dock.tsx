"use client";

import { useQuery } from "@tanstack/react-query";
import { clsx } from "clsx";
import { ArrowUp, Crosshair, MessageSquarePlus, Pin, PinOff, Sparkles, TriangleAlert, X } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useEffect, useRef, useState } from "react";

import { AnswerBody, BlockView, Trace } from "@/components/analyst/answer-view";
import {
  ask,
  clearConversation,
  clearSelections,
  openDock,
  removeSelection,
  suggestionsFor,
  toggleLens,
  togglePin,
  type Turn,
  unpin,
  useAnalyst,
} from "@/components/analyst/store";
import type { Selection } from "@/lib/agent";
import { api } from "@/lib/api";
import { humanize } from "@/lib/format";
import { DUR, EASE, REDUCED_DUR } from "@/lib/motion";

const KIND_LABEL: Record<Selection["kind"], string> = {
  warehouse: "Warehouse",
  location: "Location",
  item: "Item",
  item_group: "Group",
  stage: "Stage",
  abc: "ABC",
  stock_status: "Status",
  metric: "Metric",
  insight: "Insight",
};
const WIDTH_KEY = "lumiant-dock-w";
const MIN_REM = 22;
const MAX_REM = 44;

function Chip({ sel, onRemove }: { sel: Selection; onRemove?: () => void }) {
  return (
    <span className="inline-flex max-w-full items-center gap-1.5 rounded-full border border-accent/35 bg-accent-soft py-0.5 pr-1 pl-2.5 text-xs text-ink">
      <span className="eyebrow !text-[0.5625rem] !text-accent">{KIND_LABEL[sel.kind]}</span>
      <span className="truncate">{sel.label ?? humanize(sel.id)}</span>
      {onRemove && (
        <button type="button" onClick={onRemove} className="rounded-full p-0.5 text-ink-3 hover:bg-surface-2 hover:text-ink" aria-label={`Remove ${sel.label ?? sel.id}`}>
          <X size={11} aria-hidden />
        </button>
      )}
    </span>
  );
}

function TurnView({ turn, pinned }: { turn: Turn; pinned: boolean }) {
  const running = !turn.answer && !turn.error;
  return (
    <li className="space-y-2.5">
      <div className="ml-auto w-fit max-w-[90%] space-y-1.5 rounded-xl rounded-br-sm bg-surface-3 px-3 py-2 text-sm text-ink shadow-e1">
        <p>{turn.question}</p>
        {turn.selections.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {turn.selections.map((s) => (
              <Chip key={`${s.kind}:${s.id}`} sel={s} />
            ))}
          </div>
        )}
      </div>
      <div className="rounded-xl border border-line bg-surface p-3.5 shadow-e1">
        <Trace steps={turn.steps} running={running} />
        {running && turn.blocks.length > 0 && (
          <div className="mt-3 space-y-3">
            {turn.blocks.map((b, i) => (
              <BlockView key={i} block={b} compact />
            ))}
          </div>
        )}
        {turn.error && (
          <p role="alert" className="mt-2 flex items-start gap-2 text-sm text-signal">
            <TriangleAlert size={15} className="mt-0.5 shrink-0" aria-hidden /> {turn.error}
          </p>
        )}
        {turn.answer && (
          <div className={clsx(turn.steps.length > 0 && "mt-3 border-t border-line pt-3")}>
            <AnswerBody
              answer={turn.answer}
              onAsk={(q) => void ask(q)}
              turnId={turn.id}
              testId="analyst-answer"
              compact
              extra={
                <button
                  type="button"
                  onClick={() => togglePin(turn)}
                  className={clsx("inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 hover:bg-surface-2", pinned ? "text-accent" : "hover:text-ink")}
                  aria-pressed={pinned}
                >
                  {pinned ? <PinOff size={12} aria-hidden /> : <Pin size={12} aria-hidden />} {pinned ? "Pinned" : "Pin"}
                </button>
              }
            />
          </div>
        )}
      </div>
    </li>
  );
}

/** Drag the left edge to resize; the width lives in a CSS variable on <html> so the page can make room for it. */
function useDockWidth() {
  useEffect(() => {
    try {
      const saved = Number(window.localStorage.getItem(WIDTH_KEY));
      if (saved >= MIN_REM && saved <= MAX_REM) document.documentElement.style.setProperty("--dock-w", `${saved}rem`);
    } catch {
      // storage unavailable: default width
    }
  }, []);
  return (e: React.PointerEvent) => {
    e.preventDefault();
    const rem = parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
    const move = (ev: PointerEvent) => {
      const width = Math.min(MAX_REM, Math.max(MIN_REM, (window.innerWidth - ev.clientX) / rem));
      document.documentElement.style.setProperty("--dock-w", `${width.toFixed(1)}rem`);
      try {
        window.localStorage.setItem(WIDTH_KEY, width.toFixed(1));
      } catch {
        // ignore
      }
    };
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };
}

/**
 * The Analyst dock: a conversation that stays open across pages and is fed by what the user points at. Answers stream
 * in as a trace of the agent's work, then the grounded answer with its sources.
 */
export function AnalystDock({ canCost }: { canCost: boolean }) {
  const { open, lens, selections, turns, busy, board } = useAnalyst();
  const reduce = useReducedMotion();
  const [text, setText] = useState("");
  const [showBoard, setShowBoard] = useState(false);
  const end = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  const startResize = useDockWidth();
  const defaults = useQuery({
    queryKey: ["agent-suggestions"],
    queryFn: () => api.get<{ suggestions: string[] }>("/api/agent/suggestions"),
    enabled: open,
    staleTime: 300_000,
  });

  const lastTurn = turns[turns.length - 1];
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "end" });
  }, [turns.length, lastTurn?.steps.length, lastTurn?.answer, reduce]);
  useEffect(() => {
    if (open && selections.length > 0) input.current?.focus({ preventScroll: true });
  }, [open, selections]);

  const send = (q: string) => {
    if (q.trim().length < 2 || busy) return;
    setShowBoard(false);
    setText("");
    void ask(q);
  };
  const contextual = suggestionsFor(selections, canCost);
  const starters = contextual.length ? contextual : (defaults.data?.suggestions ?? []).slice(0, 5);
  const pinnedIds = new Set(board.map((p) => p.id));

  return (
    <AnimatePresence>
      {open && (
        <motion.aside
          key="analyst"
          data-lens-ui
          aria-label="Analyst"
          initial={reduce ? { opacity: 0 } : { opacity: 0, x: 32 }}
          animate={{ opacity: 1, x: 0 }}
          exit={reduce ? { opacity: 0 } : { opacity: 0, x: 32 }}
          transition={{ duration: reduce ? REDUCED_DUR : DUR.slow, ease: EASE.out }}
          onKeyDown={(e) => {
            if (e.key === "Escape" && !lens) openDock(false);
          }}
          className="fixed inset-y-0 right-0 z-(--z-nav) flex w-full flex-col border-l border-glass-line bg-glass-strong shadow-e3 backdrop-blur-xl sm:w-(--dock-w)"
          data-testid="analyst-dock"
        >
          <div
            role="separator"
            aria-orientation="vertical"
            aria-label="Resize the Analyst"
            onPointerDown={startResize}
            className="absolute inset-y-0 -left-1 hidden w-2 cursor-col-resize hover:bg-accent/20 sm:block"
          />
          <header className="flex items-center gap-2 border-b border-line px-4 py-3">
            <span className="grid size-7 place-items-center rounded-lg bg-accent-soft text-accent shadow-[var(--glow)]">
              <Sparkles size={15} aria-hidden />
            </span>
            <div className="min-w-0 flex-1">
              <h2 className="text-sm font-semibold tracking-tight text-ink">Analyst</h2>
              <p className="truncate text-[0.6875rem] text-ink-3">Every number comes from your permitted data</p>
            </div>
            <button
              type="button"
              onClick={toggleLens}
              aria-pressed={lens}
              title="Lens: click anything on the page to analyze it (L)"
              className={clsx("inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium transition-colors", lens ? "bg-accent text-accent-ink" : "text-ink-2 hover:bg-surface-2 hover:text-ink")}
            >
              <Crosshair size={13} aria-hidden /> Lens
            </button>
            <button
              type="button"
              onClick={() => setShowBoard((v) => !v)}
              aria-pressed={showBoard}
              title="Pinned answers"
              className={clsx("relative rounded-md p-1.5 transition-colors", showBoard ? "bg-surface-3 text-ink" : "text-ink-3 hover:bg-surface-2 hover:text-ink")}
            >
              <Pin size={14} aria-hidden />
              <span className="sr-only">Pinned answers</span>
              {board.length > 0 && <span className="figure absolute -top-0.5 -right-0.5 rounded-full bg-accent px-1 text-[0.5625rem] text-accent-ink">{board.length}</span>}
            </button>
            <button type="button" onClick={clearConversation} title="New conversation" className="rounded-md p-1.5 text-ink-3 hover:bg-surface-2 hover:text-ink">
              <MessageSquarePlus size={14} aria-hidden />
              <span className="sr-only">New conversation</span>
            </button>
            <button type="button" onClick={() => openDock(false)} className="rounded-md p-1.5 text-ink-3 hover:bg-surface-2 hover:text-ink" aria-label="Close the Analyst">
              <X size={15} aria-hidden />
            </button>
          </header>

          {selections.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5 border-b border-line px-4 py-2.5" aria-label="Analyzing">
              {selections.map((s) => (
                <Chip key={`${s.kind}:${s.id}`} sel={s} onRemove={() => removeSelection(s)} />
              ))}
              <button type="button" onClick={clearSelections} className="ml-auto text-[0.6875rem] text-ink-3 hover:text-ink">
                Clear
              </button>
            </div>
          )}

          <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-4">
            {showBoard ? (
              <section aria-label="Pinned answers" className="space-y-2">
                <p className="eyebrow">Pinned answers</p>
                {board.length === 0 && <p className="text-sm text-ink-3">Pin an answer to keep it here (this browser only).</p>}
                {board.map((p) => (
                  <article key={p.id} className="rounded-lg border border-line bg-surface p-3 text-sm">
                    <p className="font-medium text-ink">{p.question}</p>
                    <p className="mt-1 text-ink-2">{p.answer}</p>
                    <div className="mt-2 flex items-center gap-3 text-xs text-ink-3">
                      <span className="figure">{new Date(p.at).toLocaleString()}</span>
                      <button type="button" onClick={() => send(p.question)} className="hover:text-accent">
                        Ask again (fresh numbers)
                      </button>
                      <button type="button" onClick={() => unpin(p.id)} className="ml-auto hover:text-ink">
                        Unpin
                      </button>
                    </div>
                  </article>
                ))}
              </section>
            ) : turns.length === 0 ? (
              <div className="space-y-4">
                <div className="rounded-xl border border-dashed border-line-strong p-4">
                  <p className="text-sm font-medium text-ink">{selections.length ? "What would you like to know?" : "Point at anything"}</p>
                  <p className="mt-1 text-xs leading-relaxed text-ink-3">
                    Right-click a KPI, chart, row or insight — or press <kbd>L</kbd> for Lens and click it. Shift-click several to compare them.
                  </p>
                </div>
                {starters.length > 0 && (
                  <div className="flex flex-wrap gap-2" aria-label="Suggested questions">
                    {starters.map((s) => (
                      <button key={s} type="button" onClick={() => send(s)} className="rounded-full border border-line px-3 py-1.5 text-left text-xs text-ink-2 transition-colors hover:border-accent/50 hover:bg-accent-soft hover:text-accent">
                        {s}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <ol className="space-y-5" aria-live="polite">
                {turns.map((t) => (
                  <TurnView key={t.id} turn={t} pinned={pinnedIds.has(`${t.id}:${t.question}`)} />
                ))}
                {!busy && contextual.length > 0 && (
                  <li className="flex flex-wrap gap-2" aria-label="Suggested questions">
                    {contextual.map((s) => (
                      <button key={s} type="button" onClick={() => send(s)} className="rounded-full border border-line px-3 py-1 text-xs text-ink-2 hover:border-accent/50 hover:bg-accent-soft hover:text-accent">
                        {s}
                      </button>
                    ))}
                  </li>
                )}
              </ol>
            )}
            <div ref={end} />
          </div>

          <form
            className="border-t border-line p-3"
            onSubmit={(e) => {
              e.preventDefault();
              send(text);
            }}
          >
            <div className="flex items-end gap-2 rounded-xl border border-control-line bg-surface px-3 py-2 transition-colors focus-within:border-accent/70">
              <textarea
                ref={input}
                value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    send(text);
                  }
                }}
                rows={1}
                maxLength={500}
                placeholder={selections.length ? "Ask about the selection…" : "Ask anything about your inventory…"}
                aria-label="Ask the Analyst"
                className="max-h-32 min-h-6 flex-1 resize-none bg-transparent text-sm text-ink outline-none placeholder:text-ink-3"
              />
              <button
                type="submit"
                disabled={busy || text.trim().length < 2}
                className="grid size-7 shrink-0 place-items-center rounded-lg bg-accent text-accent-ink transition-opacity disabled:opacity-35"
                aria-label="Send"
              >
                <ArrowUp size={15} aria-hidden />
              </button>
            </div>
          </form>
        </motion.aside>
      )}
    </AnimatePresence>
  );
}
