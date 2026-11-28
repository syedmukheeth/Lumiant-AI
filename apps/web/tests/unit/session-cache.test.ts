import { QueryClient } from "@tanstack/react-query";
import { afterEach, describe, expect, it } from "vitest";

import { bindSessionCache, clearSessionCache } from "@/lib/session-cache";

const KEY = "lumiant-session";
const ME = { user_id: "alpha.admin", display_name: "Alex Admin", sections: ["overview"] };

afterEach(() => window.sessionStorage.clear());

describe("session cache", () => {
  it("restores the saved session as stale data, so the API is still asked", () => {
    window.sessionStorage.setItem(KEY, JSON.stringify({ me: ME }));
    const qc = new QueryClient();
    const unbind = bindSessionCache(qc);
    expect(qc.getQueryData(["me"])).toEqual(ME);
    expect(qc.getQueryState(["me"])?.dataUpdatedAt).toBe(0);
    // Stale even for a query with a long stale time, so the shell's useMe() refetches on mount.
    expect(qc.getQueryCache().find({ queryKey: ["me"] })?.isStaleByTime(5 * 60_000)).toBe(true);
    unbind();
  });

  it("does not overwrite a session that is already in the cache", () => {
    window.sessionStorage.setItem(KEY, JSON.stringify({ me: ME }));
    const qc = new QueryClient();
    qc.setQueryData(["me"], { ...ME, display_name: "Fresh" });
    bindSessionCache(qc)();
    expect(qc.getQueryData<typeof ME>(["me"])?.display_name).toBe("Fresh");
  });

  it("keeps only me and meta, and follows successful updates", () => {
    const qc = new QueryClient();
    const unbind = bindSessionCache(qc);
    qc.setQueryData(["me"], ME);
    qc.setQueryData(["meta"], { tenant: "demo-alpha" });
    qc.setQueryData(["metric-list"], [{ id: "x" }]);
    qc.setQueryData(["me", "extra"], { no: true });
    const saved = JSON.parse(window.sessionStorage.getItem(KEY) ?? "{}");
    expect(Object.keys(saved).sort()).toEqual(["me", "meta"]);
    expect(saved.me).toEqual(ME);
    unbind();
  });

  it("forgets the session on a 401 and when the session query is removed", async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const unbind = bindSessionCache(qc);
    qc.setQueryData(["me"], ME);
    expect(window.sessionStorage.getItem(KEY)).not.toBeNull();
    await qc
      .fetchQuery({ queryKey: ["me"], queryFn: () => Promise.reject(Object.assign(new Error("signed out"), { status: 401 })) })
      .catch(() => undefined);
    expect(window.sessionStorage.getItem(KEY)).toBeNull();

    qc.setQueryData(["me"], ME);
    expect(window.sessionStorage.getItem(KEY)).not.toBeNull();
    qc.removeQueries({ queryKey: ["me"] });
    expect(window.sessionStorage.getItem(KEY)).toBeNull();
    unbind();
  });

  it("survives corrupt storage", () => {
    window.sessionStorage.setItem(KEY, "{not json");
    const qc = new QueryClient();
    expect(() => bindSessionCache(qc)()).not.toThrow();
    expect(qc.getQueryData(["me"])).toBeUndefined();
    clearSessionCache();
    expect(window.sessionStorage.getItem(KEY)).toBeNull();
  });
});
