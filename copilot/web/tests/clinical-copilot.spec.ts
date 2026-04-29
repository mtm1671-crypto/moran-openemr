import { expect, test } from "@playwright/test";

test("local demo chat streams cited evidence and refuses treatment advice", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByText("Local demo auth - doctor - dev-doctor")).toBeVisible();
  await expect(page.getByRole("button", { name: /Demo Patient/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /Meds \+ allergies/ })).toBeVisible();

  await page.getByRole("button", { name: /Recent labs/ }).click();
  await expect(page.getByText(/Demo A1c was 8\.6%/)).toBeVisible();
  await expect(page.getByRole("link", { name: "Demo A1c" })).toBeVisible();
  await expect(page.getByText("passed")).toBeVisible();

  await page.getByRole("textbox", { name: "Message" }).fill("What medication changes should I make?");
  await page.getByRole("button", { name: "Send" }).click();

  await expect(page.getByText(/can't recommend medication changes/)).toBeVisible();
  await expect(page.getByText("refused_treatment_recommendation")).toBeVisible();
});

test("OpenEMR launch context preselects a patient", async ({ page }) => {
  await page.goto("/?launch_context=schedule&patient_id=demo-diabetes-001&appointment_eid=42");

  await expect(page.getByText("Loaded patient context from OpenEMR launch.")).toBeVisible();
  await expect(page.getByText("Schedule appointment context included.")).toBeVisible();
  await expect(page.getByRole("button", { name: /Demo Patient/ })).toBeVisible();
  await expect(page.getByText("demo-diabetes-001")).toBeVisible();
});
