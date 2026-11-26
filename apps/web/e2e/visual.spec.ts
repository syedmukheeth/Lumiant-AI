import { expect, type Page, test } from "@playwright/test";

// Screenshot gate (V0): the pages that show only fixed sample content, in both themes, so a palette, type or layout
// change cannot ship unseen. `/design` holds every token, control and chart. Baselines are per platform
// (Playwright adds the platform to the file name); only Windows baselines exist so far, so CI (Linux) skips this
// file until Linux baselines are recorded (docs/06-operations/TESTING.md).
test.skip(!!process.env.CI, "screenshot baselines exist for Windows only");
test.use({ reducedMotion: "reduce", viewport: { width: 1440, height: 900 } });

const THEMES = ["light", "dark"] as const;
const SHOT = { fullPage: true, animations: "disabled", maxDiffPixelRatio: 0.01 } as const;

async function ready(page: Page) {
  await page.waitForLoadState("networkidle");
  await page.evaluate(() => document.fonts.ready);
  await expect(page.locator("[aria-busy='true']")).toHaveCount(0);
}

for (const theme of THEMES) {
  test.describe(`screens, ${theme} theme`, () => {
    test.beforeEach(async ({ page }) => {
      await page.addInitScript((t) => localStorage.setItem("lumiant-theme", t), theme);
    });

    test("landing page", async ({ page }) => {
      await page.context().clearCookies();
      await page.goto("/");
      await ready(page);
      // First screen only: the long marketing page reflows by a few pixels between runs (text wrapping), which
      // made full-page shots flaky; the hero holds the brand, type and colour that matter.
      await expect(page).toHaveScreenshot(`landing-${theme}.png`, { ...SHOT, fullPage: false });
    });

    test("sign-in page", async ({ page }) => {
      await page.context().clearCookies();
      await page.goto("/login");
      await expect(page.getByTestId("login-alpha.admin")).toBeVisible();
      await ready(page);
      await expect(page).toHaveScreenshot(`login-${theme}.png`, SHOT);
    });

    test("design system page", async ({ page }) => {
      test.setTimeout(90_000);
      await page.context().clearCookies();
      await page.goto("/login");
      await page.getByTestId("login-alpha.admin").click();
      await page.waitForURL("**/overview");
      await page.goto("/design");
      await expect(page.getByRole("heading", { name: "Design system" })).toBeVisible();
      await ready(page);
      await expect(page).toHaveScreenshot(`design-${theme}.png`, {
        ...SHOT,
        mask: [page.getByTestId("data-as-of")], // the data timestamp changes with every generated data set
      });
    });
  });
}
