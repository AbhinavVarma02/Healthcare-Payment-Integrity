import { expect, test } from "@playwright/test";

const staticUrl = "http://127.0.0.1:4173";
const localUrl = "http://127.0.0.1:5173";

test("static study renders, charts and controls reconcile, and no backend receives requests", async ({ page }) => {
  const requests: string[] = [];
  const errors: string[] = [];
  page.on("request", (request) => requests.push(request.url()));
  page.on("pageerror", (error) => errors.push(error.message));
  await page.setViewportSize({ width: 1470, height: 1000 });
  await page.goto(staticUrl);
  await expect(page.getByRole("heading", { name: "Study overview" })).toBeVisible();
  await expect(page.getByText("95.9%", { exact: true })).toBeVisible();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to content" })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("main")).toBeFocused();
  await page.screenshot({ path: "test-results/overview-desktop.png", fullPage: true });
  await page.getByRole("link", { name: "Data explorer" }).click();
  await page.getByLabel("Claim part").selectOption("DME");
  await expect(page.getByRole("row", { name: /2025.*19,346.*8,650/ })).toBeVisible();
  await page.getByRole("link", { name: "Risk models" }).click();
  await expect(page.getByRole("img", { name: "Precision–recall comparison for 2025" })).toBeVisible();
  await page.getByLabel("Reporting year").selectOption("2024");
  await expect(page.getByRole("img", { name: "Precision–recall comparison for 2024" })).toBeVisible();
  await page.getByRole("link", { name: "Audit planner" }).click();
  await page.getByLabel("Review capacity").selectOption("10");
  await expect(page.getByRole("row", { name: /Risk only.*2,018/ })).toBeVisible();
  await page.getByRole("link", { name: "Policy replay" }).click();
  await page.getByLabel("Strategy details").selectOption("greedy");
  await page.getByLabel("Learning weights").selectOption("ipw");
  await expect(page.getByText("This weighting and strategy combination has no measured result.")).toBeVisible();
  await page.getByRole("link", { name: "Financial analysis" }).click();
  await expect(page.locator("output")).toHaveText("-$3.75");
  await page.getByLabel("Review cost (cents)").fill("1000");
  await expect(page.locator("output")).toHaveText("$16.25");
  await page.getByRole("link", { name: "Validation" }).click();
  await expect(page.getByText("research-only", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Methodology", exact: true }).click();
  await expect(page.getByRole("row", { name: /H3-sequential/ })).toBeVisible();
  expect(requests.every((url) => url.startsWith(staticUrl) || url.startsWith("data:"))).toBeTruthy();
  expect(errors).toEqual([]);
  const missing = await page.request.get(`${staticUrl}/assets/missing.js`);
  expect(missing.status()).toBe(404);
  expect(missing.headers()["content-security-policy"]).toContain("connect-src 'self'");
});

test("mobile navigation and loading error work", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.route("**/study.json", (route) => route.fulfill({ status: 503, body: "" }));
  await page.goto(staticUrl);
  await expect(page.getByText("The aggregate study file could not be loaded.")).toBeVisible();
  await page.unroute("**/study.json");
  await page.getByRole("button", { name: "Retry load" }).click();
  await expect(page.getByRole("heading", { name: "Study overview" })).toBeVisible();
  await page.screenshot({ path: "test-results/overview-mobile.png", fullPage: true });
  await page.getByRole("button", { name: "Open navigation" }).click();
  await page.getByRole("link", { name: "Policy replay" }).click();
  await expect(page.getByRole("heading", { name: "Exploration and cohort estimation" })).toBeVisible();
  expect(await page.evaluate(() => document.body.scrollWidth)).toBe(390);
});

test("local workspace scores, plans, and completes one real replay seed", async ({ page }) => {
  await page.goto(`${localUrl}/#/local`);
  await expect(page.getByText(/Local API status is research-only/)).toBeVisible();
  await page.getByRole("button", { name: "Score claim" }).click();
  await expect(page.getByText("Calibrated disagreement risk")).toBeVisible();
  await page.getByRole("button", { name: "Build plan" }).click();
  await expect(page.getByText("Selected examples")).toBeVisible();
  await page.getByRole("button", { name: "Start replay" }).click();
  await expect(page.getByText("1/1 seeds completed")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("completed", { exact: true })).toBeVisible();
  await page.screenshot({ path: "test-results/local-desktop.png", fullPage: true });
});
