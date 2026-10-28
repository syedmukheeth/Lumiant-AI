import { api, ApiError, type Provenance, type ResultWarning, type Row, toApiError } from "@/lib/api";

/** What the assistant can be pointed at (mirrors services/api/src/lumiant/agent/context.py). */
export type SelectionKind =
  | "warehouse"
  | "location"
  | "item"
  | "item_group"
  | "stage"
  | "abc"
  | "stock_status"
  | "metric"
  | "insight";

export type Selection = { kind: SelectionKind; id: string; label?: string };

export type ChatContext = {
  page?: string;
  widget?: string;
  filters?: { warehouse_id?: string; item_group?: string; stage?: string; stock_status?: string };
  selections?: Selection[];
};

export type HistoryTurn = { question: string; tool?: string; args?: Record<string, unknown> };

export type ColumnKind = "text" | "qty" | "money" | "int" | "date" | "pct";
export type TableBlock = { type: "table"; title: string; columns: { key: string; label: string; kind: ColumnKind }[]; rows: Row[] };
export type BarBlock = { type: "bar"; title: string; label_key: string; value_key: string; kind: "money" | "qty"; unit_key: string; rows: Row[] };
export type Block = TableBlock | BarBlock;
export type Choice = { label: string; item_id?: string; warehouse_id?: string };

export type Step = {
  type: "step";
  id: string;
  label: string;
  status: "running" | "done" | "failed";
  detail?: string;
  rows?: number;
  ms?: number;
  tool?: string;
  mode?: string;
};

export type ChatAnswer = {
  mode: "rules" | "anthropic" | "gemini";
  notice: string | null;
  kind: "tools" | "clarify" | "unsupported";
  answer: string;
  blocks: Block[];
  tool_calls: { name: string; args: Record<string, unknown> }[];
  provenance: Provenance[];
  warnings: ResultWarning[];
  follow_ups: string[];
  choices: Choice[];
  grounding: { passed: boolean; source: string; note?: string };
  steps?: Step[];
  elapsed_ms?: number;
  request_id?: string | null;
};

export type StreamEvent =
  | Step
  | { type: "block"; step: string; block: Block }
  | { type: "answer"; answer: ChatAnswer }
  | { type: "error"; code: string; message: string; request_id?: string | null };

export type ChatBody = { message: string; context?: ChatContext; history?: HistoryTurn[] };

const MAX_ID = 64;
const MAX_LABEL = 120;
// Printable only: the API refuses control characters in ids and labels.
const clean = (value: string, max: number) => value.replace(/[\u0000-\u001f\u007f]/g, " ").slice(0, max);

/** Trim a selection to what the API accepts (ids ≤ 64, labels ≤ 120, printable). */
export function toWire(sel: Selection): Selection {
  return { kind: sel.kind, id: clean(sel.id, MAX_ID), ...(sel.label ? { label: clean(sel.label, MAX_LABEL) } : {}) };
}

/** Split an SSE buffer into complete `data:` payloads; returns the parsed events and the unfinished rest. */
export function parseSse(buffer: string): { events: StreamEvent[]; rest: string } {
  const events: StreamEvent[] = [];
  let rest = buffer.replace(/\r\n/g, "\n");
  let cut = rest.indexOf("\n\n");
  while (cut >= 0) {
    const chunk = rest.slice(0, cut);
    rest = rest.slice(cut + 2);
    const data = chunk
      .split("\n")
      .filter((l) => l.startsWith("data:"))
      .map((l) => l.slice(5).trimStart())
      .join("\n");
    if (data) events.push(JSON.parse(data) as StreamEvent);
    cut = rest.indexOf("\n\n");
  }
  return { events, rest };
}

/**
 * Ask the agent and receive its steps as they happen (server-sent events). Falls back to the plain endpoint when the
 * browser or a proxy cannot stream; the final answer is the same either way.
 */
export async function streamChat(body: ChatBody, onEvent: (event: StreamEvent) => void): Promise<ChatAnswer> {
  let res: Response;
  try {
    res = await fetch("/api/agent/chat/stream", {
      method: "POST",
      credentials: "same-origin",
      headers: { Accept: "text/event-stream", "Content-Type": "application/json", "X-Requested-With": "lumiant" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "network_error", "The service could not be reached. Check that the API is running.");
  }
  if (!res.ok) throw await toApiError(res);
  if (!res.body) return api.post<ChatAnswer>("/api/agent/chat", body);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let answer: ChatAnswer | null = null;
  for (;;) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const parsed = parseSse(done ? `${buffer}\n\n` : buffer);
    buffer = parsed.rest;
    for (const event of parsed.events) {
      if (event.type === "error") throw new ApiError(500, event.code, event.message, event.request_id ?? null);
      if (event.type === "answer") answer = event.answer;
      onEvent(event);
    }
    if (done) break;
  }
  if (!answer) throw new ApiError(0, "stream_incomplete", "The answer was interrupted. Please ask again.");
  return answer;
}

/** History the API accepts: the question and the first tool that answered it, never result data. */
export function toHistory(turns: { question: string; answer?: ChatAnswer }[]): HistoryTurn[] {
  return turns
    .filter((t) => t.answer)
    .slice(-6)
    .map((t) => {
      const call = t.answer?.tool_calls[0];
      return call ? { question: t.question.slice(0, 500), tool: call.name, args: call.args } : { question: t.question.slice(0, 500) };
    });
}
