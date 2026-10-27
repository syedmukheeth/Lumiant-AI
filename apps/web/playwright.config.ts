import { defineConfig, devices } from "@playwright/test";

// The e2e stack is isolated from the dev stack: its own ports, its own freshly generated synthetic data
// and app DB under services/api/var/e2e, and a production build of the web app.
const API_PORT = 8100;
const WEB_PORT = 3100;

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: `http://127.0.0.1:${WEB_PORT}`,
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: `uv run lumiant-synthetic generate --all && uv run uvicorn --factory lumiant.main:create_app --host 127.0.0.1 --port ${API_PORT}`,
      cwd: "../../services/api",
      url: `http://127.0.0.1:${API_PORT}/api/health`,
      timeout: 180_000,
      reuseExistingServer: false,
      env: {
        LUMIANT_APP_ENV: "test",
        LUMIANT_DATA_DIR: "var/e2e",
        LUMIANT_APP_DB_URL: "sqlite:///var/e2e/app.db",
        LUMIANT_LOG_LEVEL: "WARNING",
        // The e2e suite signs in many times from one address.
        LUMIANT_RATE_LIMIT_LOGIN_PER_MIN: "1000",
      },
    },
    {
      command: `pnpm build && pnpm start --port ${WEB_PORT}`,
      url: `http://127.0.0.1:${WEB_PORT}/login`,
      timeout: 300_000,
      reuseExistingServer: false,
      env: { LUMIANT_API_ORIGIN: `http://127.0.0.1:${API_PORT}` },
    },
  ],
});
