/**
 * Content-Security-Policy with a per-request nonce (ISSUES #19).
 *
 * Scripts: same-origin files and inline scripts carrying the nonce; no 'unsafe-inline' (and no,
 * so the same-origin theme-init.js in /public keeps working without a nonce). Styles keep 'unsafe-inline' because React and Recharts set style attributes, which
 * a nonce cannot cover; that is a much smaller risk than inline scripts. Development needs eval for hot reload.
 */
export function buildCsp(nonce: string, dev: boolean): string {
  return [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}'${dev ? " 'unsafe-eval'" : ""}`,
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self' data:",
    `connect-src 'self'${dev ? " ws: wss:" : ""}`,
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ].join("; ");
}
