import { defineConfig, devices } from "@playwright/test";

const apiPort = process.env.PLAYWRIGHT_API_PORT ?? "8021";
const webPort = process.env.PLAYWRIGHT_WEB_PORT ?? "3021";
const openemrMockPort = process.env.PLAYWRIGHT_OPENEMR_MOCK_PORT ?? "9821";
const apiBaseUrl = `http://127.0.0.1:${apiPort}`;
const webBaseUrl = `http://127.0.0.1:${webPort}`;
const openemrMockBaseUrl = `http://127.0.0.1:${openemrMockPort}`;
const shouldStartServers = !process.env.PLAYWRIGHT_BASE_URL;
const apiPython =
  process.env.PLAYWRIGHT_API_PYTHON ??
  (process.platform === "win32" ? "..\\api\\.venv\\Scripts\\python.exe" : "../api/.venv/bin/python");

const webServer = shouldStartServers
  ? [
      {
        command: `${apiPython} -m uvicorn app.main:app --app-dir ../api --host 127.0.0.1 --port ${apiPort}`,
        env: {
          APP_ENV: "local",
          PUBLIC_BASE_URL: webBaseUrl
        } as Record<string, string>,
        reuseExistingServer: false,
        timeout: 120_000,
        url: `${apiBaseUrl}/healthz`
      },
      {
        command: `npm run dev -- --hostname 127.0.0.1 --port ${webPort}`,
        env: {
          COPILOT_API_BASE_URL: apiBaseUrl,
          COPILOT_COOKIE_SECURE: "false",
          COPILOT_SESSION_SECRET: "playwright-session-secret-at-least-32-bytes",
          OPENEMR_BASE_URL: openemrMockBaseUrl,
          OPENEMR_CLIENT_ID: "playwright-smart-client",
          OPENEMR_CLIENT_SECRET: "playwright-smart-secret",
          OPENEMR_TOKEN_AUTH_METHOD: "client_secret_basic",
          PUBLIC_BASE_URL: "https://copilot.example.test"
        } as Record<string, string>,
        reuseExistingServer: false,
        timeout: 120_000,
        url: webBaseUrl
      }
    ]
  : undefined;

export default defineConfig({
  testDir: "./tests",
  timeout: 30_000,
  expect: {
    timeout: 10_000
  },
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? webBaseUrl,
    trace: "retain-on-failure"
  },
  ...(webServer ? { webServer } : {}),
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] }
    }
  ]
});
