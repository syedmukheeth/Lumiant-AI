import { expect, type Page, test } from "@playwright/test";

// Planning workspaces and official branding on the synthetic manufacturer (demo-delta). Assertions avoid counts that
// depend on the weekday: demo-delta is dated relative to the generation day and plans on a Fri/Sat weekend calendar.

async function signIn(page: Page, username: string) {
  await page.context().clearCookies();
  await page.goto("/login");
  await expect(page.getByText("Development authentication, not for production")).toBeVisible();
  await page.getByTestId(`login-${username}`).click();
  await page.waitForURL("**/overview");
}

async function go(page: Page, label: string, path: string) {
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: label }).click();
  await page.waitForURL(`**${path}`);
}

test("official logo follows the theme and loads on the sign-in page", async ({ page }) => {
  await page.context().clearCookies();
  await page.goto("/login");
  await page.evaluate(() => localStorage.setItem("lumiant-theme", "dark"));
  await page.reload();
  const dark = page.getByTestId("brand-logo-dark").first();
  await expect(dark).toBeVisible();
  await expect(page.getByTestId("brand-logo-light").first()).toBeHidden();
  expect(await dark.evaluate((img: HTMLImageElement) => img.naturalWidth)).toBe(232); // the exact supplied file

  await page.evaluate(() => localStorage.setItem("lumiant-theme", "light"));
  await page.reload();
  const light = page.getByTestId("brand-logo-light").first();
  await expect(light).toBeVisible();
  await expect(page.getByTestId("brand-logo-dark").first()).toBeHidden();
  expect(await light.evaluate((img: HTMLImageElement) => img.naturalWidth)).toBe(230);
  expect(await light.evaluate((img: HTMLImageElement) => img.naturalHeight)).toBe(78); // supplied file minus the 2 teal rows
  await page.evaluate(() => localStorage.removeItem("lumiant-theme"));
});

test("order fulfilment explains a late order and the material plan flags a missing lead time", async ({ page }) => {
  await signIn(page, "delta.admin");
  const logo = page.locator("aside [data-testid^=brand-logo]:visible").first(); // the sidebar logo for the active theme
  await expect(logo).toBeVisible();
  expect((await logo.boundingBox())!.width).toBeGreaterThanOrEqual(150); // brief: ~150-170 px on desktop
  await go(page, "Orders & materials", "/planning");
  await expect(page.getByRole("heading", { name: "Orders & materials" })).toBeVisible();

  const line = page.getByTestId("line-SO-1001/10");
  await expect(line).toContainText("FG-PUMP-100");
  await expect(line).not.toContainText("On time");
  await line.getByRole("button", { name: /SO-1001\/10/ }).click();
  await expect(line.getByRole("list", { name: /Why SO-1001\/10 is late/ })).toContainText("RM-IMPELLER");

  await page.getByRole("tab", { name: "Material plan" }).click();
  const plan = page.getByRole("region", { name: "Planned orders" });
  await expect(plan).toContainText("RM-COPPER");
  await expect(plan).toContainText("cannot be dated");
  await expect(plan).toContainText("no purchase or production order is created");
});

test("BOM explorer passes a phantom kit through to its parts", async ({ page }) => {
  await signIn(page, "delta.admin");
  await go(page, "Orders & materials", "/planning");
  await page.getByRole("tab", { name: "BOM explorer" }).click();
  await page.getByLabel("Item code").fill("FG-SKID-1");
  await page.getByLabel("Quantity").fill("2");
  await page.getByRole("button", { name: "Explode" }).click();
  await expect(page.getByRole("list", { name: "BOM tree" })).toContainText("PH-KIT-01");
  await expect(page.getByRole("list", { name: "BOM tree" })).toContainText("phantom");
  const totals = page.getByRole("region", { name: "Total requirement" });
  await expect(totals).toContainText("RM-BOLT-M10");
  await expect(totals).not.toContainText("PH-KIT-01");
});

test("supplier comparison ranks by policy and lists ineligible suppliers with reasons", async ({ page }) => {
  await signIn(page, "delta.admin");
  await go(page, "Supplier comparison", "/suppliers");
  await page.getByLabel("Item code").fill("RM-IMPELLER");
  await page.getByLabel("Quantity needed").fill("27");
  await page.getByRole("button", { name: "Compare" }).click();
  await expect(page.getByTestId("supplier-recommendation")).toContainText("Beta Castings");
  await expect(page.getByTestId("supplier-recommendation")).toContainText("no purchase order is created");
  const table = page.locator("table");
  await expect(table).toContainText("ISO 9001 expired");
  await expect(table).toContainText("supplier is not approved");

  await page.getByLabel("Ranking policy").selectOption("lowest_cost");
  await page.getByRole("button", { name: "Compare" }).click();
  await expect(page.getByTestId("supplier-recommendation")).toContainText("Alpha Foundry");
});

test("commitment protection lists at-risk orders and compares sourcing options on the full timeline", async ({ page }) => {
  await signIn(page, "delta.admin");
  await go(page, "Commitment protection", "/commitments");
  await expect(page.getByRole("heading", { name: "Commitment protection" })).toBeVisible();
  await expect(page.getByTestId("risk-SO-1001/10")).toContainText("CUST-OASIS");
  await page.getByTestId("risk-SO-1001/10").getByRole("button", { name: "SO-1001/10" }).click();
  await page.waitForURL("**/commitments?order=SO-1001%2F10");
  const analysis = page.getByTestId("commitment-analysis");
  await expect(analysis).toContainText("Order value at stake");
  // Feasibility depends on the generation weekday, so assert the structure: options, gates and the approval note.
  const table = analysis.locator("table");
  for (const col of ["Material arrival", "Production completion", "Customer delivery", "Total cost", "Feasibility"]) {
    await expect(table).toContainText(col);
  }
  await expect(table).toContainText("supplier is not approved");
  await expect(table).toContainText("exceeds the 5% quality limit");
  await expect(analysis).toContainText("no purchase order is created");

  await go(page, "Orders & materials", "/planning");
  await page.getByTestId("line-SO-1001/10").getByRole("link", { name: "Protect this order" }).click();
  await page.waitForURL("**/commitments?order=SO-1001%2F10");
});

test("item master shows duplicate codes and keeps a critical spare", async ({ page }) => {
  await signIn(page, "delta.admin");
  await go(page, "Item master", "/master-data");
  await expect(page.getByTestId("dup-RM-BOLT-M10-RM-BOLT-M10B")).toContainText("Possible duplicate");
  await page.getByRole("tab", { name: "Lifecycle review" }).click();
  await expect(page.getByTestId("life-SP-BEARING-7310")).toContainText(/critical keep/i);
  await expect(page.getByTestId("life-SP-GASKET-OLD")).toContainText(/obsolete candidate/i);
});

test("a planner without cost access gets planning but no supplier prices", async ({ page }) => {
  await signIn(page, "delta.planner");
  const nav = page.getByRole("navigation", { name: "Main" });
  await expect(nav.getByRole("link", { name: "Orders & materials" })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Supplier comparison" })).toHaveCount(0);
  await expect(nav.getByRole("link", { name: "Commitment protection" })).toHaveCount(0);
  await page.goto("/suppliers");
  await expect(page.getByText("Not available for your role.")).toBeVisible();
});
