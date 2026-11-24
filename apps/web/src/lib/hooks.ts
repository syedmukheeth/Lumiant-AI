"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useSyncExternalStore } from "react";

import {
  api,
  type AbcResult,
  type CostComparison,
  type DataQuality,
  type DevUser,
  type Envelope,
  type InventoryFilters,
  type Me,
  type MetricInfo,
  type MetricResult,
  type TenantMeta,
  type BomLineView,
  type CommitmentAnalysis,
  type CommitmentAtRisk,
  type DuplicateFinding,
  type ExcessSupply,
  type FulfilmentLine,
  type LifecycleFinding,
  type PlannedOrder,
  type PlanningMeta,
  type SupplierComparisonView,
} from "@/lib/api";

export const useMe = () => useQuery({ queryKey: ["me"], queryFn: () => api.get<Me>("/api/auth/me") });

const noop = () => () => {};

/** False during server render and hydration, true afterwards. */
export const useHydrated = () =>
  useSyncExternalStore(
    noop,
    () => true,
    () => false,
  );

/**
 * The session as seen by page content. The shell fetches the same query and may finish before a page
 * segment hydrates; reading it only after hydration keeps server and client markup identical.
 */
export function usePageMe(): Me | undefined {
  const me = useMe();
  return useHydrated() ? me.data : undefined;
}

export const useTenantMeta = (enabled = true) =>
  useQuery({ queryKey: ["meta"], queryFn: () => api.get<TenantMeta>("/api/meta/tenant"), enabled });

export const useMetricList = () =>
  useQuery({ queryKey: ["metrics"], queryFn: () => api.get<{ metrics: MetricInfo[] }>("/api/metrics") });

export const useMetric = (id: string, enabled = true) =>
  useQuery({ queryKey: ["metric", id], queryFn: () => api.get<MetricResult>(`/api/metrics/${id}`), enabled });

export const useDevUsers = () =>
  useQuery({
    queryKey: ["dev-users"],
    queryFn: () => api.get<{ users: DevUser[]; notice: string }>("/api/auth/dev-users"),
  });

export const useInventoryFilters = () =>
  useQuery({ queryKey: ["inventory-filters"], queryFn: () => api.get<InventoryFilters>("/api/inventory/filters") });

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

export const useBalances = (query: BalanceQuery) =>
  useQuery({
    queryKey: ["balances", query],
    queryFn: () => api.get<Envelope>("/api/inventory/balances", query),
    placeholderData: keepPreviousData,
  });

export const useBelowReorder = (query: { offset: number; limit: number }) =>
  useQuery({
    queryKey: ["below-reorder", query],
    queryFn: () => api.get<Envelope>("/api/analyses/below-reorder", query),
    placeholderData: keepPreviousData,
  });

export type RiskKind = "excess-stock" | "dormant" | "expiring-lots";

export const useRisk = (kind: RiskKind, params: Record<string, string | number>, enabled = true) =>
  useQuery({
    queryKey: ["risk", kind, params],
    queryFn: () => api.get<Envelope>(`/api/analyses/${kind}`, params),
    placeholderData: keepPreviousData,
    enabled,
  });

export const useDataQuality = (enabled = true) =>
  useQuery({ queryKey: ["data-quality"], queryFn: () => api.get<DataQuality>("/api/analyses/data-quality"), enabled });

export const useCostComparison = (item: string, warehouse: string) =>
  useQuery({
    queryKey: ["cost", item, warehouse],
    queryFn: () => api.get<CostComparison>("/api/analyses/cost-comparison", { item_id: item, warehouse_id: warehouse }),
    enabled: item.length > 0 && warehouse.length > 0,
    retry: false,
  });

export const useAbc = (a: string, b: string, currency: string) =>
  useQuery({
    queryKey: ["abc", a, b, currency],
    queryFn: () => api.get<AbcResult>("/api/analyses/abc", { a, b, currency: currency || undefined }),
    // The user picks the cutoffs and presses Run; asking before that only earns a 422 for missing parameters.
    enabled: a.length > 0 && b.length > 0,
    retry: false,
  });

// ---------------------------------------------------------------------------------------- planning
export const useFulfilment = (enabled = true) =>
  useQuery({
    queryKey: ["planning", "fulfilment"],
    queryFn: () => api.get<PlanningMeta & { lines: FulfilmentLine[] }>("/api/planning/fulfilment"),
    enabled,
  });

export const useMaterialPlan = (enabled = true) =>
  useQuery({
    queryKey: ["planning", "material-plan"],
    queryFn: () => api.get<PlanningMeta & { planned_orders: PlannedOrder[]; excess_supply: ExcessSupply[] }>("/api/planning/material-plan"),
    enabled,
  });

export const useBomExplosion = (item: string, qty: string) =>
  useQuery({
    queryKey: ["planning", "bom", item, qty],
    queryFn: () =>
      api.get<PlanningMeta & { item_id: string; quantity: string; lines: BomLineView[]; totals: Record<string, string> }>(
        "/api/planning/bom",
        { item, qty },
      ),
    enabled: item.trim().length > 0 && Number(qty) > 0,
    retry: false,
  });

export type SupplierQuery = { item: string; qty: string; need_date?: string; policy: string };

export const useSupplierComparison = (q: SupplierQuery | null) =>
  useQuery({
    queryKey: ["planning", "suppliers", q],
    queryFn: () => api.get<SupplierComparisonView>("/api/planning/suppliers", q ?? undefined),
    enabled: !!q,
    retry: false,
  });

export const useCommitments = () =>
  useQuery({
    queryKey: ["planning", "commitments"],
    queryFn: () => api.get<PlanningMeta & { at_risk: CommitmentAtRisk[] }>("/api/planning/commitments"),
    retry: false,
  });

export const useCommitment = (order: string | null) =>
  useQuery({
    queryKey: ["planning", "commitment", order],
    queryFn: () => api.get<CommitmentAnalysis>("/api/planning/commitment", { order: order ?? "" }),
    enabled: !!order,
    retry: false,
  });

export const useDuplicates = (enabled = true) =>
  useQuery({
    queryKey: ["planning", "duplicates"],
    queryFn: () => api.get<PlanningMeta & { findings: DuplicateFinding[] }>("/api/planning/duplicates"),
    enabled,
  });

export const useLifecycle = (enabled = true) =>
  useQuery({
    queryKey: ["planning", "lifecycle"],
    queryFn: () => api.get<PlanningMeta & { findings: LifecycleFinding[] }>("/api/planning/lifecycle"),
    enabled,
    retry: false,
  });
