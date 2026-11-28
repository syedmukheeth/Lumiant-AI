// Per-request trace of one development sign-in on a running deployment: when each page and API request starts and
// how long it takes, relative to opening /login. Run it after the deployment has been idle to see the cold start
// (ISSUES #71); run it twice for warm numbers. Not a CI gate. Synthetic demo data only.
//
//   node scripts/sign-in-trace.mjs https://lumiant-ai.vercel.app [dev-user]
//
// Columns: start ms, +duration ms, status, method, "pf" for a request carrying `next-router-prefetch`, path,
// and the Vercel edge::function regions from `x-vercel-id`.
import { chromium } from "@playwright/test";

const base = (process.argv[2] ?? "http://127.0.0.1:3000").replace(/\/$/, "");
const user = process.argv[3] ?? "alpha.admin";
const TIMEOUT = 60_000;

const browser = await chromium.launch();
const page = await browser.newPage();
const t0 = Date.now();
const rel = () => Date.now() - t0;
const reqs = new Map();
page.on("request", (r) => {
  const u = new URL(r.url());
  if (u.pathname.startsWith("/_next/static") || /\.(png|svg|woff2|js|css|ico)$/.test(u.pathname)) return;
  reqs.set(r, {
    start: rel(),
    method: r.method(),
    path: u.pathname + (u.searchParams.has("_rsc") ? "?_rsc" : ""),
    pf: r.headers()["next-router-prefetch"] ? "pf" : "",
  });
});
page.on("requestfinished", async (r) => {
  const e = reqs.get(r);
  if (!e) return;
  e.end = rel();
  try {
    const res = await r.response();
    e.status = res?.status();
    e.region = (res?.headers()["x-vercel-id"] ?? "").split("::").slice(0, 2).join("::");
  } catch {
    // the page closed first
  }
});
page.on("requestfailed", (r) => {
  const e = reqs.get(r);
  if (e) Object.assign(e, { end: rel(), status: "FAILED" });
});

const marks = [];
await page.goto(`${base}/login`);
marks.push(["login page loaded", rel()]);
const button = page.getByTestId(`login-${user}`);
await button.waitFor({ state: "visible", timeout: TIMEOUT });
marks.push(["sign-in button shown (demo users loaded)", rel()]);
await button.click({ timeout: TIMEOUT });
marks.push(["clicked", rel()]);
await page.waitForURL("**/overview", { timeout: TIMEOUT });
marks.push(["on /overview", rel()]);
await page.waitForFunction(
  () => /\d/.test(document.querySelector('[data-testid="kpi-items"]')?.textContent ?? ""),
  null,
  { timeout: TIMEOUT },
);
marks.push(["Overview figures shown", rel()]);
await page.waitForLoadState("networkidle").catch(() => undefined);
marks.push(["network idle", rel()]);
await browser.close();

for (const [m, t] of marks) console.log(`${String(t).padStart(6)} ms  ${m}`);
console.log("");
for (const e of [...reqs.values()].sort((a, b) => a.start - b.start)) {
  const dur = e.end !== undefined ? e.end - e.start : "pending";
  console.log(
    `${String(e.start).padStart(6)} +${String(dur).padStart(6)}  ${e.status ?? "-"}  ${e.method.padEnd(4)} ${e.pf.padEnd(2)} ${e.path}  ${e.region ?? ""}`,
  );
}
