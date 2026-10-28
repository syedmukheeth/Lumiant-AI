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

async function request<T>(method: "GET" | "POST", path: string, opts: { query?: Query; body?: unknown } = {}) {
  let res: Response;
  try {
    res = await fetch(buildUrl(path, opts.query), {
      method,
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        ...(method === "POST" ? { "Content-Type": "application/json", "X-Requested-With": "lumiant" } : {}),
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
};

// ---------------------------------------------------------------------------------------- API shapes
export type Me = {
  user: { id: string; display_name: string };
  tenant: { id: string; display_name: string };
  roles: string[];
  permissions: string[];
  scope: { all_warehouses: boolean; warehouses: string[]; departments: string[] };
  sections: ("overview" | "inventory" | "risks" | "costs" | "assistant" | "reports" | "admin")[];
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
