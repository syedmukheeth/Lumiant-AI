"use client";

import { useMutation } from "@tanstack/react-query";
import { clsx } from "clsx";
import {
  BookOpen,
  CheckCircle2,
  CircleDashed,
  Compass,
  Info,
  Loader2,
  MessageCircleQuestionMark,
  ShieldCheck,
  ThumbsDown,
  ThumbsUp,
  TriangleAlert,
  XCircle,
} from "lucide-react";
import { useId, useState } from "react";

import { ProvenanceButton } from "@/components/data/provenance";
import { SimpleTable, type SimpleColumn } from "@/components/data/simple-table";
import { Chip } from "@/components/ui/badge";
import { IconButton } from "@/components/ui/button";
import { ChartFrame, VIZ } from "@/components/viz/shared";
import { TrendArea, type TrendRow } from "@/components/viz/trend-area";
import type { BarBlock, Block, ChartBlock, ChartSeries, ChatAnswer, Choice, ColumnKind, SourcesBlock, Step, TableBlock } from "@/lib/agent";
import { api, type Row } from "@/lib/api";
import { formatMoney, formatNumber, formatQuantity, humanize, toChartNumber } from "@/lib/format";
import { enterDelay } from "@/lib/motion";

function cell(kind: ColumnKind, row: Row, key: string) {
  const v = row[key];
  if (v === null || v === undefined || v === "") return <span className="text-ink-3">–</span>;
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
      <p className="mb-1.5 text-dense font-medium text-ink-2">{block.title}</p>
      <SimpleTable columns={columns} rows={block.rows} empty="Nothing to show." rowKey={(_, i) => String(i)} minWidth={compact ? "22rem" : "30rem"} />
    </div>
  );
}

type BarItem = { label: string; title?: string; value: number; text: string };

/** Horizontal bars on one scale: label, a bar sized from the number, and the exact display string. */
function BarList({ items, max, color = VIZ[0], compact }: { items: BarItem[]; max?: number; color?: string; compact?: boolean }) {
  const top = max ?? (Math.max(...items.map((b) => b.value), 0) || 1);
  return (
    <div className="space-y-1.5">
      {items.map((b, i) => (
        <div
          key={i}
          className={clsx(
            "grid items-center gap-3 text-sm",
            compact ? "grid-cols-[minmax(4rem,7rem)_1fr_auto]" : "grid-cols-[minmax(5rem,10rem)_1fr_auto]",
          )}
        >
          <span className="truncate text-ink-2" title={b.title ?? b.label}>{b.label}</span>
          <span className="h-2 overflow-hidden rounded-full bg-surface-2">
            <span
              className="bar-grow block h-full rounded-full"
              style={{ width: `${(Math.max(b.value, 0) / top) * 100}%`, background: color, ...enterDelay(i) }}
            />
          </span>
          <span className="figure text-xs text-ink">{b.text}</span>
        </div>
      ))}
    </div>
  );
}

export function BarView({ block }: { block: BarBlock }) {
  const groups = new Map<string, Row[]>();
  for (const r of block.rows) groups.set(String(r[block.unit_key] ?? ""), [...(groups.get(String(r[block.unit_key] ?? "")) ?? []), r]);
  return (
    <div className="space-y-3">
      <p className="text-dense font-medium text-ink-2">{block.title}</p>
      {[...groups.entries()].map(([unit, rows]) => (
        <div key={unit} className="space-y-1.5">
          {groups.size > 1 && <p className="text-xs text-ink-3">{unit}</p>}
          <BarList
            items={rows.map((r) => ({
              label: String(r[block.label_key] ?? "Not set"),
              title: String(r[block.label_key] ?? ""),
              value: toChartNumber(r[block.value_key] as string),
              text: block.kind === "money" ? formatMoney(r[block.value_key] as string, unit) : formatQuantity(r[block.value_key] as string, unit),
            }))}
          />
        </div>
      ))}
    </div>
  );
}

type SeriesKind = ChartSeries["kind"];

/**
 * One value as printed: the API's decimal string formatted without float maths (`lib/format`), the same way a table
 * cell prints it. A string that is not a plain decimal is printed exactly as sent.
 */
function seriesText(kind: SeriesKind, value: string | number, unit: string): string {
  const text =
    kind === "money"
      ? formatMoney(value, unit || undefined)
      : kind === "qty"
        ? formatQuantity(value, unit || undefined)
        : kind === "int"
          ? formatNumber(value, { maxFraction: 0 })
          : `${formatNumber(value, { maxFraction: 1 })}%`;
  return text === "–" || text === "–%" ? String(value) : text;
}

type ChartPoint = { x: string; values: Record<string, number>; exact: Record<string, string> };
/** The series that share one axis: same kind and same currency or unit. */
type ChartPanel = { id: string; kind: SeriesKind; unit: string; series: ChartSeries[]; points: ChartPoint[] };

/** Split a chart block into one panel per kind and unit, so currencies and units never share an axis. */
function chartPanels(block: ChartBlock): ChartPanel[] {
  const panels = new Map<string, { panel: ChartPanel; keys: Set<string>; at: Map<string, number> }>();
  for (const row of block.rows) {
    const xv = row[block.x_key];
    const x = xv === null || xv === undefined || xv === "" ? "Not set" : String(xv);
    for (const s of block.series) {
      const v = row[s.key];
      if (v === null || v === undefined || v === "" || typeof v === "boolean") continue;
      const unit = s.unit_key ? String(row[s.unit_key] ?? "") : "";
      const id = `${s.kind}|${unit}`;
      let entry = panels.get(id);
      if (!entry) {
        entry = { panel: { id, kind: s.kind, unit, series: [], points: [] }, keys: new Set(), at: new Map() };
        panels.set(id, entry);
      }
      entry.keys.add(s.key);
      let i = entry.at.get(x);
      if (i === undefined) {
        i = entry.panel.points.push({ x, values: {}, exact: {} }) - 1;
        entry.at.set(x, i);
      }
      entry.panel.points[i].values[s.key] = toChartNumber(v);
      entry.panel.points[i].exact[s.key] = seriesText(s.kind, v, unit);
    }
  }
  return [...panels.values()].map(({ panel, keys }) => ({ ...panel, series: block.series.filter((s) => keys.has(s.key)) }));
}

const NO_UNIT: Record<SeriesKind, string> = { money: "No currency", qty: "No unit", int: "Count", pct: "Percent" };

function panelLabel(block: ChartBlock, p: ChartPanel) {
  if (p.unit) return `${block.title}, in ${p.unit}`;
  return p.kind === "pct" ? `${block.title}, in percent` : block.title;
}

/**
 * A chart answer. Line → the kit's TrendArea; bar → the bar list. Each kind and currency or unit gets its own panel
 * (never one axis for two units). Printed values are the API strings; numbers only size the marks.
 */
export function ChartView({ block, compact }: { block: ChartBlock; compact?: boolean }) {
  const panels = chartPanels(block);
  return (
    <div className="min-w-0 space-y-3" data-testid="answer-chart">
      <p className="text-dense font-medium text-ink-2">{block.title}</p>
      {panels.length === 0 && <p className="text-xs text-ink-3">Nothing to show.</p>}
      {panels.map((p) => {
        const label = panelLabel(block, p);
        const colors = p.series.map((_, i) => VIZ[i % VIZ.length]);
        return (
          <div key={p.id} className="min-w-0 space-y-1.5">
            {panels.length > 1 && <p className="text-xs text-ink-3">{p.unit || NO_UNIT[p.kind]}</p>}
            {block.variant === "line" && p.points.length > 1 ? (
              // The kit's legend sits below its fixed-height frame; the padding keeps it clear of the next block.
              <div className={clsx(p.series.length > 1 && "pb-7")}>
                <TrendArea
                  rows={p.points.map((pt): TrendRow => ({ label: pt.x, values: pt.values, exact: pt.exact }))}
                  series={p.series.map((s) => ({ key: s.key, label: s.label }))}
                  label={label}
                  height={compact ? 160 : 220}
                />
              </div>
            ) : (
              <ChartFrame
                label={label}
                table={{
                  columns: [humanize(block.x_key), ...p.series.map((s) => s.label)],
                  rows: p.points.map((pt) => [pt.x, ...p.series.map((s) => pt.exact[s.key] ?? "")]),
                }}
              >
                <div className="space-y-2.5">
                  {p.series.map((s, i) => (
                    <div key={s.key} className="space-y-1.5">
                      {p.series.length > 1 && (
                        <p className="flex items-center gap-1.5 text-xs text-ink-3">
                          <span className="size-2 shrink-0 rounded-full" style={{ background: colors[i] }} aria-hidden />
                          {s.label}
                        </p>
                      )}
                      <BarList
                        compact={compact}
                        color={colors[i]}
                        max={Math.max(...p.points.flatMap((pt) => Object.values(pt.values)), 0) || 1}
                        items={p.points
                          .filter((pt) => s.key in pt.values)
                          .map((pt) => ({ label: pt.x, value: pt.values[s.key], text: pt.exact[s.key] }))}
                      />
                    </div>
                  ))}
                </div>
              </ChartFrame>
            )}
          </div>
        );
      })}
    </div>
  );
}

/** Cited passages from Lumiant's definitions (knowledge search). Product text, never tenant figures. */
function SourcesView({ block }: { block: SourcesBlock }) {
  return (
    <div className="rise" data-testid="answer-sources">
      <p className="mb-1.5 flex items-center gap-1.5 text-dense font-medium text-ink-2">
        <BookOpen className="size-3.5 text-accent" aria-hidden />
        {block.title}
      </p>
      <ol className="space-y-1.5">
        {block.items.map((s, i) => (
          <li key={s.id}>
            <details className="group rounded-control border border-line bg-surface-2/60 open:bg-surface-2" open={i === 0}>
              <summary className="flex cursor-pointer list-none items-center gap-2 px-2.5 py-1.5 text-xs text-ink-2 hover:text-ink">
                <span className="grid size-4 shrink-0 place-items-center rounded-full border border-line-strong text-caption font-semibold text-ink-2">{i + 1}</span>
                <span className="min-w-0 truncate font-medium text-ink">{s.heading}</span>
                <span className="ml-auto shrink-0 text-ink-3">{s.source}</span>
              </summary>
              <p className="px-2.5 pb-2 text-xs leading-relaxed text-ink-2">{s.text}</p>
            </details>
          </li>
        ))}
      </ol>
    </div>
  );
}

export function BlockView({ block, compact }: { block: Block; compact?: boolean }) {
  switch (block.type) {
    case "table":
      return <TableView block={block} compact={compact} />;
    case "bar":
      return <BarView block={block} />;
    case "chart":
      return <ChartView block={block} compact={compact} />;
    case "sources":
      return <SourcesView block={block} />;
    default:
      // A block type this build does not know (a newer API): show nothing rather than guess its shape.
      return null;
  }
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
            {s.detail && <span className="text-ink-3"> · {s.detail}</span>}
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
          <IconButton size="sm" onClick={() => send.mutate("up")} aria-label="Helpful"><ThumbsUp size={14} /></IconButton>
          <IconButton size="sm" onClick={() => send.mutate("down")} aria-label="Not helpful"><ThumbsDown size={14} /></IconButton>
        </>
      )}
    </span>
  );
}

/** The question a clarification choice asks next; a choice without an item asks its own label. */
function choiceQuestion(c: Choice) {
  if (!c.item_id) return c.label;
  return c.warehouse_id ? `compare cost of item ${c.item_id} in warehouse ${c.warehouse_id}` : `how much stock of item ${c.item_id}`;
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
  const uid = useId();
  return (
    <div className="answer-in space-y-3" data-testid={testId}>
      {r.notice && (
        <p role="note" className="flex items-start gap-1.5 rounded-control border border-line bg-surface-2/60 px-2.5 py-1.5 text-xs leading-relaxed text-ink-2" data-testid="answer-notice">
          <Info size={13} className="mt-0.5 shrink-0 text-ink-3" aria-hidden />
          <span className="min-w-0">{r.notice}</span>
        </p>
      )}
      <p dir="auto" className="text-sm leading-relaxed text-ink">{r.answer}</p>
      {!r.grounding.passed && (
        <p role="alert" className="flex items-start gap-1.5 text-xs text-signal" data-testid="grounding-failed">
          <TriangleAlert size={13} className="mt-px shrink-0" aria-hidden />
          {r.grounding.source === "blocked"
            ? `${r.mode === "rules" ? "The answer" : "The AI answer"} was withheld because its figures could not be traced to your data. The tables below are the query results themselves.`
            : "Some figures in this answer could not be traced to the results. Check them against the table and source."}
        </p>
      )}
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
      {r.choices.length > 0 &&
        (r.kind === "clarify" ? (
          <div role="group" aria-labelledby={`${uid}-clarify`} className="rounded-control border border-accent/30 bg-accent-soft p-3" data-testid="answer-clarify">
            <p id={`${uid}-clarify`} className="mb-2 flex items-center gap-1.5 text-xs font-medium text-ink">
              <MessageCircleQuestionMark size={14} className="shrink-0 text-accent" aria-hidden />
              Which one did you mean?
            </p>
            <div className={clsx("grid gap-2", !compact && "sm:grid-cols-2")}>
              {r.choices.map((c, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => onAsk(choiceQuestion(c))}
                  className="rounded-control border border-line-strong bg-surface px-3 py-2 text-left text-sm font-medium text-ink shadow-e1 transition-colors hover:border-accent/50 hover:text-accent"
                >
                  {c.label}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div role="group" className="flex flex-wrap gap-2" aria-label="Choose one">
            {r.choices.map((c, i) => (
              <button
                key={i}
                type="button"
                onClick={() => onAsk(choiceQuestion(c))}
                className="rounded-control border border-line-strong bg-surface px-2.5 py-1.5 text-left text-xs transition-colors hover:border-control-line hover:bg-surface-2"
              >
                {c.label}
              </button>
            ))}
          </div>
        ))}
      {r.follow_ups.length > 0 &&
        (r.kind === "unsupported" ? (
          <section aria-labelledby={`${uid}-can`} className="rounded-control border border-line bg-surface-2/60 p-3" data-testid="answer-unsupported">
            <p id={`${uid}-can`} className="mb-2 flex items-center gap-1.5 text-xs font-medium text-ink">
              <Compass size={14} className="shrink-0 text-ink-2" aria-hidden />
              Here is what I can answer
            </p>
            <div className="flex flex-wrap gap-2">
              {r.follow_ups.map((f) => (
                <Chip key={f} size="sm" onClick={() => onAsk(f)}>
                  {f}
                </Chip>
              ))}
            </div>
          </section>
        ) : (
          <div className="flex flex-wrap gap-2">
            {r.follow_ups.map((f) => (
              <Chip key={f} size="sm" onClick={() => onAsk(f)}>
                {f}
              </Chip>
            ))}
          </div>
        ))}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-line pt-2 text-xs text-ink-3">
        <span title={r.mode === "rules" ? "Built-in question matching; no data left this system" : "External AI chose the analysis and worded the answer from the results"}>
          {MODE_LABEL[r.mode] ?? r.mode}
        </span>
        {r.grounding.passed && r.grounding.source === "model" && <span className="text-ok">numbers checked</span>}
        {r.tool_calls.length > 0 && <span className="code">used: {r.tool_calls.map((c) => c.name).join(", ")}</span>}
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
