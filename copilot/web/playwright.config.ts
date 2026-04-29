import { defineConfig, devices } from "@playwright/test";

const apiPort = process.env.PLAYWRIGHT_API_PORT ?? "8021";
const webPort = process.env.PLAYWRIGHT_WEB_PORT ?? "3021";
const apiBaseUrl = `http://127.0.0.1:${apiPort}`;
const webBaseUrl = `http://127.0.0.1:${webPort}`;
const apiPython =
  process.env.PLAYWRIGHT_API_PYTHON ??
  (process.platform === "win32" ? "..\\api\\.venv\\Scripts\\python.exe" : "../api/.venv/bin/python");

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
  webServer: [
    {
      command: `${apiPython} -m uvicorn app.main:app --app-dir ../api --host 127.0.0.1 --port ${apiPort}`,
      env: {
        APP_ENV: "local",
        PUBLIC_BASE_URL: webBaseUrl
      },
      reuseExistingServer: false,
      timeout: 120_000,
      url: `${apiBaseUrl}/healthz`
    },
    {
      command: `npm run dev -- --hostname 127.0.0.1 --port ${webPort}`,
      env: {
        NEXT_PUBLIC_API_BASE_URL: apiBaseUrl
      },
      reuseExistingServer: false,
      timeout: 120_000,
      url: webBaseUrl
    }
  ],
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] }
    }
  ]
});
