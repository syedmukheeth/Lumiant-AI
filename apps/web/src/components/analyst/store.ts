"use client";

import { useSyncExternalStore } from "react";

import { ApiError } from "@/lib/api";
import {
  type Block,
  type ChatAnswer,
  type ChatContext,
  type Selection,
  type Step,
  streamChat,
  toHistory,
  toWire,
} from "@/lib/agent";

/**
 * The Analyst: one conversation that follows the user across pages, fed by whatever they point at (ADR-0010).
 *
 * A tiny external store (no provider needed): the shell, the dock, the lens and every Analyzable element read and
 * write the same state. Pinned answers are kept per browser (localStorage) — a convenience, not a record.
 */
export type Turn = {
  id: number;
  question: string;
  selections: Selection[];
  steps: Step[];
  blocks: Block[];
  answer?: ChatAnswer;
  error?: string;
};

export type Pin = { id: string; question: string; answer: string; at: string; selections: Selection[] };

type State = {
  open: boolean;
  lens: boolean;
  selections: Selection[];
  turns: Turn[];
  busy: boolean;
  board: Pin[];
};

const MAX_SELECTIONS = 5;
const BOARD_KEY = "lumiant-analyst-board";
const listeners = new Set<() => void>();
let nextId = 1;

function loadBoard(): Pin[] {
  try {
    const raw = typeof window === "undefined" ? null : window.localStorage.getItem(BOARD_KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? (parsed as Pin[]).slice(0, 50) : [];
  } catch {
    return [];
  }
}

let state: State = { open: false, lens: false, selections: [], turns: [], busy: false, board: [] };
let boardLoaded = false;
const SERVER: State = state;

function set(patch: Partial<State> | ((s: State) => Partial<State>)) {
  state = { ...state, ...(typeof patch === "function" ? patch(state) : patch) };
  if (typeof document !== "undefined") {
    const root = document.documentElement;
    root.toggleAttribute("data-lens", state.lens);
    root.dataset.dock = state.open ? "open" : "closed";
  }
  listeners.forEach((l) => l());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  if (!boardLoaded) {
    boardLoaded = true;
    queueMicrotask(() => set({ board: loadBoard() }));
  }
  return () => listeners.delete(listener);
}

export function useAnalyst(): State {
  return useSyncExternalStore(
    subscribe,
    () => state,
    () => SERVER,
  );
}

export const sameSelection = (a: Selection, b: Selection) => a.kind === b.kind && a.id === b.id;

// ------------------------------------------------------------------------------------------------ actions
export function openDock(open = true) {
  set({ open });
}

export function toggleDock() {
  set((s) => ({ open: !s.open }));
}

export function setLens(lens: boolean) {
  set({ lens });
}

export function toggleLens() {
  set((s) => ({ lens: !s.lens }));
}

export function removeSelection(sel: Selection) {
  set((s) => ({ selections: s.selections.filter((x) => !sameSelection(x, sel)) }));
}

export function clearSelections() {
  set({ selections: [] });
}

export function clearConversation() {
  set({ turns: [] });
}

/** Point the Analyst at something. `additive` keeps earlier selections (compare); `ask` asks right away. */
export function analyze(sel: Selection, opts: { additive?: boolean; ask?: string } = {}) {
  const wire = toWire(sel);
  set((s) => {
    const kept = opts.additive ? s.selections.filter((x) => !sameSelection(x, wire)) : [];
    return { open: true, selections: [...kept, wire].slice(-MAX_SELECTIONS) };
  });
  if (opts.ask) void ask(opts.ask);
}

/** The page the user is on and the explorer-style filters in its URL. */
function screenContext(): ChatContext {
  if (typeof window === "undefined") return {};
  const page = window.location.pathname.split("/").filter(Boolean)[0]?.toLowerCase();
  const params = new URLSearchParams(window.location.search);
  const filters: NonNullable<ChatContext["filters"]> = {};
  const map: [string, keyof NonNullable<ChatContext["filters"]>][] = [
    ["warehouse", "warehouse_id"],
    ["item_group", "item_group"],
    ["stage", "stage"],
    ["status", "stock_status"],
  ];
  for (const [param, key] of map) {
    const v = params.get(param);
    if (v) filters[key] = v.slice(0, 64);
  }
  return { ...(page && /^[a-z-]{1,24}$/.test(page) ? { page } : {}), filters };
}

function updateTurn(id: number, patch: (t: Turn) => Partial<Turn>) {
  set((s) => ({ turns: s.turns.map((t) => (t.id === id ? { ...t, ...patch(t) } : t)) }));
}

export async function ask(question: string): Promise<void> {
  const q = question.trim().slice(0, 500);
  if (q.length < 2 || state.busy) return;
  const id = nextId++;
  const selections = state.selections;
  const history = toHistory(state.turns);
  set((s) => ({ open: true, busy: true, turns: [...s.turns, { id, question: q, selections, steps: [], blocks: [] }] }));
  try {
    const answer = await streamChat(
      { message: q, context: { ...screenContext(), selections }, history },
      (event) => {
        if (event.type === "step") {
          updateTurn(id, (t) => ({ steps: [...t.steps.filter((x) => x.id !== event.id), event] }));
        } else if (event.type === "block") {
          updateTurn(id, (t) => ({ blocks: [...t.blocks, event.block] }));
        }
      },
    );
    updateTurn(id, () => ({ answer, steps: answer.steps ?? state.turns.find((t) => t.id === id)?.steps ?? [] }));
  } catch (error) {
    const message =
      error instanceof ApiError
        ? `${error.message}${error.requestId ? ` (ref ${error.requestId.slice(0, 12)})` : ""}`
        : "Something went wrong.";
    updateTurn(id, () => ({ error: message }));
  } finally {
    set({ busy: false });
  }
}

function saveBoard(board: Pin[]) {
  try {
    window.localStorage.setItem(BOARD_KEY, JSON.stringify(board));
  } catch {
    // private window or blocked storage: the board just isn't remembered
  }
}

export function togglePin(turn: Turn) {
  if (!turn.answer) return;
  const pinId = `${turn.id}:${turn.question}`;
  set((s) => {
    const exists = s.board.some((p) => p.id === pinId);
    const board = exists
      ? s.board.filter((p) => p.id !== pinId)
      : [
          { id: pinId, question: turn.question, answer: turn.answer?.answer ?? "", at: new Date().toISOString(), selections: turn.selections },
          ...s.board,
        ].slice(0, 50);
    saveBoard(board);
    return { board };
  });
}

export function unpin(pinId: string) {
  set((s) => {
    const board = s.board.filter((p) => p.id !== pinId);
    saveBoard(board);
    return { board };
  });
}

/** Questions that make sense for what is selected (shown as one-tap chips in the dock). */
export function suggestionsFor(selections: Selection[], canCost: boolean): string[] {
  if (selections.length >= 2) {
    const kinds = new Set(selections.map((s) => s.kind));
    return kinds.size === 1 ? ["Compare these", "What is the difference between these?"] : ["Explain these"];
  }
  const sel = selections[0];
  if (!sel) return [];
  switch (sel.kind) {
    case "warehouse":
    case "location":
      return canCost
        ? ["Why is this so high?", "Which items drive the value here?", "What about quantity?"]
        : ["What is stored here?", "Break this down by item group"];
    case "item_group":
    case "stage":
    case "stock_status":
      return ["Explain this", "Where is this held?", ...(canCost ? ["Which items drive the value here?"] : [])];
    case "item":
      return ["Where is this held?", "How much of this is in stock?"];
    case "metric":
      return ["Break this down", ...(canCost ? ["Which items make up most of the value?"] : [])];
    case "insight":
      return ["Explain this", "What should I look at today?"];
    default:
      return ["Explain this"];
  }
}
