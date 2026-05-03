import { createServer, type Server } from "node:http";

import { expect, test } from "@playwright/test";

const openemrMockPort = Number(process.env.PLAYWRIGHT_OPENEMR_MOCK_PORT ?? "9821");
let openemrMockServer: Server;
let lastTokenBody = "";
let lastTokenAuthorization = "";

test.beforeAll(async () => {
  openemrMockServer = createServer((request, response) => {
    if (request.method === "POST" && request.url === "/oauth2/default/token") {
      let body = "";
      request.on("data", (chunk) => {
        body += chunk.toString();
      });
      request.on("end", () => {
        lastTokenBody = body;
        lastTokenAuthorization = request.headers.authorization ?? "";
        response.writeHead(200, {
          "Content-Type": "application/json",
          "Cache-Control": "no-store"
        });
        if (body.includes("code=missing-token")) {
          response.end(JSON.stringify({ expires_in: 600, token_type: "Bearer" }));
          return;
        }
        response.end(
          JSON.stringify({
            access_token: "playwright-openemr-token",
            expires_in: 600,
            scope: "openid api:fhir user/Patient.read",
            token_type: "Bearer"
          })
        );
      });
      return;
    }

    response.writeHead(404, { "Content-Type": "application/json" });
    response.end(JSON.stringify({ error: "not_found" }));
  });

  await new Promise<void>((resolve) => {
    openemrMockServer.listen(openemrMockPort, "127.0.0.1", () => resolve());
  });
});

test.afterAll(async () => {
  await new Promise<void>((resolve, reject) => {
    openemrMockServer.close((error) => {
      if (error) reject(error);
      else resolve();
    });
  });
});

test("local demo chat streams cited evidence and refuses treatment advice", async ({ page }) => {
  const patientId = process.env.E2E_PATIENT_ID ?? "demo-diabetes-001";
  const patientName = new RegExp(process.env.E2E_PATIENT_NAME ?? "Demo Patient");
  const labText = new RegExp(process.env.E2E_LAB_TEXT ?? "Demo A1c was 8\\.6%");
  const labLink = new RegExp(process.env.E2E_LAB_LINK ?? "Demo A1c");

  await page.goto("/");

  await expect(page.getByRole("heading", { name: "AgentForge Clinical Co-Pilot" })).toBeVisible();
  await expect(page.getByText("Authenticated as doctor (dev-doctor)")).toBeVisible();
  await expect(page.getByLabel("Switch patient")).toHaveValue(patientId);
  await expect(page.getByText(patientName).first()).toBeVisible();
  await expect(page.getByRole("button", { name: /Meds \+ allergies/ })).toBeVisible();

  await page.getByRole("button", { name: /Recent labs/ }).click();
  await expect(page.getByText(labText)).toBeVisible();
  await expect(page.getByRole("link", { name: labLink })).toBeVisible();
  await expect(page.getByText("passed")).toBeVisible();

  await page.getByRole("textbox", { name: "Message" }).fill("What medication changes should I make?");
  await page.getByRole("button", { name: "Send" }).click();

  await expect(page.getByText(/can't recommend medication changes/)).toBeVisible();
  await expect(page.getByText("refused_treatment_recommendation")).toBeVisible();
});

test("OpenEMR launch context preselects a patient", async ({ page }) => {
  const patientId = process.env.E2E_PATIENT_ID ?? "demo-diabetes-001";
  const patientName = new RegExp(process.env.E2E_PATIENT_NAME ?? "Demo Patient");

  await page.goto(`/?launch_context=schedule&patient_id=${patientId}&appointment_eid=42`);

  await expect(page.getByText("Loaded patient context from OpenEMR launch.")).toBeVisible();
  await expect(page.getByText("Schedule appointment context included.")).toBeVisible();
  await expect(page.getByText(patientName).first()).toBeVisible();
  await expect(page.getByLabel("Switch patient")).toHaveValue(patientId);
  await expect(page.getByText(patientId)).toBeVisible();
});

test("missing bearer session starts SMART authorization with launch context", async ({ page }) => {
  await page.route("**/api/me", async (route) => {
    await route.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Missing bearer token" })
    });
  });
  await page.route("**/api/auth/start**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "text/html",
      body: "<main>SMART authorization start</main>"
    });
  });

  await page.goto(
    "/?launch_context=schedule&patient_id=patient-123&launch=launch-token&iss=https%3A%2F%2Fopenemr.example.test%2Fapis%2Fdefault%2Ffhir&aud=https%3A%2F%2Fopenemr.example.test%2Fapis%2Fdefault%2Ffhir"
  );

  await expect(page.getByText("SMART authorization start")).toBeVisible();
  await expect(page).toHaveURL(/\/api\/auth\/start/);
  const authStartUrl = new URL(page.url());
  expect(authStartUrl.searchParams.get("launch")).toBe("launch-token");
  expect(authStartUrl.searchParams.get("iss")).toBe(
    "https://openemr.example.test/apis/default/fhir"
  );
  expect(authStartUrl.searchParams.get("redirect_to")).toContain("patient_id=patient-123");
});

test("SMART callback exchanges code and creates an encrypted web session", async ({ request }) => {
  const redirectTo = "/?patient_id=patient-123";
  const startResponse = await request.get(
    `/api/auth/start?redirect_to=${encodeURIComponent(redirectTo)}`,
    { maxRedirects: 0 }
  );
  expect(startResponse.status()).toBeGreaterThanOrEqual(300);
  expect(startResponse.status()).toBeLessThan(400);

  const authorizationUrl = new URL(startResponse.headers()["location"]);
  expect(authorizationUrl.origin).toBe(`http://127.0.0.1:${openemrMockPort}`);
  expect(authorizationUrl.pathname).toBe("/oauth2/default/authorize");
  expect(authorizationUrl.searchParams.get("client_id")).toBe("playwright-smart-client");
  expect(authorizationUrl.searchParams.get("code_challenge_method")).toBe("S256");

  const state = authorizationUrl.searchParams.get("state");
  expect(state).toBeTruthy();

  const callbackResponse = await request.get(
    `/api/auth/callback?code=auth-code-123&state=${state}`,
    { maxRedirects: 0 }
  );
  expect(callbackResponse.status()).toBeGreaterThanOrEqual(300);
  expect(callbackResponse.status()).toBeLessThan(400);
  const callbackLocation = new URL(callbackResponse.headers()["location"]);
  expect(callbackLocation.origin).toBe("https://copilot.example.test");
  expect(`${callbackLocation.pathname}${callbackLocation.search}`).toBe(redirectTo);
  expect(lastTokenBody).toContain("grant_type=authorization_code");
  expect(lastTokenBody).toContain("code=auth-code-123");
  expect(lastTokenBody).toContain("client_id=playwright-smart-client");
  expect(lastTokenBody).toContain("code_verifier=");
  expect(lastTokenBody).not.toContain("client_secret=");
  expect(lastTokenAuthorization).toBe(
    `Basic ${Buffer.from("playwright-smart-client:playwright-smart-secret", "utf8").toString("base64")}`
  );

  const sessionResponse = await request.get("/api/auth/session");
  expect(sessionResponse.ok()).toBeTruthy();
  expect(await sessionResponse.json()).toEqual(
    expect.objectContaining({
      authenticated: true,
      scope: "openid api:fhir user/Patient.read"
    })
  );

  const publicOriginResponse = await request.get("/api/me", {
    headers: { Origin: "https://copilot.example.test" }
  });
  expect(publicOriginResponse.ok()).toBeTruthy();

  const crossSiteResponse = await request.get("/api/me", {
    headers: { Origin: "https://evil.example.test" }
  });
  expect(crossSiteResponse.status()).toBe(403);
});

test("SMART authorization start rejects untrusted launch issuers", async ({ request }) => {
  const response = await request.get(
    `/api/auth/start?iss=${encodeURIComponent("https://evil.example.test/apis/default/fhir")}`
  );

  expect(response.status()).toBe(400);
  expect(await response.json()).toEqual({
    error: "SMART issuer is not an allowed OpenEMR origin"
  });
});

test("SMART callback rejects token responses without an access token", async ({ request }) => {
  const redirectTo = "/?patient_id=patient-456";
  const startResponse = await request.get(
    `/api/auth/start?redirect_to=${encodeURIComponent(redirectTo)}`,
    { maxRedirects: 0 }
  );
  const authorizationUrl = new URL(startResponse.headers()["location"]);
  const state = authorizationUrl.searchParams.get("state");
  expect(state).toBeTruthy();

  const callbackResponse = await request.get(
    `/api/auth/callback?code=missing-token&state=${state}`,
    { maxRedirects: 0 }
  );
  expect(callbackResponse.status()).toBeGreaterThanOrEqual(300);
  expect(callbackResponse.status()).toBeLessThan(400);
  const callbackLocation = new URL(callbackResponse.headers()["location"]);
  expect(callbackLocation.origin).toBe("https://copilot.example.test");
  expect(`${callbackLocation.pathname}${callbackLocation.search}`).toBe(
    `${redirectTo}&auth_error=invalid_token_response`
  );
});
