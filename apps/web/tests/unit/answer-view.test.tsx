import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AnswerBody, BlockView, ChartView } from "@/components/analyst/answer-view";
import type { Block, ChartBlock, ChatAnswer } from "@/lib/agent";
import { formatMoney, formatQuantity } from "@/lib/format";

/** Text as the DOM matcher sees it (Intl puts a no-break space after the currency code). */
const shown = (s: string) => s.replace(/\s+/g, " ");

const valueTrend: ChartBlock = {
  type: "chart",
  variant: "line",
  title: "Inventory value by month",
  x_key: "period",
  series: [{ key: "value", label: "Month-end value", kind: "money", unit_key: "currency" }],
  rows: [
    { period: "2026-09", value: "1204.50", currency: "USD" },
    // Above 2^53: a float would print …992; the label must come from the API string.
    { period: "2026-10", value: "9007199254740993.00", currency: "USD" },
    { period: "2026-09", value: "880.00", currency: "EUR" },
    { period: "2026-10", value: "910.25", currency: "EUR" },
  ],
};

const stockByWarehouse: ChartBlock = {
  type: "chart",
  variant: "bar",
  title: "Stock by warehouse",
  x_key: "warehouse",
  series: [
    { key: "on_hand", label: "On hand", kind: "qty", unit_key: "uom" },
    { key: "share", label: "Share of items", kind: "pct" },
  ],
  rows: [
    { warehouse: "1100 North", on_hand: "1250", uom: "EA", share: "62.5" },
    { warehouse: "3100 South", on_hand: "40.125", uom: "KG", share: "37.5" },
  ],
};

const answer = (over: Partial<ChatAnswer>): ChatAnswer => ({
  mode: "rules",
  notice: null,
  kind: "tools",
  answer: "An answer.",
  blocks: [],
  tool_calls: [],
  provenance: [],
  warnings: [],
  follow_ups: [],
  choices: [],
  grounding: { passed: true, source: "rules" },
  ...over,
});

function renderAnswer(a: ChatAnswer, onAsk = vi.fn()) {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <AnswerBody answer={a} onAsk={onAsk} turnId={1} testId="answer" />
    </QueryClientProvider>,
  );
  return onAsk;
}

describe("ChartView", () => {
  it("draws a line per currency, never two currencies on one axis, with the exact strings in its table", () => {
    render(<ChartView block={valueTrend} />);
    const usd = screen.getByRole("table", { name: "Inventory value by month, in USD" });
    const eur = screen.getByRole("table", { name: "Inventory value by month, in EUR" });
    expect(screen.getByRole("img", { name: "Inventory value by month, in USD" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Inventory value by month, in EUR" })).toBeInTheDocument();

    expect(within(usd).getByText(shown(formatMoney("1204.50", "USD")))).toBeInTheDocument();
    const huge = within(usd).getByText(shown(formatMoney("9007199254740993.00", "USD")));
    expect(huge.textContent).toMatch(/993\.00$/);
    expect(within(usd).getAllByText("2026-10")).toHaveLength(1);
    expect(within(usd).queryByText(/EUR/)).toBeNull();
    expect(within(eur).getByText(shown(formatMoney("910.25", "EUR")))).toBeInTheDocument();
    expect(within(eur).queryByText(/USD/)).toBeNull();
  });

  it("is shorter in the dock", () => {
    render(<ChartView block={valueTrend} compact />);
    expect(screen.getByRole("img", { name: "Inventory value by month, in USD" })).toHaveStyle({ height: "160px" });
  });

  it("draws bars per unit and prints the exact strings, visibly and in the hidden table", () => {
    render(<ChartView block={stockByWarehouse} />);
    const ea = screen.getByRole("table", { name: "Stock by warehouse, in EA" });
    expect(within(ea).getByText(shown(formatQuantity("1250", "EA")))).toBeInTheDocument();
    expect(within(ea).queryByText(/KG/)).toBeNull();
    const kg = screen.getByRole("table", { name: "Stock by warehouse, in KG" });
    expect(within(kg).getByText(shown(formatQuantity("40.125", "KG")))).toBeInTheDocument();
    const pct = screen.getByRole("table", { name: "Stock by warehouse, in percent" });
    expect(within(pct).getByText("62.5%")).toBeInTheDocument();
    // Visible bar labels carry the same strings as the table (once on screen, once for screen readers).
    expect(screen.getAllByText("62.5%")).toHaveLength(2);
    expect(screen.getAllByText("1100 North").length).toBeGreaterThanOrEqual(2);
  });

  it("is dispatched by BlockView", () => {
    render(<BlockView block={stockByWarehouse} />);
    expect(screen.getByTestId("answer-chart")).toBeInTheDocument();
  });
});

describe("BlockView", () => {
  it("renders nothing for a block type it does not know", () => {
    const { container } = render(<BlockView block={{ type: "map", title: "Stock on a map", rows: [] } as unknown as Block} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("AnswerBody kinds", () => {
  it("shows an unsupported answer's follow-ups in a 'Here is what I can answer' callout", () => {
    const onAsk = renderAnswer(answer({ kind: "unsupported", answer: "I cannot forecast demand yet.", follow_ups: ["Stock by warehouse", "Slow movers"] }));
    const callout = screen.getByRole("region", { name: "Here is what I can answer" });
    fireEvent.click(within(callout).getByRole("button", { name: "Slow movers" }));
    expect(onAsk).toHaveBeenCalledWith("Slow movers");
  });

  it("keeps plain follow-up chips on a normal answer", () => {
    renderAnswer(answer({ follow_ups: ["Slow movers"] }));
    expect(screen.queryByTestId("answer-unsupported")).toBeNull();
    expect(screen.getByRole("button", { name: "Slow movers" })).toBeInTheDocument();
  });

  it("puts a clarification's choices up front, and a choice without an item asks its label", () => {
    const onAsk = renderAnswer(
      answer({
        kind: "clarify",
        answer: "Which bearing do you mean?",
        choices: [{ label: "Bearing 6204 (BRG-6204)", item_id: "BRG-6204" }, { label: "All bearings" }],
      }),
    );
    const group = screen.getByRole("group", { name: "Which one did you mean?" });
    fireEvent.click(within(group).getByRole("button", { name: "Bearing 6204 (BRG-6204)" }));
    fireEvent.click(within(group).getByRole("button", { name: "All bearings" }));
    expect(onAsk.mock.calls).toEqual([["how much stock of item BRG-6204"], ["All bearings"]]);
  });

  it("styles the notice as a notice", () => {
    renderAnswer(answer({ notice: "External AI is off for this tenant; built-in matching answered." }));
    expect(screen.getByRole("note")).toHaveTextContent("External AI is off for this tenant; built-in matching answered.");
  });
});
