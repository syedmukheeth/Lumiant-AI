import { describe, expect, it } from "vitest";

import { formatCount, formatMoney, formatNumber, formatQuantity, formatTimestamp, humanize, toChartNumber } from "@/lib/format";

const L = "en-US";
// Intl separates the currency code with a non-breaking space; compare on plain spaces.
const plain = (s: string) => s.replace(/ /g, " ");

describe("formatMoney", () => {
  it("formats decimal strings exactly, without float drift", () => {
    // 0.1 + 0.2 style values must never appear; the string is formatted as-is.
    expect(plain(formatMoney("146708.07823930", "USD", { locale: L }))).toBe("USD 146,708.08");
    expect(plain(formatMoney("9007199254740993.01", "EUR", { locale: L }))).toBe("EUR 9,007,199,254,740,993.01");
  });

  it("uses banker's rounding for display", () => {
    expect(plain(formatMoney("0.125", "USD", { locale: L }))).toBe("USD 0.12");
    expect(plain(formatMoney("0.135", "USD", { locale: L }))).toBe("USD 0.14");
  });

  it("always shows the currency code and flags a missing currency", () => {
    expect(plain(formatMoney("10", "GBP", { locale: L }))).toContain("GBP");
    expect(plain(formatMoney("10", null, { locale: L }))).toBe("10 (no currency)");
  });

  it("renders missing or malformed values as a dash, never as zero", () => {
    expect(plain(formatMoney(null, "USD", { locale: L }))).toBe("—");
    expect(plain(formatMoney("", "USD", { locale: L }))).toBe("—");
    expect(plain(formatMoney("12abc", "USD", { locale: L }))).toBe("—");
  });

  it("supports compact axis labels", () => {
    expect(plain(formatMoney(1_200_000, "USD", { compact: true, locale: L }))).toBe("USD 1.2M");
  });
});

describe("quantities and counts", () => {
  it("keeps up to three decimals and appends the unit", () => {
    expect(formatQuantity("107.6130", "KG", L)).toBe("107.613 KG");
    expect(formatQuantity("17.0000", "EA", L)).toBe("17 EA");
    expect(formatQuantity(null, "EA", L)).toBe("—");
  });

  it("formats counts without decimals", () => {
    expect(formatCount(1160, L)).toBe("1,160");
    expect(formatNumber("2.5", { maxFraction: 0, locale: L })).toBe("2");
  });
});

describe("helpers", () => {
  it("humanizes codes", () => {
    expect(humanize("MECH_SPARES")).toBe("Mech Spares");
    expect(humanize(null)).toBe("—");
  });

  it("chart numbers are only used for geometry", () => {
    expect(toChartNumber("12.5")).toBe(12.5);
    expect(toChartNumber(null)).toBe(0);
  });

  it("handles unknown timestamps", () => {
    expect(formatTimestamp(null)).toBe("unknown");
    expect(formatTimestamp("not-a-date")).toBe("unknown");
  });
});
