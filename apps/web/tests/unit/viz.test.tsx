import { render, screen, within } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import { BlockView } from "@/components/analyst/answer-view";
import { Gauge } from "@/components/viz/gauge";
import { HeatCalendar } from "@/components/viz/heat-calendar";
import { DeltaChip, KpiCard } from "@/components/viz/kpi-card";
import { ChartFrame } from "@/components/viz/shared";
import { Sparkline } from "@/components/viz/sparkline";
import { Timeline } from "@/components/viz/timeline";

describe("ChartFrame", () => {
  it("gives every chart an accessible label and a hidden data table with the exact values", () => {
    render(
      <ChartFrame label="Value by warehouse" table={{ columns: ["Warehouse", "Value"], rows: [["3100", "USD 1,204.50"]] }}>
        <svg />
      </ChartFrame>,
    );
    expect(screen.getByRole("img", { name: "Value by warehouse" })).toBeInTheDocument();
    const table = screen.getByRole("table", { name: "Value by warehouse" });
    expect(within(table).getByText("USD 1,204.50")).toBeInTheDocument();
  });
});

describe("Sparkline", () => {
  it("draws a labelled trend and nothing for fewer than two points", () => {
    const { container, rerender } = render(<Sparkline values={[1, 3, 2]} label="Trend" />);
    expect(screen.getByRole("img", { name: "Trend" })).toBeInTheDocument();
    expect(container.querySelectorAll("path")).toHaveLength(2);
    rerender(<Sparkline values={[1]} label="Trend" />);
    expect(screen.queryByRole("img", { name: "Trend" })).toBeNull();
  });
});

describe("DeltaChip / KpiCard", () => {
  it("states the direction in words, not only in colour", () => {
    render(<DeltaChip direction="up" text="4.2%" goodWhen="down" />);
    expect(screen.getByText("up")).toHaveClass("sr-only");
    expect(screen.getByText("4.2%").closest("span[class*='critical']")).not.toBeNull();
  });

  it("prints the exact figure it is given", () => {
    render(<KpiCard label="Inventory value" value="USD 2,767,451.83" trend={[1, 2, 3]} />);
    expect(screen.getByText("USD 2,767,451.83")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Inventory value: trend over the last 3 periods/ })).toBeInTheDocument();
  });
});

describe("Gauge", () => {
  it("reads the score and its state together", () => {
    render(<Gauge value={92} exact="92" label="Data quality score" status="Good" />);
    expect(screen.getByRole("img", { name: "Data quality score: 92 out of 100, Good" })).toBeInTheDocument();
  });
});

describe("HeatCalendar", () => {
  it("shows days without data as neutral, never as zero", () => {
    const { container } = render(
      <HeatCalendar
        label="Expiries"
        days={[
          { date: "2026-12-01", value: 4, exact: "4 lots" },
          { date: "2026-12-03", value: 0, exact: "0 lots" },
        ]}
      />,
    );
    const titles = Array.from(container.querySelectorAll("rect title")).map((t) => t.textContent);
    expect(titles).toContain("2026-12-01: 4 lots");
    expect(titles).toContain("2026-12-02: no data");
  });
});

describe("Timeline", () => {
  it("lists every bar with its dates in the text alternative", () => {
    render(
      <Timeline
        label="Plan"
        from="2026-12-01"
        to="2026-12-31"
        lanes={[{ id: "a", label: "SO-1", bars: [{ label: "PO-9", start: "2026-12-02", end: "2026-12-20", note: "late" }] }]}
      />,
    );
    const table = screen.getByRole("table", { name: "Plan" });
    expect(within(table).getByText("2026-12-20")).toBeInTheDocument();
    expect(within(table).getByText("late")).toBeInTheDocument();
  });
});

describe("Answer sources", () => {
  it("renders cited passages from the knowledge base, numbered", () => {
    render(
      <BlockView
        block={{
          type: "sources",
          title: "From Lumiant's definitions",
          items: [{ id: "a#0", source: "Inventory metrics", heading: "Inventory value", text: "On-hand quantity × valuation price." }],
        }}
      />,
    );
    const block = screen.getByTestId("answer-sources");
    expect(within(block).getByText("Inventory value")).toBeInTheDocument();
    expect(within(block).getByText("1")).toBeInTheDocument();
  });
});

describe("Chart kit tokens", () => {
  it("uses only design tokens for colour (no hex literals in components/viz)", () => {
    for (const file of ["gauge", "heat-calendar", "kpi-card", "pareto-chart", "radar-chart", "risk-matrix", "shared", "sparkline", "stacked-bars", "timeline", "treemap", "trend-area", "waterfall"]) {
      const src = readFileSync(resolve(__dirname, `../../src/components/viz/${file}.tsx`), "utf8");
      expect(src, file).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
    }
  });
});
