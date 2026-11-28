import type { QueryClient } from "@tanstack/react-query";

import type { Me } from "@/lib/api";
import { INVENTORY_FIRST_PAGE, OVERVIEW_BELOW_REORDER, RISK_PAGE, queries } from "@/lib/queries";

/**
 * What each page asks for first, warmed when the user shows intent (pointer over or focus on its link). The page then
 * opens with its data in the cache instead of a skeleton. Same query definitions as the pages (lib/queries.ts), so
 * nothing is fetched twice; React Query skips a request whose data is still fresh. The API authorizes every one of
 * these requests exactly as when the page sends it.
 */
const ROUTE_DATA: Record<string, (qc: QueryClient, me: Me) => void> = {
  "/overview": (qc, me) => {
    void qc.prefetchQuery(queries.metricList());
    void qc.prefetchQuery(queries.insights());
    void qc.prefetchQuery(queries.belowReorder(OVERVIEW_BELOW_REORDER));
    void qc.prefetchQuery(queries.metric("items_in_stock"));
    void qc.prefetchQuery(queries.metric("stock_lines"));
    if (me.permissions.includes("cost:read")) {
      void qc.prefetchQuery(queries.metric("inventory_value_total"));
      void qc.prefetchQuery(queries.valueTrend());
    }
  },
  "/inventory": (qc) => {
    void qc.prefetchQuery(queries.inventoryFilters());
    void qc.prefetchQuery(queries.balances(INVENTORY_FIRST_PAGE));
  },
  "/risks": (qc) => {
    void qc.prefetchQuery(queries.ageing());
    void qc.prefetchQuery(queries.risk("excess-stock", { limit: RISK_PAGE, offset: 0 }));
  },
  "/costs": (qc) => void qc.prefetchQuery(queries.inventoryFilters()),
  "/assistant": (qc) => void qc.prefetchQuery(queries.agentSuggestions()),
  "/reports": (qc) => void qc.prefetchQuery(queries.reports()),
  "/planning": (qc) => void qc.prefetchQuery(queries.fulfilment()),
  "/commitments": (qc) => void qc.prefetchQuery(queries.commitments()),
  "/master-data": (qc) => void qc.prefetchQuery(queries.duplicates()),
};

export function prefetchRouteData(qc: QueryClient, href: string, me: Me | undefined) {
  if (me) ROUTE_DATA[href]?.(qc, me);
}
