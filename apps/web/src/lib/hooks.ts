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

export const useRisk = (kind: RiskKind, params: Record<string, string | number>) =>
  useQuery({
    queryKey: ["risk", kind, params],
    queryFn: () => api.get<Envelope>(`/api/analyses/${kind}`, params),
    placeholderData: keepPreviousData,
  });

export const useDataQuality = () =>
  useQuery({ queryKey: ["data-quality"], queryFn: () => api.get<DataQuality>("/api/analyses/data-quality") });

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
    retry: false,
  });
