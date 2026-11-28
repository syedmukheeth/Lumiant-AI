// Navigation timing on a running Lumiant web app (local production build or a deployment). Not a CI gate: numbers
// depend on the machine and the network. Results go in docs/logs/TEST_RUNS.md (ADR-0014).
//
//   node scripts/nav-timing.mjs [base-url] [dev-user]
//   node scripts/nav-timing.mjs https://lumiant-ai.vercel.app alpha.admin
//
// Signs in with development sign-in (synthetic data only), then measures:
// - sign-in → Overview figures shown, and the API calls it took
// - each rail link, first visit and revisit: click → page shown (heading, no route skeleton) and → data shown
//   (no skeleton or busy region left in the page)
// - Overview reload → figures shown, and the API calls it took
import { chromium } from "@playwright/test";

const base = (process.argv[2] ?? "http://127.0.0.1:3000").replace(/\/$/, "");
const user = process.argv[3] ?? "alpha.admin";
const TIMEOUT = 20_000;

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
let apiCalls = 0;
page.on("request", (r) => {
  if (new URL(r.url()).pathname.startsWith("/api/")) apiCalls += 1;
});

const now = () => performance.now();
const ms = (n) => `${Math.round(n)}`.padStart(6);
const figures = () =>
  page.waitForFunction(() => /\d/.test(document.querySelector('[data-testid="kpi-items"]')?.textContent ?? ""), null, {
    timeout: TIMEOUT,
    polling: "raf",
  });

// ------------------------------------------------------------------ sign in
await page.goto(`${base}/login`);
let t = now();
apiCalls = 0;
await page.getByTestId(`login-${user}`).click();
await page.waitForURL("**/overview", { timeout: TIMEOUT });
await figures();
const signIn = now() - t;
await page.waitForLoadState("networkidle");
const signInCalls = apiCalls;
await page.waitForTimeout(3_000); // idle prefetch of the rail routes

// ------------------------------------------------------------------ rail clicks
const links = await page.getByRole("navigation", { name: "Main" }).getByRole("link").all();
const rail = [];
for (const link of links) rail.push({ name: (await link.innerText()).trim() || (await link.getAttribute("aria-label")), href: await link.getAttribute("href") });
const order = [...rail.filter((r) => r.href !== "/overview"), ...rail.filter((r) => r.href === "/overview")];

async function visit({ name, href }) {
  const start = now();
  await page.locator(`nav[aria-label="Main"] a[href="${href}"]`).click();
  await page.waitForFunction(
    (path) =>
      location.pathname.startsWith(path) &&
      !document.querySelector('[data-testid="page-loading"]') &&
      document.querySelector("main h1"),
    href,
    { timeout: TIMEOUT, polling: "raf" },
  );
  const shown = now() - start;
  await page.waitForFunction(() => !document.querySelector("main .skeleton, main [aria-busy='true']"), null, {
    timeout: TIMEOUT,
    polling: 50,
  });
  return { name, shown, data: now() - start };
}

const first = [];
for (const r of order) first.push(await visit(r));
const again = [];
for (const r of order) again.push(await visit(r));

// ------------------------------------------------------------------ overview reload
apiCalls = 0;
t = now();
await page.reload();
await figures();
const reload = now() - t;
await page.waitForLoadState("networkidle");
const reloadCalls = apiCalls;
await browser.close();

console.log(`Navigation timing — ${base} as ${user} (ms)\n`);
console.log(`sign-in → overview figures  ${ms(signIn)}   (${signInCalls} API calls)`);
console.log(`overview reload → figures   ${ms(reload)}   (${reloadCalls} API calls)\n`);
console.log(`${"page".padEnd(16)} ${"first: shown".padStart(13)} ${"data".padStart(7)}   ${"revisit: shown".padStart(15)} ${"data".padStart(7)}`);
for (let i = 0; i < first.length; i++) {
  const a = first[i];
  const b = again[i];
  console.log(`${String(a.name).padEnd(16)} ${ms(a.shown).padStart(13)} ${ms(a.data).padStart(7)}   ${ms(b.shown).padStart(15)} ${ms(b.data).padStart(7)}`);
}
const median = (xs) => [...xs].sort((x, y) => x - y)[Math.floor(xs.length / 2)];
console.log(
  `\nmedian           ${ms(median(first.map((x) => x.shown))).padStart(13)} ${ms(median(first.map((x) => x.data))).padStart(7)}   ${ms(median(again.map((x) => x.shown))).padStart(15)} ${ms(median(again.map((x) => x.data))).padStart(7)}`,
);
