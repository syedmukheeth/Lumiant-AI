import { afterEach, describe, expect, it, vi } from "vitest";

import { api, ApiError, buildUrl } from "@/lib/api";

afterEach(() => vi.unstubAllGlobals());

describe("buildUrl", () => {
  it("drops empty values and repeats array params", () => {
    expect(buildUrl("/api/x", { a: "1", b: undefined, c: "", d: ["p", "q"], e: 0 })).toBe("/api/x?a=1&d=p&d=q&e=0");
    expect(buildUrl("/api/x")).toBe("/api/x");
  });
});

describe("api client", () => {
  it("sends the CSRF header on POST and same-origin credentials", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    await api.post("/api/auth/dev-login", { username: "alpha.admin" });
    const [, init] = fetchMock.mock.calls[0];
    expect(init.headers["X-Requested-With"]).toBe("lumiant");
    expect(init.credentials).toBe("same-origin");
  });

  it("turns the API error envelope into an ApiError with code and request id", async () => {
    const body = { error: { code: "forbidden_scope", message: "No access.", request_id: "abc123" } };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status: 403 })));
    const err = await api.get("/api/inventory/balances").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ status: 403, code: "forbidden_scope", requestId: "abc123", message: "No access." });
  });

  it("does not leak non-JSON error bodies (e.g. proxy pages)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("<html>stack trace</html>", { status: 502 })));
    const err = (await api.get("/api/x").catch((e: unknown) => e)) as ApiError;
    expect(err.code).toBe("http_error");
    expect(err.message).not.toContain("stack");
  });

  it("reports network failures as status 0", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    const err = (await api.get("/api/x").catch((e: unknown) => e)) as ApiError;
    expect(err.status).toBe(0);
    expect(err.code).toBe("network_error");
  });
});
