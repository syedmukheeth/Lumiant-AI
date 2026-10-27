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

test("risks: excess, dormant, expiring and data quality views load with provenance", async ({ page }) => {
  await signIn(page, "alpha.admin");
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Risks" }).click();
  await expect(page.getByRole("heading", { name: "Inventory risks" })).toBeVisible();
  const region = (name: string) => page.getByRole("region", { name });
  await expect(region("Excess stock").locator("tbody tr").first()).toBeVisible();
  await page.getByRole("tab", { name: "Dormant stock" }).click();
  await expect(region("Dormant stock").locator("tbody tr").first()).toBeVisible();
  await page.getByRole("tab", { name: "Expiring lots" }).click();
  await expect(region("Expiring lots").locator("tbody tr").first()).toBeVisible();
  await expect(region("Expiring lots")).toContainText(/Expired|d left/);
  await page.getByRole("tab", { name: "Data quality" }).click();
  await expect(page.getByTestId("dq-invalid_item_codes")).toContainText("3");
  await expect(page.getByTestId("dq-pairs_without_policy")).toBeVisible();
});

test("costs: comparison reconciles with the source and ABC compares with assigned", async ({ page }) => {
  await signIn(page, "alpha.admin");
  const pair = await page.request.get("/api/inventory/balances?sort=value&dir=desc&limit=1");
  const top = (await pair.json()).data[0];
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Costs" }).click();
  await page.getByLabel("Item id").fill(String(top.item_id));
  await page.getByRole("combobox", { name: "Warehouse" }).selectOption(String(top.warehouse_id));
  await page.getByRole("button", { name: "Compare" }).click();
  const result = page.getByTestId("cost-result");
  await expect(result).toContainText("Moving weighted average");
  await expect(result).toContainText("Reconciliation with the source valuation");
  await expect(result).toContainText(/USD/);
  await page.getByRole("button", { name: "Classify" }).click();
  await expect(page.getByTestId("abc-result")).toContainText("differ from the class assigned in the source");
});

test("costs and value-based pages are not offered to roles without cost access", async ({ page }) => {
  await signIn(page, "alpha.analyst");
  const nav = page.getByRole("navigation", { name: "Main" });
  await expect(nav.getByRole("link", { name: "Risks" })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Costs" })).toHaveCount(0);
  const forbidden = await page.request.get("/api/analyses/cost-comparison?item_id=x&warehouse_id=3100");
  expect(forbidden.status()).toBe(403);
});

test("assistant: answers with a table and source, asks to clarify, and respects permissions", async ({ page }) => {
  await signIn(page, "alpha.admin");
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Assistant" }).click();
  await page.getByLabel("Ask a question").fill("Which items are below reorder level?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  const answer = page.getByTestId("assistant-answer").first();
  await expect(answer).toContainText("below their reorder level");
  await expect(answer.locator("tbody tr").first()).toBeVisible();
  await expect(answer.getByRole("button", { name: /how this was calculated/i })).toBeVisible();
  await page.getByLabel("Ask a question").fill("how much stock of gasket");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.getByText("Which one do you mean?")).toBeVisible();
  await page.getByLabel("Ask a question").fill("Which items may become obsolete?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.getByText("can't predict obsolescence")).toBeVisible();
  await page.getByRole("button", { name: "Helpful" }).first().click();
  await expect(page.getByText("Thanks for the feedback")).toBeVisible();
});

test("assistant never reveals values to a role without cost access", async ({ page }) => {
  await signIn(page, "alpha.analyst");
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Assistant" }).click();
  await page.getByLabel("Ask a question").fill("Show the highest-value items");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  const answer = page.getByTestId("assistant-answer").first();
  await expect(answer).toContainText("can't view inventory values");
  await expect(answer).not.toContainText("USD");
});

test("guided menu runs the same analyses and reports carry metadata and export", async ({ page }) => {
  await signIn(page, "alpha.admin");
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Explore" }).click();
  await expect(page.getByTestId("explore-cards").getByRole("listitem")).toHaveCount(8);
  await page.getByRole("link", { name: /Find slow-moving items/ }).click();
  await expect(page.getByTestId("assistant-answer").first()).toContainText("no issue in the last 180 days");

  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Reports" }).click();
  await page.getByRole("combobox", { name: "Report" }).selectOption("below_reorder");
  const meta = page.getByTestId("report-meta");
  await expect(meta).toContainText("SYNTHETIC DEMO DATA");
  await expect(meta).toContainText("Access scope: all warehouses in tenant");
  await expect(page.getByRole("link", { name: "CSV" })).toBeVisible();
  const csv = await page.request.get("/api/reports/below_reorder/export?format=csv");
  expect(csv.status()).toBe(200);
  const text = await csv.text();
  expect(text).toContain("# Report");
  expect(text).toContain("# NOTICE");
});

test("a role without export or cost access sees a reduced menu and cannot export", async ({ page }) => {
  await signIn(page, "alpha.analyst");
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Explore" }).click();
  await expect(page.getByRole("link", { name: /Investigate inventory costs/ })).toHaveCount(0);
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Reports" }).click();
  await page.getByRole("combobox", { name: "Report" }).selectOption("below_reorder");
  await expect(page.getByTestId("report-view")).toBeVisible();
  await expect(page.getByRole("link", { name: "CSV" })).toHaveCount(0);
  await expect(page.getByText("Your role can view reports but not export them.")).toBeVisible();
  expect((await page.request.get("/api/reports/below_reorder/export")).status()).toBe(403);
  expect((await page.request.get("/api/reports/value_by_warehouse")).status()).toBe(403);
});

test("admin: schema check, capability matrix, reconciliation gate and audit log", async ({ page }) => {
  await signIn(page, "alpha.admin");
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Admin" }).click();
  await expect(page.getByTestId("schema-result")).toContainText("Mapping matches the source");
  await page.getByRole("tab", { name: "Capabilities" }).click();
  await expect(page.getByTestId("capabilities")).toContainText("Below-reorder analysis");

  const report = await (await page.request.get("/api/reports/value_by_warehouse")).json();
  const csv = report.rows.map((r: { warehouse_id: string; currency: string; value: string }) => `${r.warehouse_id},${r.currency},${r.value}`).join("\n");
  await page.getByRole("tab", { name: "Reconciliation" }).click();
  await page.getByLabel("Customer report rows").fill(csv);
  await page.getByRole("button", { name: "Reconcile" }).click();
  await expect(page.getByTestId("recon-result")).toContainText("Go-live gate passed");
  await page.getByLabel("Customer report rows").fill(csv + "\n9999,USD,1");
  await page.getByRole("button", { name: "Reconcile" }).click();
  await expect(page.getByTestId("recon-result")).toContainText("Go-live gate NOT passed");

  await page.getByRole("tab", { name: "Audit log" }).click();
  await expect(page.getByText("admin:reconciliation").first()).toBeVisible();
});

test("admin area is hidden from non-admin roles and refused by the API", async ({ page }) => {
  await signIn(page, "alpha.north_manager");
  await expect(page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Admin" })).toHaveCount(0);
  expect((await page.request.get("/api/admin/schema")).status()).toBe(403);
  expect((await page.request.get("/api/admin/audit")).status()).toBe(403);
});
