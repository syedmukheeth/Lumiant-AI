import { expect, type Page, type Request, test } from "@playwright/test";

// S11 speed work (ADR-0014): rail routes are prefetched in full on idle, kept for a while on the client, and filters
// change the URL without a server round trip. These tests fail if a click has to wait for the server again.

async function signIn(page: Page, username: string) {
  await page.context().clearCookies();
  await page.goto("/login");
  await page.getByTestId(`login-${username}`).click();
  await page.waitForURL("**/overview");
  await expect(page.getByTestId("kpi-items")).toContainText(/\d/);
}

/** A request for the Inventory page's server payload: what `router.replace(?qs)` used to send on every filter. */
const isInventoryPageRequest = (r: Request) => {
  const url = new URL(r.url());
  return url.pathname === "/inventory" && (url.searchParams.has("_rsc") || r.headers()["rsc"] === "1");
};

function watchConsole(page: Page) {
  const problems: string[] = [];
  page.on("console", (m) => {
    const text = m.text();
    if (m.type() === "error" || /content security policy|hydrat/i.test(text)) problems.push(text);
  });
  page.on("pageerror", (e) => problems.push(e.message));
  return problems;
}

test("a rail click shows the prefetched page without waiting for the server", async ({ page }) => {
  const problems = watchConsole(page);
  await signIn(page, "alpha.admin");
  // The shell prefetches every permitted route once the browser is idle.
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(2_500);

  // From now on every page request (navigation or prefetch) is held for 4 s: a page that still needs the server cannot
  // appear within 2 s. Full prefetches carry no `next-router-prefetch` header, so the header cannot tell them apart.
  await page.route(
    (url) => url.searchParams.has("_rsc"),
    async (route) => {
      await new Promise((r) => setTimeout(r, 4_000));
      await route.continue().catch(() => undefined);
    },
  );
  const rail = page.getByRole("navigation", { name: "Main" });
  const started = Date.now();
  await rail.getByRole("link", { name: "Inventory" }).click();
  await expect(page.getByRole("heading", { name: "Stock on hand" })).toBeVisible({ timeout: 2_000 });
  expect(Date.now() - started).toBeLessThan(2_000);
  await rail.getByRole("link", { name: "Risks" }).click();
  await expect(page.getByRole("heading", { name: "Inventory risks" })).toBeVisible({ timeout: 2_000 });
  // A revisit within the client cache window needs no request either, and the highlight follows the click.
  await rail.getByRole("link", { name: "Inventory" }).click();
  await expect(page.getByRole("heading", { name: "Stock on hand" })).toBeVisible({ timeout: 2_000 });
  await expect(rail.getByRole("link", { name: "Inventory" })).toHaveAttribute("aria-current", "page");
  await rail.getByRole("link", { name: "Overview" }).click();
  await expect(page.getByTestId("kpi-items")).toContainText(/\d/, { timeout: 2_000 });
  expect(problems).toEqual([]);
});

test("an inventory filter or sort change makes no server round trip for the page", async ({ page }) => {
  await signIn(page, "alpha.admin");
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Inventory" }).click();
  await expect(page.getByRole("heading", { name: "Stock on hand" })).toBeVisible();
  const table = page.getByTestId("balances-table");
  await expect(table.locator("tbody tr").first()).toBeVisible();

  const rsc: string[] = [];
  page.on("request", (r) => {
    if (isInventoryPageRequest(r)) rsc.push(r.url());
  });
  await page.getByRole("combobox", { name: "Warehouse" }).selectOption("3100");
  await expect(page).toHaveURL(/warehouse=3100/);
  await expect(table).toHaveAttribute("aria-busy", "false");
  await expect(table.locator("tbody tr").first()).toContainText("3100");
  await page.getByLabel("Search items").fill("Gasket");
  await expect(page).toHaveURL(/q=Gasket/);
  await expect(table.locator("tbody tr").first()).toContainText("Gasket");
  // Back and forward still restore the filters (the URL stays the source of truth).
  await page.goBack();
  await expect(page).not.toHaveURL(/q=Gasket/);
  expect(rsc).toEqual([]);
});
