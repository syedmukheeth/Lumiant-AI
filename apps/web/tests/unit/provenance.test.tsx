import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ProvenanceButton } from "@/components/data/provenance";
import { SyntheticTape } from "@/components/shell/synthetic-tape";
import type { Provenance } from "@/lib/api";

const base: Provenance = {
  tenant_id: "demo-alpha",
  source_system: "Synthetic DuckDB warehouse",
  synthetic: true,
  dataset: "stock_balance",
  source_objects: ["ZV_STOCK"],
  fields: { stock_value: "ZV_STOCK.LABST * ZV_STOCK.VERPR" },
  filters: {
    user: [{ field: "item.item_group", op: "in", value: ["RUBBER"] }],
    injected: [{ field: "warehouse_id", op: "in", value: ["1100", "1110"], reason: "warehouse_scope" }],
  },
  auto_grouped: ["currency"],
  data_as_of: "2026-10-27T06:42:00+00:00",
  row_count: 3,
  truncated: false,
  executed_at: "2026-10-27T07:00:00+00:00",
  duration_ms: 4.2,
  metric: { id: "inventory_value_by_warehouse", version: 1, status: "draft", rule: "Sum of on-hand × price" },
};

function open(provenance: Provenance) {
  render(<ProvenanceButton provenance={provenance} />);
  fireEvent.click(screen.getByRole("button", { name: /how this was calculated/i }));
}

describe("ProvenanceButton", () => {
  it("shows mapping, user filters and permission-injected scope", () => {
    open(base);
    expect(screen.getByText(/ZV_STOCK.LABST \* ZV_STOCK.VERPR/)).toBeInTheDocument();
    expect(screen.getByText(/item.item_group in RUBBER/)).toBeInTheDocument();
    expect(screen.getByText(/warehouse_id in 1100, 1110/)).toBeInTheDocument();
    expect(screen.getByText(/applied by your permissions/)).toBeInTheDocument();
    expect(screen.getByText(/never summed across/)).toBeInTheDocument();
    expect(screen.getByText(/status: draft/)).toBeInTheDocument();
  });

  it("hides the SQL section unless the API included it", () => {
    open(base);
    expect(screen.queryByText(/show generated SQL/)).not.toBeInTheDocument();
  });

  it("shows SQL only when present (query:view_sql users)", () => {
    open({ ...base, sql: "SELECT 1" });
    expect(screen.getByText(/show generated SQL/)).toBeInTheDocument();
  });

  it("renders nothing without provenance", () => {
    const { container } = render(<ProvenanceButton provenance={undefined} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("SyntheticTape", () => {
  it("labels demo data", () => {
    render(<SyntheticTape />);
    expect(screen.getByTestId("synthetic-badge")).toHaveTextContent(/SYNTHETIC/);
  });
});
