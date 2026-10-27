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
  sections: ("overview" | "inventory")[];
  auth_mode: string;
};

export type TenantMeta = {
  tenant_id: string;
  display_name: string;
  source_system: string;
  synthetic: boolean;
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

export type DevUser = { username: string; display_name: string; tenant_id: string; tenant_name: string; roles: string[] };

export type InventoryFilters = {
  warehouses: { id: string; name: string }[];
  item_groups: string[];
  abc_classes: string[];
  stages: string[];
};
