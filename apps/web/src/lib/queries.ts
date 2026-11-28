import { keepPreviousData, queryOptions } from "@tanstack/react-query";

import type { Feed } from "@/components/overview/insights-feed";
import type { Trend } from "@/components/overview/value-trend";
import type { ReportList } from "@/components/reports/reports-page";
import type { Ageing } from "@/components/risks/ageing-panel";
import {
  api,
  type CommitmentAtRisk,
  type DuplicateFinding,
  type Envelope,
  type FulfilmentLine,
  type InventoryFilters,
  type LifecycleFinding,
  type Me,
  type MetricInfo,
  type MetricResult,
  type PlanningMeta,
  type TenantMeta,
} from "@/lib/api";

/**
 * One definition per request: the hooks, the pages and the navigation prefetch (lib/prefetch.ts) all build their
 * queries here, so a prefetched response lands under exactly the key the page reads.
 */
export type BalanceQuery = {
  warehouse?: string;
  item_group?: string;
  abc?: string;
  stage?: string;
  status?: string;
  q?: string;
  sort: string;
  dir: "asc" | "desc";
  offset: number;
  limit: number;
};

export type RiskKind = "excess-stock" | "dormant" | "expiring-lots";

/** The Overview's below-reorder page: the KPI, the area board and the panel all use this key, so it is fetched once. */
export const OVERVIEW_BELOW_REORDER = { offset: 0, limit: 12 } as const;

/** Inventory's first page with no filters (the explorer's defaults). */
export const INVENTORY_FIRST_PAGE: BalanceQuery = { sort: "item_code", dir: "asc", offset: 0, limit: 50 };

/** Risks: rows per page, and the first tab's request. */
export const RISK_PAGE = 25;

export const queries = {
  me: () => queryOptions({ queryKey: ["me"], queryFn: () => api.get<Me>("/api/auth/me") }),
  meta: () => queryOptions({ queryKey: ["meta"], queryFn: () => api.get<TenantMeta>("/api/meta/tenant") }),
  metricList: () =>
    queryOptions({ queryKey: ["metrics"], queryFn: () => api.get<{ metrics: MetricInfo[] }>("/api/metrics") }),
  metric: (id: string) =>
    queryOptions({ queryKey: ["metric", id], queryFn: () => api.get<MetricResult>(`/api/metrics/${id}`) }),
  insights: () =>
    queryOptions({ queryKey: ["insights"], queryFn: () => api.get<Feed>("/api/insights"), staleTime: 60_000 }),
  valueTrend: () =>
    queryOptions({
      queryKey: ["value-trend", 12],
      queryFn: () => api.get<Trend>("/api/analyses/value-trend", { months: 12 }),
      staleTime: 60_000,
    }),
  inventoryFilters: () =>
    queryOptions({ queryKey: ["inventory-filters"], queryFn: () => api.get<InventoryFilters>("/api/inventory/filters") }),
  balances: (query: BalanceQuery) =>
    queryOptions({
      queryKey: ["balances", query],
      queryFn: () => api.get<Envelope>("/api/inventory/balances", query),
      placeholderData: keepPreviousData,
    }),
  belowReorder: (query: { offset: number; limit: number }) =>
    queryOptions({
      queryKey: ["below-reorder", query],
      queryFn: () => api.get<Envelope>("/api/analyses/below-reorder", query),
      placeholderData: keepPreviousData,
    }),
  risk: (kind: RiskKind, params: Record<string, string | number>) =>
    queryOptions({
      queryKey: ["risk", kind, params],
      queryFn: () => api.get<Envelope>(`/api/analyses/${kind}`, params),
      placeholderData: keepPreviousData,
    }),
  ageing: () => queryOptions({ queryKey: ["ageing"], queryFn: () => api.get<Ageing>("/api/analyses/ageing") }),
  reports: () => queryOptions({ queryKey: ["reports"], queryFn: () => api.get<ReportList>("/api/reports") }),
  agentSuggestions: () =>
    queryOptions({
      queryKey: ["agent-suggestions"],
      queryFn: () => api.get<{ suggestions: string[] }>("/api/agent/suggestions"),
      staleTime: 300_000,
    }),
  fulfilment: () =>
    queryOptions({
      queryKey: ["planning", "fulfilment"],
      queryFn: () => api.get<PlanningMeta & { lines: FulfilmentLine[] }>("/api/planning/fulfilment"),
    }),
  commitments: () =>
    queryOptions({
      queryKey: ["planning", "commitments"],
      queryFn: () => api.get<PlanningMeta & { at_risk: CommitmentAtRisk[] }>("/api/planning/commitments"),
      retry: false,
    }),
  duplicates: () =>
    queryOptions({
      queryKey: ["planning", "duplicates"],
      queryFn: () => api.get<PlanningMeta & { findings: DuplicateFinding[] }>("/api/planning/duplicates"),
    }),
  lifecycle: () =>
    queryOptions({
      queryKey: ["planning", "lifecycle"],
      queryFn: () => api.get<PlanningMeta & { findings: LifecycleFinding[] }>("/api/planning/lifecycle"),
      retry: false,
    }),
};
