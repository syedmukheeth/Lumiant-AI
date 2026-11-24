import { describe, expect, it } from "vitest";

import { needsDevLogin } from "@/proxy";

describe("needsDevLogin (routing only; the API authorizes every request)", () => {
  it("sends visitors without the dev session cookie to /login in development auth", () => {
    expect(needsDevLogin("/overview", false, undefined)).toBe(true);
    expect(needsDevLogin("/overview", false, "dev")).toBe(true);
    expect(needsDevLogin("/overview", true, "dev")).toBe(false);
    expect(needsDevLogin("/login", false, "dev")).toBe(false);
  });

  it("never redirects in OIDC mode: the identity-aware gateway signs users in (LA-01)", () => {
    expect(needsDevLogin("/overview", false, "oidc")).toBe(false);
    expect(needsDevLogin("/planning", false, "OIDC")).toBe(false);
  });
});
