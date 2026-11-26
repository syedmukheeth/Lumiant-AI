import { z } from "zod";

/** Error returned by the API ({error: {code, message, request_id}}) or by the network. */
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly requestId: string | null = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const errorBody = z.object({
  error: z.object({ code: z.string(), message: z.string(), request_id: z.string().nullable().optional() }),
});

export async function toApiError(res: Response): Promise<ApiError> {
  try {
    const parsed = errorBody.safeParse(await res.json());
    if (parsed.success) {
      const e = parsed.data.error;
      return new ApiError(res.status, e.code, e.message, e.request_id ?? null);
    }
  } catch {
    // fall through: non-JSON body (e.g. proxy error page)
  }
  return new ApiError(res.status, "http_error", "The service could not be reached.");
}

type Query = Record<string, string | number | string[] | undefined | null>;

export function buildUrl(path: string, query?: Query): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) value.forEach((v) => params.append(key, v));
    else params.set(key, String(value));
  }
  const qs = params.toString();
  return qs ? `${path}?${qs}` : path;
}

async function request<T>(method: "GET" | "POST" | "DELETE", path: string, opts: { query?: Query; body?: unknown } = {}) {
  let res: Response;
  try {
    res = await fetch(buildUrl(path, opts.query), {
      method,
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        ...(method === "POST" ? { "Content-Type": "application/json" } : {}),
        ...(method !== "GET" ? { "X-Requested-With": "lumiant" } : {}),
      },
      body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
    });
  } catch {
    throw new ApiError(0, "network_error", "The service could not be reached. Check that the API is running.");
  }
  if (!res.ok) throw await toApiError(res);
  return (await res.json()) as T;
}

export const api = {
  get: <T>(path: string, query?: Query) => request<T>("GET", path, { query }),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, { body: body ?? {} }),
  delete: <T>(path: string) => request<T>("DELETE", path),
};

// ---------------------------------------------------------------------------------------- API shapes
export type Me = {
  user: { id: string; display_name: string };
  tenant: { id: string; display_name: string };
  roles: string[];
  permissions: string[];
  scope: { all_warehouses: boolean; warehouses: string[]; departments: string[] };
  sections: ("overview" | "inventory" | "risks" | "costs" | "assistant" | "reports" | "admin" | "planning" | "procurement" | "master_data")[];
  auth_mode: string;
};

export type DataClassification = "synthetic" | "customer" | "customer_extract";

export type TenantMeta = {
  tenant_id: string;
  display_name: string;
  source_system: string;
  synthetic: boolean;
  data_classification: DataClassification;
  data_as_of: string | null;
  stale: boolean;
  stale_after_hours: number;
  warnings: ResultWarning[];
};

export type ResultWarning = { code: string; message: string };

export type FilterDescription = { field: string; op: string; value: unknown; reason?: string } | { any: FilterDescription[] };

export type Provenance = {
  tenant_id: string;
  source_system: string;
  synthetic: boolean;
  data_classification?: DataClassification;
  dataset: string;
  source_objects: string[];
  fields: Record<string, string>;
  filters: { user: FilterDescription[]; injected: FilterDescription[] };
  auto_grouped: string[];
  data_as_of: string | null;
  row_count: number;
  truncated: boolean;
  executed_at: string;
  duration_ms: number;
  metric?: { id: string; version: number; status: string; rule: string };
  rule?: string;
  excluded_lines?: number;
  sql?: string;
};

export type Row = Record<string, string | number | boolean | null>;

export type Envelope<R extends Row = Row> = {
  data: R[];
  columns: { name: string; type: string; kind: string }[];
  provenance: Provenance;
  warnings: ResultWarning[];
  page?: { offset: number; limit: number; total: number };
  summary?: Record<string, string | number | null>;
};

export type MetricInfo = {
  id: string;
  version: number;
  title: string;
  description: string;
  rule: string;
  unit: "currency" | "count";
  chart: "kpi" | "bar";
  status: string;
};

export type MetricResult = Envelope & { metric: MetricInfo };

export type DevUser = {
  username: string;
  display_name: string;
  tenant_id: string;
  tenant_name: string;
  roles: string[];
  data_classification?: DataClassification;
};

export type InventoryFilters = {
  warehouses: { id: string; name: string | null }[];
  item_groups: string[];
  abc_classes: string[];
  stages: string[];
  stock_statuses?: string[];
  /** Lists that hold more values than were returned (each list stops at `limit`). */
  truncated?: string[];
  limit?: number;
};

export type DataQualityCheck = {
  id: string;
  title: string;
  status: "ok" | "issue" | "info" | "not_mapped" | "restricted" | "no_rules";
  count: number | null;
  /** Percentage of the records checked, as an exact decimal string. */
  share?: string | null;
  examples?: { item_id: string; item_code: string; problems: string[] }[];
  checked?: number;
  partial?: boolean;
};

export type DataQuality = {
  checks: DataQualityCheck[];
  total_items: number;
  warnings: ResultWarning[];
  synthetic: boolean;
  data_as_of: string | null;
};

export type CostMethods = {
  moving_weighted_average?: { quantity: string; unit_cost: string | null; value: string };
  fifo?: {
    quantity: string;
    unit_cost: string | null;
    value: string;
    layers: { receipt_date: string; quantity: string; unit_cost: string; source: string }[];
  };
  latest_receipt_cost: { unit_cost: string; date: string; reference: string } | null;
  latest_valid_purchase_price: { unit_price: string; order_date: string; reference: string } | null;
  source_valuation: { quantity: string | null; unit_cost: string | null; value: string | null };
};

export type CostComparison = {
  item_id: string;
  warehouse_id: string;
  currency: string | null;
  uom: string | null;
  movements_used: number;
  methods: CostMethods;
  errors: Record<string, string>;
  reconciliation: {
    status: string;
    difference_unit_cost?: string;
    tolerance?: string;
    quantity_matches?: boolean;
    note?: string;
  };
  lots: { lot_id: string; quantity: string; receipt_date: string | null; unit_cost: string | null }[];
  rules: Record<string, string>;
  status: string;
  warnings: ResultWarning[];
  provenance: Provenance;
};

export type AbcResult = {
  currency: string | null;
  config: { a_cutoff: string; b_cutoff: string; value_definition: string };
  items: { item_id: string; value: string | null; computed: string | null; assigned: string | null; differs: boolean }[];
  item_count: number;
  differences: number;
  matrix: Record<string, Record<string, number>>;
  assigned_available: boolean;
  rule: string;
  provenance: Provenance;
  warnings: ResultWarning[];
};

// ---------------------------------------------------------------------------------------- planning (/api/planning)
/** Every planning result is a recommendation: nothing is ordered, approved, merged or disposed of. */
export type PlanningIssue = { code: string; severity: "info" | "warning" | "blocker"; message: string; item_id: string | null; reference: string | null };

export type PlanningMeta = {
  today: string;
  issues: PlanningIssue[];
  available: Record<string, number>;
  recommendation_only: true;
};

export type FulfilmentLine = {
  key: string;
  item_id: string;
  warehouse_id: string;
  customer_id: string;
  quantity: string;
  due: string;
  from_stock: string;
  from_receipts: string;
  from_alternates: string;
  from_planned: string;
  unplanned: string;
  ready: string | null;
  on_time: boolean;
  late_days: number | null;
  reasons: string[];
};

export type PlannedOrder = {
  planned_order: string;
  item_id: string;
  warehouse_id: string;
  action: "make" | "buy";
  net: string;
  quantity: string;
  excess: string;
  need: string;
  release: string | null;
  ready: string | null;
  lead_days: number | null;
  bom: string | null;
  for_orders: string[];
  explanation: string;
  issues: string[];
};

export type ExcessSupply = { item_id: string; warehouse_id: string; source: string; reference: string; quantity: string };

export type BomLineView = {
  component_id: string;
  quantity: string;
  level: number;
  path: string[];
  bom: string;
  explanation: string;
  phantom: boolean;
  subassembly: boolean;
};

export type SupplierOfferView = {
  supplier_id: string;
  supplier_name: string;
  eligible: boolean;
  reasons: string[];
  notes: string[];
  order_quantity: string;
  excess_quantity: string;
  unit_price: string | null;
  landed_unit_cost: string | null;
  effective_unit_cost: string | null;
  unknown_charges: string[];
  total_cost: string | null;
  currency: string;
  fx_note: string;
  lead_days: number | null;
  earliest_delivery: string | null;
  meets_need_date: boolean | null;
  latest_release: string | null;
  rejection_pct: string | null;
  on_time_pct: string | null;
  evidence_lots: number;
  price_vs_last_pct: string | null;
  price_vs_average_pct: string | null;
  score: string | null;
  rank: number | null;
  allocated: string;
};

export type SupplierComparisonView = PlanningMeta & {
  item_id: string;
  quantity: string;
  need_date: string | null;
  policy: string;
  offers: SupplierOfferView[];
  split: SupplierOfferView[];
  recommendation: string;
  gaps: string[];
};

/** Customer Commitment Protection (/api/planning/commitments, /api/planning/commitment). Needs cost access. */
export type CommitmentAtRisk = {
  key: string;
  item_id: string;
  customer_id: string;
  quantity: string;
  due: string;
  delivery: string | null;
  late_days: number | null;
  order_value: string | null;
  currency: string;
};

export type SourcingOption = {
  label: string;
  kind: "supplier" | "split";
  material_id: string;
  suppliers: string[];
  quantity: string;
  total_cost: string | null;
  currency: string;
  lead_days: number | null;
  material_arrival: string | null;
  material_needed_by: string;
  production_complete: string | null;
  customer_delivery: string | null;
  meets_deadline: boolean;
  eligible: boolean;
  reasons: string[];
  notes: string[];
  incremental_cost: string | null;
  recommended: boolean;
};

export type CommitmentExposure = {
  order_value: string | null;
  currency: string;
  margin_value: string | null;
  penalty_per_day: string | null;
  penalty_if_cheapest: string | null;
  premium: string | null;
  premium_pct_of_value: string | null;
  premium_pct_of_margin: string | null;
  missing: string[];
};

export type CommitmentAnalysis = PlanningMeta & {
  order_key: string;
  item_id: string;
  customer_id: string;
  quantity: string;
  due: string;
  baseline: FulfilmentLine & { delivery: string | null };
  at_risk: boolean;
  critical: { item_id: string; warehouse_id: string; quantity: string; needed_by: string; planned_arrival: string | null; reason: string }[];
  options: SourcingOption[];
  recommended_delivery: string | null;
  feasible: boolean;
  exposure: CommitmentExposure;
  explanation: string[];
  fallbacks: string[];
  limitations: string[];
  approval_required: boolean;
};

export type DuplicateFinding = {
  item_a: string;
  item_b: string;
  verdict: "probable_duplicate" | "possible_duplicate" | "conflict" | "different_specification";
  confidence: string;
  similarity: number;
  reasons: string[];
  action: string;
};

export type LifecycleFinding = {
  item_id: string;
  verdict: string;
  on_hand: string;
  evidence: string[];
  still_needed: string | null;
  possible_excess: string | null;
  action: string;
};
