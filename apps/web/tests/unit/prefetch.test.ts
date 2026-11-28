import { QueryClient } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Me } from "@/lib/api";
import { prefetchRouteData } from "@/lib/prefetch";

afterEach(() => vi.unstubAllGlobals());

function requested(me: Partial<Me>, href = "/overview"): string[] {
  const fetchMock = vi.fn().mockResolvedValue(new Response("{}", { status: 200 }));
  vi.stubGlobal("fetch", fetchMock);
  prefetchRouteData(new QueryClient(), href, me as Me);
  return fetchMock.mock.calls.map(([url]) => String(url).split("?")[0]);
}

describe("route data prefetch", () => {
  it("asks for the Overview's figures, risks and values for a role that may see them", () => {
    const urls = requested({ sections: ["overview", "risks"], permissions: ["dashboard:read", "cost:read"] });
    expect(urls).toEqual(
      expect.arrayContaining([
        "/api/metrics",
        "/api/metrics/items_in_stock",
        "/api/analyses/excess-stock",
        "/api/analyses/data-quality",
        "/api/metrics/inventory_value_total",
        "/api/metrics/inventory_value_by_warehouse",
        "/api/analyses/value-trend",
      ]),
    );
  });

  it("never asks for values without cost access, or for risks without the Risks section", () => {
    const urls = requested({ sections: ["overview"], permissions: ["dashboard:read"] });
    expect(urls).toContain("/api/metrics/items_in_stock");
    const values = urls.filter((u) => u.includes("value"));
    const risks = urls.filter((u) => u.startsWith("/api/analyses/") && !u.endsWith("/below-reorder"));
    expect(values).toEqual([]);
    expect(risks).toEqual([]);
  });

  it("does nothing without a session or for an unknown route", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    prefetchRouteData(new QueryClient(), "/overview", undefined);
    prefetchRouteData(new QueryClient(), "/nowhere", { sections: ["overview"], permissions: [] } as unknown as Me);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
