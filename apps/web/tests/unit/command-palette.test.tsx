import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CommandPalette, distinctMaterials, paletteFilter } from "@/components/shell/command-palette";
import { navFor } from "@/components/shell/nav";

function setup(props: Partial<React.ComponentProps<typeof CommandPalette>> = {}) {
  const onNavigate = vi.fn();
  const onAsk = vi.fn();
  const onOpenChange = vi.fn();
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <CommandPalette
        open
        onOpenChange={onOpenChange}
        nav={navFor(["overview", "inventory", "risks", "assistant"])}
        canSearchMaterials
        canAsk
        onNavigate={onNavigate}
        onAsk={onAsk}
        onSignOut={vi.fn()}
        {...props}
      />
    </QueryClientProvider>,
  );
  return { onNavigate, onAsk, onOpenChange, input: screen.getByRole("combobox") };
}

afterEach(() => vi.unstubAllGlobals());

describe("CommandPalette", () => {
  it("offers only the pages of the granted sections", () => {
    setup();
    const pages = within(screen.getByRole("group", { name: "Go to" }));
    for (const name of ["Overview", "Explore", "Inventory", "Risks", "Assistant"]) expect(pages.getByText(name)).toBeInTheDocument();
    for (const name of ["Costs", "Reports", "Admin"]) expect(pages.queryByText(name)).not.toBeInTheDocument();
  });

  it("navigates to a page and closes", () => {
    const { input, onNavigate, onOpenChange } = setup();
    fireEvent.change(input, { target: { value: "risk" } });
    fireEvent.click(screen.getByText("Risks"));
    expect(onOpenChange).toHaveBeenCalledWith(false);
    expect(onNavigate).toHaveBeenCalledWith("/risks");
  });

  it("hands a free-text question to the assistant", () => {
    const { input, onAsk } = setup({ canSearchMaterials: false });
    fireEvent.change(input, { target: { value: "which items are below reorder level" } });
    fireEvent.click(screen.getByText(/Ask:/));
    expect(onAsk).toHaveBeenCalledWith("which items are below reorder level");
  });

  it("offers no question without assistant access", () => {
    const { input } = setup({ canAsk: false, canSearchMaterials: false });
    fireEvent.change(input, { target: { value: "anything at all" } });
    expect(screen.queryByText(/Ask:/)).not.toBeInTheDocument();
  });

  it("finds materials through the permission-scoped stock-line search and opens them in the explorer", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(
        JSON.stringify({
          data: [
            { item_id: "I-1", "item.item_code": "GSK-001", "item.description": "Gasket 40 mm" },
            { item_id: "I-1", "item.item_code": "GSK-001", "item.description": "Gasket 40 mm" },
            { item_id: "I-2", "item.item_code": "GSK-002", "item.description": "Gasket 60 mm" },
          ],
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    const { input, onNavigate } = setup();
    fireEvent.change(input, { target: { value: "gasket" } });
    const first = await screen.findByText("Gasket 40 mm");
    expect(screen.getAllByText(/Gasket \d+ mm/)).toHaveLength(2);
    const url = String((fetchMock.mock.calls[0] as unknown[])[0]);
    expect(url).toContain("/api/inventory/balances");
    expect(url).toContain("q=gasket");
    fireEvent.click(first);
    expect(onNavigate).toHaveBeenCalledWith("/inventory?q=GSK-001");
  });

  it("never searches materials without inventory access", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const { input } = setup({ canSearchMaterials: false });
    fireEvent.change(input, { target: { value: "gasket" } });
    await waitFor(() => expect(screen.getByText(/Ask:/)).toBeInTheDocument());
    await new Promise((r) => setTimeout(r, 300));
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("distinctMaterials", () => {
  it("keeps one entry per item, in API order, capped", () => {
    const rows = ["a", "b", "a", "c", "d"].map((id) => ({ item_id: id, "item.item_code": id.toUpperCase(), "item.description": null }));
    expect(distinctMaterials(rows, 3).map((m) => m.code)).toEqual(["A", "B", "C"]);
  });
});

describe("paletteFilter", () => {
  it("matches word prefixes, not letters scattered across words", () => {
    expect(paletteFilter("Go to Inventory", "inv", ["Analyze"])).toBe(1);
    expect(paletteFilter("Go to Inventory", "go inv")).toBe(1);
    expect(paletteFilter("Sign out", "sign o", ["logout"])).toBe(1);
    // a fuzzy subsequence matcher would take this (v…a…l…v…e across "Inventory Analyze")
    expect(paletteFilter("Go to Inventory", "valve", ["Analyze"])).toBe(0);
    expect(paletteFilter("Go to Risks", "which items are below reorder")).toBe(0);
  });
});
