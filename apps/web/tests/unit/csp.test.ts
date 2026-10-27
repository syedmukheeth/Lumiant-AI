import { describe, expect, it } from "vitest";

import { buildCsp } from "@/lib/csp";

describe("buildCsp", () => {
  const prod = buildCsp("abc123", false);

  it("allows scripts only from self and by nonce, never inline or eval, in production", () => {
    const scriptSrc = prod.split("; ").find((d) => d.startsWith("script-src"))!;
    expect(scriptSrc).toBe("script-src 'self' 'nonce-abc123'");
  });

  it("keeps the other lock-downs", () => {
    for (const d of ["object-src 'none'", "base-uri 'self'", "form-action 'self'", "frame-ancestors 'none'", "connect-src 'self'"]) {
      expect(prod).toContain(d);
    }
  });

  it("only development adds eval and websockets (hot reload)", () => {
    const dev = buildCsp("abc123", true);
    expect(dev).toContain("'unsafe-eval'");
    expect(dev).toContain("ws:");
    expect(prod).not.toContain("unsafe-eval");
    expect(prod).not.toContain("ws:");
  });
});
