"use client";

import { useMutation } from "@tanstack/react-query";
import { clsx } from "clsx";
import { CheckCircle2, CircleDashed, Loader2, ShieldCheck, ThumbsDown, ThumbsUp, TriangleAlert, XCircle } from "lucide-react";
import { useState } from "react";

import { ProvenanceButton } from "@/components/data/provenance";
import { SimpleTable, type SimpleColumn } from "@/components/data/simple-table";
import type { BarBlock, Block, ChatAnswer, ColumnKind, Step, TableBlock } from "@/lib/agent";
import { api, type Row } from "@/lib/api";
import { formatMoney, formatNumber, formatQuantity } from "@/lib/format";

function cell(kind: ColumnKind, row: Row, key: string) {
  const v = row[key];
  if (v === null || v === undefined || v === "") return <span className="text-ink-3">—</span>;
  if (kind === "qty") return <span className="figure">{formatQuantity(v as string, row.uom as string | undefined)}</span>;
  if (kind === "money") return <span className="figure">{formatMoney(v as string, row.currency as string | undefined)}</span>;
  if (kind === "int") return <span className="figure">{formatNumber(v as string, { maxFraction: 0 })}</span>;
  if (kind === "pct") return <span className="figure">{formatNumber(v as string, { maxFraction: 1 })}%</span>;
  return <span className={kind === "date" ? "figure text-xs" : ""}>{String(v)}</span>;
}

export function TableView({ block, compact }: { block: TableBlock; compact?: boolean }) {
  const columns: SimpleColumn[] = block.columns.map((c) => ({
    key: c.key,
    label: c.label,
    align: c.kind === "text" || c.kind === "date" ? undefined : "right",
    render: (r) => cell(c.kind, r, c.key),
  }));
  return (
    <div className="min-w-0">
      <p className="eyebrow mb-1">{block.title}</p>
      <SimpleTable columns={columns} rows={block.rows} empty="Nothing to show." rowKey={(_, i) => String(i)} minWidth={compact ? "22rem" : "30rem"} />
    </div>
  );
}

export function BarView({ block }: { block: BarBlock }) {
  const groups = new Map<string, Row[]>();
  for (const r of block.rows) groups.set(String(r[block.unit_key] ?? ""), [...(groups.get(String(r[block.unit_key] ?? "")) ?? []), r]);
  return (
    <div className="space-y-3">
      <p className="eyebrow">{block.title}</p>
      {[...groups.entries()].map(([unit, rows]) => {
        const max = Math.max(...rows.map((r) => Number(r[block.value_key])), 0) || 1;
        return (
          <div key={unit} className="space-y-1.5">
            {groups.size > 1 && <p className="figure text-xs text-ink-3">{unit}</p>}
            {rows.map((r, i) => (
              <div key={i} className="grid grid-cols-[minmax(5rem,10rem)_1fr_auto] items-center gap-3 text-sm">
                <span className="truncate text-ink-2" title={String(r[block.label_key] ?? "")}>{String(r[block.label_key] ?? "Not set")}</span>
                <span className="h-2.5 overflow-hidden rounded-full bg-surface-2">
                  <span
                    className="bar-grow block h-full rounded-full bg-(--viz-1)"
                    style={{ width: `${(Number(r[block.value_key]) / max) * 100}%`, animationDelay: `${Math.min(i, 8) * 40}ms` }}
                  />
                </span>
                <span className="figure text-xs text-ink">
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

export function BlockView({ block, compact }: { block: Block; compact?: boolean }) {
  return block.type === "table" ? <TableView block={block} compact={compact} /> : <BarView block={block} />;
}

/** The agent's work as it happens: understand → each analysis (rows, time) → wording → number check. */
export function Trace({ steps, running }: { steps: Step[]; running: boolean }) {
  if (steps.length === 0 && !running) return null;
  return (
    <ol className="space-y-1" aria-label="What the assistant did">
      {steps.map((s) => (
        <li key={s.id} className="trace-step flex items-start gap-2 text-xs">
          {s.status === "running" ? (
            <Loader2 size={13} className="mt-px shrink-0 animate-spin text-accent" aria-hidden />
          ) : s.status === "failed" ? (
            <XCircle size={13} className="mt-px shrink-0 text-signal" aria-hidden />
          ) : s.id === "ground" ? (
            <ShieldCheck size={13} className="mt-px shrink-0 text-ok" aria-hidden />
          ) : (
            <CheckCircle2 size={13} className="mt-px shrink-0 text-ok" aria-hidden />
          )}
          <span className={clsx("min-w-0", s.status === "running" ? "text-ink" : "text-ink-2")}>
            {s.label}
            {s.detail && <span className="text-ink-3"> — {s.detail}</span>}
            {s.rows !== undefined && s.status !== "running" && (
              <span className="figure text-ink-3">
                {" "}
                · {s.rows} row{s.rows === 1 ? "" : "s"}
                {s.ms !== undefined ? ` · ${s.ms} ms` : ""}
              </span>
            )}
          </span>
        </li>
      ))}
      {running && steps.every((s) => s.status !== "running") && (
        <li className="flex items-center gap-2 text-xs text-ink-3">
          <CircleDashed size={13} className="animate-spin" aria-hidden /> Working…
        </li>
      )}
    </ol>
  );
}

export function Feedback({ turn }: { turn: number }) {
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

const MODE_LABEL: Record<ChatAnswer["mode"], string> = {
  rules: "Built-in matching",
  anthropic: "AI-assisted (Claude)",
  gemini: "AI-assisted (Gemini)",
};

/** A finished answer: text, result blocks, warnings, clarification choices, follow-ups, sources and feedback. */
export function AnswerBody({
  answer: r,
  onAsk,
  turnId,
  testId,
  compact,
  extra,
}: {
  answer: ChatAnswer;
  onAsk: (q: string) => void;
  turnId: number;
  testId: string;
  compact?: boolean;
  extra?: React.ReactNode;
}) {
  return (
    <div className="answer-in space-y-3" data-testid={testId}>
      {r.notice && <p className="text-xs text-ink-3">{r.notice}</p>}
      <p className="text-sm leading-relaxed text-ink">{r.answer}</p>
      {r.blocks.map((b, i) => (
        <BlockView key={i} block={b} compact={compact} />
      ))}
      {r.warnings.length > 0 && (
        <ul className="space-y-1">
          {r.warnings
            .filter((w) => w.code !== "truncated")
            .map((w, i) => (
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
                onAsk(c.warehouse_id ? `compare cost of item ${c.item_id} in warehouse ${c.warehouse_id}` : `how much stock of item ${c.item_id}`)
              }
              className="rounded-md border border-line-strong px-2.5 py-1.5 text-left text-xs hover:bg-surface-2"
            >
              {c.label}
            </button>
          ))}
        </div>
      )}
      {r.follow_ups.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {r.follow_ups.map((f) => (
            <button key={f} type="button" onClick={() => onAsk(f)} className="rounded-full border border-line px-3 py-1 text-xs text-ink-2 transition-colors hover:border-accent/50 hover:bg-accent-soft hover:text-accent">
              {f}
            </button>
          ))}
        </div>
      )}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-line pt-2 text-xs text-ink-3">
        <span title={r.mode === "rules" ? "Built-in question matching; no data left this system" : "External AI chose the analysis and worded the answer from the results"}>
          {MODE_LABEL[r.mode] ?? r.mode}
        </span>
        {r.grounding.source === "model" && <span className="text-ok">numbers checked</span>}
        {r.tool_calls.length > 0 && <span className="figure">used: {r.tool_calls.map((c) => c.name).join(", ")}</span>}
        {r.elapsed_ms !== undefined && <span className="figure">{r.elapsed_ms} ms</span>}
        {r.provenance.map((p, i) => (
          <ProvenanceButton key={i} provenance={p} label={r.provenance.length > 1 ? `Source ${i + 1}` : "Source"} />
        ))}
        {extra}
        <Feedback turn={turnId} />
      </div>
    </div>
  );
}
