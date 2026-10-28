import { act, fireEvent, render, renderHook, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Analyzable, readSelection } from "@/components/analyst/analyzable";
import { clearSelections, openDock, setLens, suggestionsFor, useAnalyst } from "@/components/analyst/store";
import { useShortcuts } from "@/components/shell/use-shortcuts";
import { parseSse, toHistory, toWire } from "@/lib/agent";

afterEach(() => {
  act(() => {
    clearSelections();
    openDock(false);
    setLens(false);
  });
});

describe("parseSse", () => {
  it("returns complete events and keeps the unfinished rest", () => {
    const first = 'event: step\ndata: {"type":"step","id":"understand","label":"x","status":"running"}\n\n';
    const { events, rest } = parseSse(`${first}event: answer\ndata: {"type":"ans`);
    expect(events).toEqual([{ type: "step", id: "understand", label: "x", status: "running" }]);
    expect(rest).toBe('event: answer\ndata: {"type":"ans');
  });

  it("handles CRLF line endings", () => {
    const { events } = parseSse('data: {"type":"block","step":"tool:0","block":{"type":"table"}}\r\n\r\n');
    expect(events[0]).toMatchObject({ type: "block", step: "tool:0" });
  });
});

describe("toWire / toHistory", () => {
  it("trims selections to what the API accepts", () => {
    const sel = toWire({ kind: "item", id: `A\u0000${"9".repeat(80)}`, label: `x\ny${"z".repeat(200)}` });
    expect(sel.id).toHaveLength(64);
    expect(sel.id).not.toMatch(/[\u0000-\u001f]/);
    expect(sel.label).toHaveLength(120);
    expect(sel.label).not.toContain("\n");
  });

  it("sends questions and tools, never result data", () => {
    const answer = { tool_calls: [{ name: "stock_by", args: { dimension: "warehouse" } }], answer: "USD 123" } as never;
    expect(toHistory([{ question: "value by warehouse", answer }, { question: "pending" }])).toEqual([
      { question: "value by warehouse", tool: "stock_by", args: { dimension: "warehouse" } },
    ]);
  });
});

describe("Analyzable", () => {
  it("right-click selects the element for the Analyst and opens the dock", () => {
    const { result } = renderHook(() => useAnalyst());
    render(
      <Analyzable sel={{ kind: "warehouse", id: "1100", label: "North" }}>
        <p>North plant</p>
      </Analyzable>,
    );
    fireEvent.contextMenu(screen.getByText("North plant"));
    expect(result.current.open).toBe(true);
    expect(result.current.selections).toEqual([{ kind: "warehouse", id: "1100", label: "North" }]);
    expect(screen.getByText("North plant").closest("[data-analyzable]")?.hasAttribute("data-selected")).toBe(true);
  });

  it("Shift on the spark button adds to a comparison of up to five", () => {
    const { result } = renderHook(() => useAnalyst());
    render(
      <>
        {["1", "2", "3", "4", "5", "6"].map((id) => (
          <Analyzable key={id} sel={{ kind: "warehouse", id, label: `W${id}` }}>
            <p>W{id}</p>
          </Analyzable>
        ))}
      </>,
    );
    for (const id of ["1", "2", "3", "4", "5", "6"]) fireEvent.click(screen.getByRole("button", { name: `Analyze W${id}` }), { shiftKey: true });
    expect(result.current.selections.map((s) => s.id)).toEqual(["2", "3", "4", "5", "6"]);
  });

  it("readSelection ignores malformed attributes", () => {
    const el = document.createElement("div");
    el.setAttribute("data-analyzable", "");
    el.setAttribute("data-sel", "{not json");
    expect(readSelection(el)).toBeNull();
    el.setAttribute("data-sel", JSON.stringify({ kind: "item", id: "X1" }));
    expect(readSelection(el)).toEqual({ kind: "item", id: "X1" });
  });
});

describe("Analyst shortcuts and suggestions", () => {
  it("Ctrl+J toggles the dock and L toggles the lens, but not while typing", () => {
    const onDock = vi.fn();
    const onLens = vi.fn();
    renderHook(() => useShortcuts({ nav: [], onPalette: vi.fn(), onNavigate: vi.fn(), onToggleRail: vi.fn(), onDock, onLens }));
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "j", ctrlKey: true, bubbles: true, cancelable: true }));
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "l", bubbles: true, cancelable: true }));
    const input = document.createElement("input");
    document.body.append(input);
    input.dispatchEvent(new KeyboardEvent("keydown", { key: "l", bubbles: true, cancelable: true }));
    input.remove();
    expect(onDock).toHaveBeenCalledTimes(1);
    expect(onLens).toHaveBeenCalledTimes(1);
  });

  it("never suggests value questions to a role without cost access", () => {
    const qs = suggestionsFor([{ kind: "warehouse", id: "1100" }], false).join(" ");
    expect(qs).not.toMatch(/value/i);
    expect(suggestionsFor([{ kind: "warehouse", id: "1" }, { kind: "warehouse", id: "2" }], true)).toContain("Compare these");
  });
});
