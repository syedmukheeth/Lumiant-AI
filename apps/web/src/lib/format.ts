/**
 * Display formatting. The API sends decimals as strings; Intl.NumberFormat formats numeric *strings*
 * exactly (no float rounding), so amounts are never converted to JS numbers for display.
 * Amounts are never summed in the browser.
 */

type Numeric = string | number | null | undefined;

function asIntlInput(value: string | number): number {
  // Intl accepts decimal strings at runtime (ES2023); the cast only satisfies older lib typings.
  return value as unknown as number;
}

function isNumeric(value: Numeric): value is string | number {
  if (value === null || value === undefined || value === "") return false;
  return typeof value === "number" ? Number.isFinite(value) : /^-?\d+(\.\d+)?$/.test(value);
}

export function formatNumber(value: Numeric, opts: { maxFraction?: number; minFraction?: number; locale?: string } = {}) {
  if (!isNumeric(value)) return "—";
  return new Intl.NumberFormat(opts.locale, {
    minimumFractionDigits: opts.minFraction ?? 0,
    maximumFractionDigits: opts.maxFraction ?? 2,
    roundingMode: "halfEven",
  } as Intl.NumberFormatOptions).format(asIntlInput(value));
}

export function formatMoney(value: Numeric, currency: string | null | undefined, opts: { compact?: boolean; locale?: string } = {}) {
  if (!isNumeric(value)) return "—";
  if (!currency) return `${formatNumber(value, { locale: opts.locale })} (no currency)`;
  return new Intl.NumberFormat(opts.locale, {
    style: "currency",
    currency,
    currencyDisplay: "code",
    notation: opts.compact ? "compact" : "standard",
    minimumFractionDigits: opts.compact ? 0 : 2,
    maximumFractionDigits: opts.compact ? 1 : 2,
    roundingMode: "halfEven",
  } as Intl.NumberFormatOptions).format(asIntlInput(value));
}

export function formatQuantity(value: Numeric, uom?: string | null, locale?: string) {
  const n = formatNumber(value, { maxFraction: 3, locale });
  return uom && n !== "—" ? `${n} ${uom}` : n;
}

export function formatCount(value: Numeric, locale?: string) {
  return formatNumber(value, { maxFraction: 0, locale });
}

export function formatTimestamp(iso: string | null | undefined, locale?: string) {
  if (!iso) return "unknown";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "unknown";
  return new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" }).format(d);
}

/** Chart geometry only — labels and tooltips always use the exact string. */
export function toChartNumber(value: Numeric): number {
  return isNumeric(value) ? Number(value) : 0;
}

export function humanize(code: string | null | undefined): string {
  if (!code) return "—";
  return code
    .toLowerCase()
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}
