"use client";

import { useQuery } from "@tanstack/react-query";
import { Bot, Crosshair, Send, TriangleAlert } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { AnswerBody, BlockView, Trace } from "@/components/analyst/answer-view";
import { openDock, setLens } from "@/components/analyst/store";
import { Chip } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { type Block, type ChatAnswer, type Step, streamChat, toHistory } from "@/lib/agent";
import { api, ApiError } from "@/lib/api";
import { ASK_EVENT } from "@/lib/ask";
import { enterDelay } from "@/lib/motion";

type Turn = { id: number; question: string; steps: Step[]; blocks: Block[]; response?: ChatAnswer; error?: string };

export function AssistantPage() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [text, setText] = useState("");
  const [pending, setPending] = useState(false);
  const suggestions = useQuery({ queryKey: ["agent-suggestions"], queryFn: () => api.get<{ suggestions: string[] }>("/api/agent/suggestions") });
  const end = useRef<HTMLDivElement>(null);
  const next = useRef(1);
  const turnsRef = useRef(turns);
  useEffect(() => {
    turnsRef.current = turns;
  });

  const update = (id: number, patch: (t: Turn) => Partial<Turn>) => setTurns((all) => all.map((t) => (t.id === id ? { ...t, ...patch(t) } : t)));

  const ask = async (question: string) => {
    const q = question.trim();
    if (q.length < 2 || pending) return;
    const id = next.current++;
    const history = toHistory(turnsRef.current.map((t) => ({ question: t.question, answer: t.response })));
    setTurns((t) => [...t, { id, question: q, steps: [], blocks: [] }]);
    setText("");
    setPending(true);
    try {
      const response = await streamChat({ message: q, context: { page: "assistant" }, history }, (event) => {
        if (event.type === "step") update(id, (t) => ({ steps: [...t.steps.filter((s) => s.id !== event.id), event] }));
        else if (event.type === "block") update(id, (t) => ({ blocks: [...t.blocks, event.block] }));
      });
      update(id, (t) => ({ response, steps: response.steps ?? t.steps }));
    } catch (error) {
      update(id, () => ({
        error: error instanceof ApiError ? `${error.message}${error.requestId ? ` (ref ${error.requestId.slice(0, 12)})` : ""}` : "Something went wrong.",
      }));
    } finally {
      setPending(false);
    }
  };

  // A guided-menu card links here with ?q=...: ask once, then clean the URL.
  const prefilled = useRef(false);
  useEffect(() => {
    if (prefilled.current) return;
    prefilled.current = true;
    const q = new URLSearchParams(window.location.search).get("q");
    if (q) {
      window.history.replaceState(null, "", window.location.pathname);
      void ask(q);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // The command palette hands over questions while this page is open (no remount, the conversation stays).
  const askLatest = useRef(ask);
  useEffect(() => {
    askLatest.current = ask;
  });
  useEffect(() => {
    const onAsk = (e: Event) => void askLatest.current(String((e as CustomEvent<string>).detail ?? ""));
    window.addEventListener(ASK_EVENT, onAsk);
    return () => window.removeEventListener(ASK_EVENT, onAsk);
  }, []);

  const last = turns[turns.length - 1];
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns.length, last?.steps.length, last?.response]);

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <PageHeader
        title="Ask about your inventory"
        description="Answers come from your permitted data through the same checked queries as the dashboards. The assistant never writes SQL, and every number comes from a result you can inspect."
        actions={
          <Button
            size="sm"
            onClick={() => {
              openDock(true);
              setLens(true);
            }}
            title="Point at anything on any page and ask about it"
          >
            <Crosshair size={13} aria-hidden /> Analyze anything on screen
          </Button>
        }
      />

      {turns.length === 0 && (
        <div className="rise panel p-4 sm:p-5" style={enterDelay(1)}>
          <p className="mb-3 flex items-center gap-1.5 text-dense font-medium text-ink-2">
            <Bot size={14} aria-hidden /> Try asking
          </p>
          <div className="flex flex-wrap gap-2">
            {(suggestions.data?.suggestions ?? []).map((s) => (
              <Chip key={s} onClick={() => void ask(s)}>
                {s}
              </Chip>
            ))}
          </div>
        </div>
      )}

      <ol className="space-y-5" aria-live="polite">
        {turns.map((t) => {
          const running = !t.response && !t.error;
          return (
            <li key={t.id} className="space-y-2">
              <p className="ml-auto w-fit max-w-[85%] rounded-panel rounded-br-[0.25rem] bg-surface-3 px-3.5 py-2 text-sm text-ink shadow-e1">{t.question}</p>
              <div className="panel p-4 sm:p-5">
                <Trace steps={t.steps} running={running} />
                {running && t.blocks.length > 0 && (
                  <div className="mt-3 space-y-3">
                    {t.blocks.map((b, i) => (
                      <BlockView key={i} block={b} />
                    ))}
                  </div>
                )}
                {t.error && (
                  <p role="alert" className="flex items-start gap-2 text-sm text-signal">
                    <TriangleAlert size={15} className="mt-0.5 shrink-0" aria-hidden /> {t.error}
                  </p>
                )}
                {t.response && (
                  <div className={t.steps.length > 0 ? "mt-3 border-t border-line pt-3" : undefined}>
                    <AnswerBody answer={t.response} onAsk={(q) => void ask(q)} turnId={t.id} testId="assistant-answer" />
                  </div>
                )}
              </div>
            </li>
          );
        })}
      </ol>
      <div ref={end} />

      <form
        className="sticky bottom-3 flex gap-2 rounded-panel border border-control-line bg-surface p-1.5 shadow-e2 transition-[border-color,box-shadow] focus-within:border-accent focus-within:ring-1 focus-within:ring-accent"
        onSubmit={(e) => {
          e.preventDefault();
          void ask(text);
        }}
      >
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          maxLength={500}
          placeholder="e.g. Which items are below reorder level?"
          aria-label="Ask a question"
          data-focus-frame
          className="h-10 min-w-0 flex-1 bg-transparent px-2.5 text-sm text-ink outline-none placeholder:text-ink-3"
        />
        <Button type="submit" variant="primary" size="lg" disabled={pending || text.trim().length < 2}>
          <Send size={14} aria-hidden /> Ask
        </Button>
      </form>
    </div>
  );
}
