import { expect, type Page, test } from "@playwright/test";

async function signIn(page: Page, username: string) {
  await page.context().clearCookies();
  await page.goto("/login");
  await expect(page.getByText("Development authentication — not for production")).toBeVisible();
  await page.getByTestId(`login-${username}`).click();
  await page.waitForURL("**/overview");
  // Wait until the overview has data so the router is settled before the next interaction.
  await expect(page.getByTestId("kpi-items")).toContainText(/\d/);
}

async function openInventory(page: Page) {
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Inventory" }).click();
  await page.waitForURL("**/inventory**");
  await expect(page.getByRole("heading", { name: "Stock on hand" })).toBeVisible();
}

test("unauthenticated visitors are sent to the login page", async ({ page }) => {
  await page.context().clearCookies();
  await page.goto("/overview");
  await expect(page).toHaveURL(/\/login$/);
});

test("admin sees labelled synthetic data, values and provenance", async ({ page }) => {
  await signIn(page, "alpha.admin");
  await expect(page.getByTestId("synthetic-badge").first()).toBeVisible();
  await expect(page.getByTestId("data-as-of")).not.toContainText("unknown");
  await expect(page.getByTestId("kpi-value")).toContainText("USD");
  await expect(page.getByTestId("kpi-below")).toContainText(/\d/);

  const chart = page.getByRole("region", { name: "Value by warehouse" });
  await expect(chart.locator(".recharts-bar-rectangle").first()).toBeVisible();
  await chart.getByRole("button", { name: /how this was calculated/i }).click();
  const slip = page.getByRole("dialog");
  await expect(slip).toContainText("ZV_STOCK.LABST * ZV_STOCK.VERPR");
  await expect(slip).toContainText("all warehouses in tenant");
  await expect(slip).toContainText("show generated SQL"); // super_admin has query:view_sql
});

test("inventory search, filters and paging", async ({ page }) => {
  await signIn(page, "alpha.admin");
  await openInventory(page);
  const table = page.getByTestId("balances-table");
  await expect(table.locator("tbody tr").first()).toBeVisible();
  await expect(page.getByRole("region", { name: "Stock lines" }).getByTestId("pager-range")).toContainText("1–50 of");

  await page.getByLabel("Search items").fill("Gasket");
  await expect(page).toHaveURL(/q=Gasket/);
  const rows = table.locator("tbody tr");
  await expect(rows.first()).toContainText("Gasket");
  for (const text of await rows.allInnerTexts()) expect(text).toContain("Gasket");

  // Regression: a pending debounced search must not wipe a filter chosen right after it.
  await page.getByLabel("Search items").fill("");
  await page.getByRole("combobox", { name: "Warehouse" }).selectOption("3100");
  await expect(page).toHaveURL(/warehouse=3100/);
  await expect(page).not.toHaveURL(/q=Gasket/);
  await page.waitForTimeout(500); // longer than the 300 ms search debounce
  await expect(page).toHaveURL(/warehouse=3100/);
  await expect(table).toHaveAttribute("aria-busy", "false");
  await expect(table.locator("tbody tr").first()).toContainText("3100");
  for (const text of await table.locator("tbody tr").allInnerTexts()) expect(text).toContain("3100");
});

test("viewer without cost access never receives values", async ({ page }) => {
  await signIn(page, "alpha.analyst");
  await expect(page.getByTestId("kpi-value")).toContainText("Your role cannot view values");
  await expect(page.getByText("Value breakdowns are hidden")).toBeVisible();

  const denied = await page.request.get("/api/metrics/inventory_value_total");
  expect(denied.status()).toBe(403);

  await openInventory(page);
  const table = page.getByTestId("balances-table");
  await expect(table.locator("tbody tr").first()).toBeVisible();
  await expect(table.getByRole("columnheader", { name: /value/i })).toHaveCount(0);
  for (const text of await table.locator("tbody tr").allInnerTexts()) expect(text).toContain("3100");
});

test("a user of another tenant only sees their own warehouse", async ({ page }) => {
  await signIn(page, "beta.user");
  await expect(page.getByRole("banner").getByText("Demo Beta Distribution (synthetic)")).toBeVisible();
  await expect(page.getByTestId("kpi-value")).toContainText("GBP");
  await expect(page.getByTestId("kpi-value")).not.toContainText("EUR");
  await openInventory(page);
  await expect(page.getByRole("combobox", { name: "Warehouse" }).locator("option")).toHaveText([
    "All",
    "LDS1 · Leeds Plant Stores",
  ]);
  const forbidden = await page.request.get("/api/inventory/balances?warehouse=1100");
  expect(forbidden.status()).toBe(403);
});
