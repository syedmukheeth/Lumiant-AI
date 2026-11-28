import type { QueryClient } from "@tanstack/react-query";

/**
 * The signed-in session (`me`) and tenant facts (`meta`) kept in this tab's sessionStorage, so a reload paints the
 * shell and starts the page's requests at once instead of waiting for /api/auth/me first.
 *
 * Only display and routing facts are kept (name, roles, scope, sections, data date): no token, no data rows. The copy
 * is marked stale on restore, so React Query still asks the API straight away, and every data request is authorized
 * by the API as before. A 401 or sign-out clears it.
 */
const KEY = "lumiant-session";
const KEPT = ["me", "meta"] as const;

type Saved = Partial<Record<(typeof KEPT)[number], unknown>>;

function read(): Saved | null {
  try {
    const raw = window.sessionStorage.getItem(KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : null;
    return parsed && typeof parsed === "object" ? (parsed as Saved) : null;
  } catch {
    return null;
  }
}

function write(saved: Saved) {
  try {
    window.sessionStorage.setItem(KEY, JSON.stringify(saved));
  } catch {
    // private window or blocked storage: the next reload simply waits for the API
  }
}

export function clearSessionCache() {
  try {
    window.sessionStorage.removeItem(KEY);
  } catch {
    // nothing was stored either
  }
}

/** Put the saved session into the cache (as stale data) and keep the copy in step with the cache. */
export function bindSessionCache(qc: QueryClient): () => void {
  const saved = read();
  for (const key of KEPT) {
    const value = saved?.[key];
    // updatedAt 0: shown at once, but stale, so the query still fetches the current session from the API.
    if (value !== undefined && qc.getQueryData([key]) === undefined) qc.setQueryData([key], value, { updatedAt: 0 });
  }
  return qc.getQueryCache().subscribe((event) => {
    const key = event.query.queryKey[0];
    if (!KEPT.includes(key as (typeof KEPT)[number]) || event.query.queryKey.length !== 1) return;
    if (event.type === "removed") {
      clearSessionCache();
      return;
    }
    if (event.type !== "updated") return;
    const { status, data, error } = event.query.state;
    if (status === "error" && (error as { status?: number } | null)?.status === 401) clearSessionCache();
    else if (status === "success") write({ ...read(), [key as string]: data });
  });
}
