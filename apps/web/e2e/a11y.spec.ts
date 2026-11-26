import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

// Accessibility gate (V0, docs/05-plan/PRODUCT_V3_PLAN.md §5.3): no serious or critical axe finding on the main
// screens, in both themes. axe is injected through page.evaluate, which the page's script CSP does not apply to.

const THEMES = ["light", "dark"] as const;
const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

async function settle(page: Page) {
  await page.waitForLoadState("networkidle");
  await expect(page.locator("[aria-busy='true']")).toHaveCount(0);
  // Finish entrance animations so colour contrast is measured on the final colours, not mid-fade. Twice, because
  // cards that render when late data arrives (the insight feed) start their own entrance after the first pass.
  for (let pass = 0; pass < 2; pass++) {
    await page.evaluate(() =>
      document.getAnimations().forEach((a) => {
        const end = a.effect?.getComputedTiming().endTime;
        if (end !== Infinity && a.playState !== "finished") a.finish();
      }),
    );
    await page.waitForTimeout(400);
  }
}

async function scan(page: Page, where: string) {
  await settle(page);
  const result = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  const blocking = result.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  const report = blocking.map(
    (v) => `${where}: [${v.impact}] ${v.id}: ${v.help}\n    ${v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join("\n    ")}`,
  );
  expect(report, report.join("\n")).toEqual([]);
}

async function signIn(page: Page, username: string) {
  await page.context().clearCookies();
  await page.goto("/login");
  await page.getByTestId(`login-${username}`).click();
  await page.waitForURL("**/overview");
  await expect(page.locator("main h1").first()).toBeVisible();
}

async function scanPages(page: Page, paths: string[]) {
  for (const path of paths) {
    await page.goto(path);
    await expect(page.locator("main h1").first(), `${path} shows its page title`).toBeVisible();
    await scan(page, path);
  }
}

for (const theme of THEMES) {
  test.describe(`accessibility, ${theme} theme`, () => {
    test.beforeEach(async ({ page }) => {
      await page.addInitScript((t) => localStorage.setItem("lumiant-theme", t), theme);
    });

    test("public pages", async ({ page }) => {
      await page.context().clearCookies();
      await page.goto("/");
      await scan(page, "landing");
      await page.goto("/login");
      await scan(page, "sign-in");
    });

    test("app screens", async ({ page }) => {
      test.setTimeout(180_000);
      await signIn(page, "alpha.admin");
      await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
      await expect(page.getByTestId("kpi-items")).toContainText(/\d/);
      await scan(page, "overview");
      await scanPages(page, ["/inventory", "/risks", "/costs", "/assistant", "/reports", "/admin", "/design"]);
    });

    test("planning screens", async ({ page }) => {
      test.setTimeout(180_000);
      await signIn(page, "delta.admin"); // the tenant with orders, BOMs and suppliers
      await scanPages(page, ["/planning", "/commitments", "/suppliers", "/master-data"]);
    });
  });
}
