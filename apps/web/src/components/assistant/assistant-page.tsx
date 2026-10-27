"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { clsx } from "clsx";
import { Bot, Send, ThumbsDown, ThumbsUp, TriangleAlert } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { ProvenanceButton } from "@/components/data/provenance";
import { SimpleTable, type SimpleColumn } from "@/components/data/simple-table";
import { api, ApiError, type Provenance, type ResultWarning, type Row } from "@/lib/api";
import { formatMoney, formatNumber, formatQuantity } from "@/lib/format";

type Kind = "text" | "qty" | "money" | "int" | "date";
type ColumnDef = { key: string; label: string; kind: Kind };
type TableBlock = { type: "table"; title: string; columns: ColumnDef[]; rows: Row[] };
type BarBlock = { type: "bar"; title: string; label_key: string; value_key: string; kind: "money" | "qty"; unit_key: string; rows: Row[] };
type Block = TableBlock | BarBlock;
type Choice = { label: string; item_id?: string; warehouse_id?: string };

type ChatResponse = {
  mode: "rules" | "anthropic";
  notice: string | null;
  kind: "tools" | "clarify" | "unsupported";
  answer: string;
  blocks: Block[];
  tool_calls: { name: string; args: Record<string, unknown> }[];
  provenance: Provenance[];
  warnings: ResultWarning[];
  follow_ups: string[];
  choices: Choice[];
  grounding: { passed: boolean; source: string };
};

type Turn = { id: number; question: string; response?: ChatResponse; error?: string };

function cell(kind: Kind, row: Row, key: string) {
  const v = row[key];
  if (v === null || v === undefined || v === "") return <span className="text-ink-3">—</span>;
  if (kind === "qty") return <span className="figure">{formatQuantity(v as string, row.uom as string | undefined)}</span>;
  if (kind === "money") return <span className="figure">{formatMoney(v as string, row.currency as string | undefined)}</span>;
  if (kind === "int") return <span className="figure">{formatNumber(v as string, { maxFraction: 0 })}</span>;
  return <span className={kind === "date" ? "figure text-xs" : ""}>{String(v)}</span>;
}

function TableView({ block }: { block: TableBlock }) {
  const columns: SimpleColumn[] = block.columns.map((c) => ({
    key: c.key,
    label: c.label,
    align: c.kind === "text" || c.kind === "date" ? undefined : "right",
    render: (r) => cell(c.kind, r, c.key),
  }));
  return (
    <div>
      <p className="eyebrow mb-1">{block.title}</p>
      <SimpleTable columns={columns} rows={block.rows} empty="Nothing to show." rowKey={(_, i) => String(i)} minWidth="30rem" />
    </div>
  );
}

function BarView({ block }: { block: BarBlock }) {
  const groups = new Map<string, Row[]>();
  for (const r of block.rows) groups.set(String(r[block.unit_key] ?? ""), [...(groups.get(String(r[block.unit_key] ?? "")) ?? []), r]);
  return (
    <div className="space-y-3">
      <p className="eyebrow">{block.title}</p>
      {[...groups.entries()].map(([unit, rows]) => {
        const max = Math.max(...rows.map((r) => Number(r[block.value_key])), 0) || 1;
        return (
          <div key={unit} className="space-y-1">
            {groups.size > 1 && <p className="figure text-xs text-ink-3">{unit}</p>}
            {rows.map((r, i) => (
              <div key={i} className="grid grid-cols-[minmax(6rem,12rem)_1fr_auto] items-center gap-3 text-sm">
                <span className="truncate text-ink-2" title={String(r[block.label_key] ?? "")}>{String(r[block.label_key] ?? "Not set")}</span>
                <span className="h-3 rounded-sm bg-surface-2">
                  <span className="block h-full rounded-sm bg-accent" style={{ width: `${(Number(r[block.value_key]) / max) * 100}%` }} />
                </span>
                <span className="figure text-xs">
                  {block.kind === "money" ? formatMoney(r[block.value_key] as string, unit) : formatQuantity(r[block.value_key] as string, unit)}
                </span>
              </div>
            ))}
          </div>
        );
      })}
    </div>
  );
}

function Feedback({ turn }: { turn: number }) {
  const [sent, setSent] = useState<"up" | "down" | null>(null);
  const send = useMutation({
    mutationFn: (rating: "up" | "down") => api.post("/api/agent/feedback", { rating, reason: `turn ${turn}` }),
    onSuccess: (_d, rating) => setSent(rating),
  });
  return (
    <span className="flex items-center gap-1 text-ink-3" role="group" aria-label="Was this helpful?">
      {sent ? (
        <span className="text-xs">Thanks for the feedback</span>
      ) : (
        <>
          <button type="button" onClick={() => send.mutate("up")} className="rounded-sm p-1 hover:bg-surface-2 hover:text-ink" aria-label="Helpful"><ThumbsUp size={14} /></button>
          <button type="button" onClick={() => send.mutate("down")} className="rounded-sm p-1 hover:bg-surface-2 hover:text-ink" aria-label="Not helpful"><ThumbsDown size={14} /></button>
        </>
      )}
    </span>
  );
}

function Answer({ turn, onAsk }: { turn: Turn; onAsk: (q: string) => void }) {
  const r = turn.response;
  if (turn.error) {
    return (
      <p role="alert" className="flex items-start gap-2 text-sm text-signal">
        <TriangleAlert size={15} className="mt-0.5 shrink-0" aria-hidden /> {turn.error}
      </p>
    );
  }
  if (!r) return <p className="text-sm text-ink-3" role="status">Thinking…</p>;
  return (
    <div className="space-y-3" data-testid="assistant-answer">
      {r.notice && <p className="text-xs text-ink-3">{r.notice}</p>}
      <p className="text-sm leading-relaxed text-ink">{r.answer}</p>
      {r.blocks.map((b, i) => (b.type === "table" ? <TableView key={i} block={b} /> : <BarView key={i} block={b} />))}
      {r.warnings.length > 0 && (
        <ul className="space-y-1">
          {r.warnings.filter((w) => w.code !== "truncated").map((w, i) => (
            <li key={i} className="flex items-start gap-1.5 text-xs text-ink-2">
              <TriangleAlert size={13} className="mt-px shrink-0 text-signal" aria-hidden /> {w.message}
            </li>
          ))}
        </ul>
      )}
      {r.choices.length > 0 && (
        <div className="flex flex-wrap gap-2" aria-label="Choose one">
          {r.choices.map((c, i) => (
            <button
              key={i}
              type="button"
              onClick={() =>
                onAsk(
                  c.warehouse_id
                    ? `compare cost of item ${c.item_id} in warehouse ${c.warehouse_id}`
                    : `how much stock of item ${c.item_id}`,
                )
              }
              className="rounded-sm border border-line-strong px-2.5 py-1.5 text-left text-xs hover:bg-surface-2"
            >
              {c.label}
            </button>
          ))}
        </div>
      )}
      {r.follow_ups.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {r.follow_ups.map((f) => (
            <button key={f} type="button" onClick={() => onAsk(f)} className="rounded-full border border-line px-3 py-1 text-xs text-ink-2 hover:bg-surface-2">
              {f}
            </button>
          ))}
        </div>
      )}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-line pt-2 text-xs text-ink-3">
        <span title={r.mode === "rules" ? "Built-in question matching; no data left this system" : "External AI chose the analysis and worded the answer from the results"}>
          {r.mode === "rules" ? "Built-in matching" : "AI-assisted"}
        </span>
        {r.tool_calls.length > 0 && <span className="figure">used: {r.tool_calls.map((c) => c.name).join(", ")}</span>}
        {r.provenance.map((p, i) => <ProvenanceButton key={i} provenance={p} label={r.provenance.length > 1 ? `Source ${i + 1}` : "Source"} />)}
        <Feedback turn={turn.id} />
      </div>
    </div>
  );
}

export function AssistantPage() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [text, setText] = useState("");
  const suggestions = useQuery({ queryKey: ["agent-suggestions"], queryFn: () => api.get<{ suggestions: string[] }>("/api/agent/suggestions") });
  const end = useRef<HTMLDivElement>(null);
  const next = useRef(1);

  const chat = useMutation({
    mutationFn: ({ question }: { id: number; question: string }) => api.post<ChatResponse>("/api/agent/chat", { message: question }),
    onSuccess: (response, { id }) => setTurns((t) => t.map((x) => (x.id === id ? { ...x, response } : x))),
    onError: (error, { id }) =>
      setTurns((t) => t.map((x) => (x.id === id ? { ...x, error: error instanceof ApiError ? `${error.message}${error.requestId ? ` (ref ${error.requestId.slice(0, 12)})` : ""}` : "Something went wrong." } : x))),
  });

  const ask = (question: string) => {
    const q = question.trim();
    if (q.length < 2 || chat.isPending) return;
    const id = next.current++;
    setTurns((t) => [...t, { id, question: q }]);
    setText("");
    chat.mutate({ id, question: q });
  };

  // A guided-menu card links here with ?q=...: ask once, then clean the URL.
  const prefilled = useRef(false);
  useEffect(() => {
    if (prefilled.current) return;
    prefilled.current = true;
    const q = new URLSearchParams(window.location.search).get("q");
    if (q) {
      window.history.replaceState(null, "", window.location.pathname);
      ask(q);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns]);

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <div className="rise">
        <p className="eyebrow">Assistant</p>
        <h1 className="mt-1 text-2xl font-bold tracking-tight text-ink sm:text-[1.75rem]">Ask about your inventory</h1>
        <p className="mt-1 text-sm text-ink-3">
          Answers come from your permitted data through the same checked queries as the dashboards. The assistant never writes SQL, and every number comes from a result you can inspect.
        </p>
      </div>

      {turns.length === 0 && (
        <div className="rise rounded-md border border-line bg-surface p-4" style={{ animationDelay: "60ms" }}>
          <p className="eyebrow mb-2 flex items-center gap-1.5"><Bot size={13} aria-hidden /> Try asking</p>
          <div className="flex flex-wrap gap-2">
            {(suggestions.data?.suggestions ?? []).map((s) => (
              <button key={s} type="button" onClick={() => ask(s)} className="rounded-full border border-line px-3 py-1.5 text-sm text-ink-2 hover:bg-surface-2">
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      <ol className="space-y-5" aria-live="polite">
        {turns.map((t) => (
          <li key={t.id} className="space-y-2">
            <p className={clsx("ml-auto w-fit max-w-[85%] rounded-md bg-ink px-3 py-2 text-sm text-surface")}>{t.question}</p>
            <div className="rounded-md border border-line bg-surface p-4">
              <Answer turn={t} onAsk={ask} />
            </div>
          </li>
        ))}
      </ol>
      <div ref={end} />

      <form
        className="sticky bottom-3 flex gap-2 rounded-md border border-line-strong bg-surface p-2 shadow-lg"
        onSubmit={(e) => {
          e.preventDefault();
          ask(text);
        }}
      >
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          maxLength={500}
          placeholder="e.g. Which items are below reorder level?"
          aria-label="Ask a question"
          className="h-10 min-w-0 flex-1 bg-transparent px-2 text-sm outline-none placeholder:text-ink-3"
        />
        <button type="submit" disabled={chat.isPending || text.trim().length < 2} className="inline-flex h-10 items-center gap-1.5 rounded-sm bg-ink px-4 text-sm font-medium text-surface disabled:opacity-40">
          <Send size={14} aria-hidden /> Ask
        </button>
      </form>
    </div>
  );
}
