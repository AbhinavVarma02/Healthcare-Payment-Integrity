import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import axe from "axe-core";

const staticRoot = "http://127.0.0.1:4173";
const localRoot = "http://127.0.0.1:5173";
const apiRoot = "http://127.0.0.1:8000";
const sharedRoutes = ["overview", "data", "models", "planner", "replay", "finance", "validation",
  "evidence", "review", "analyst", "methods"];
const sizes = [
  { name: "desktop", width: 1440, height: 900 },
  { name: "tablet", width: 768, height: 950 },
  { name: "mobile", width: 390, height: 844 },
];

for (const mode of ["static", "local"] as const) {
  for (const { name, width, height } of sizes) {
    for (const theme of ["light", "dark"] as const) {
      test(`${mode} ${name} ${theme} routes render without overflow or runtime errors`, async ({ page }, info) => {
        test.setTimeout(90_000);
        await page.setViewportSize({ width, height });
        await page.emulateMedia({ colorScheme: theme });
        const root = mode === "static" ? staticRoot : localRoot;
        const routes = mode === "static" ? sharedRoutes : [...sharedRoutes, "local", "operations"];
        const failures: string[] = [];
        const accessibility: Record<string, string[]> = {};
        page.on("pageerror", (error) => failures.push(error.message));
        page.on("request", (request) => {
          const url = request.url();
          if (!url.startsWith(root + "/") && !(mode === "local" && url.startsWith(apiRoot + "/")) &&
              !url.startsWith("data:")) failures.push(`Unexpected request ${url}`);
        });
        page.on("requestfailed", (request) => {
          const reason = request.failure()?.errorText;
          const cancelledStudy = request.url() === `${root}/study.json` &&
            (reason === "net::ERR_ABORTED" || reason === "NS_BINDING_ABORTED");
          if (!cancelledStudy) failures.push(`Failed request ${request.url()} (${reason})`);
        });
        page.on("response", (response) => {
          if (response.status() >= 400) failures.push(`Response ${response.status()} ${response.url()}`);
        });
        page.on("console", (message) => {
          if (message.type() === "error") failures.push(message.text());
        });
        for (const route of routes) {
          await page.goto(`${root}/?screen=${route}#/${route}`);
          await expect(page.locator("main h1")).toBeVisible();
          await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
          if (name === "desktop" && route === "overview") {
            const timing = await page.evaluate(() => {
              const navigation = performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming;
              return { heading_ready_ms: performance.now(), document_end_ms: navigation.responseEnd,
                resources: performance.getEntriesByType("resource").length };
            });
            await info.attach("navigation-timing", { body: JSON.stringify(timing), contentType: "application/json" });
          }
          await expect(page.locator("#navigation [aria-current='page']")).toHaveAttribute("href", `#/${route}`);
          expect(await page.locator(".topbar").evaluate((header) =>
            header.getBoundingClientRect().top - document.querySelector(".sidebar")!.getBoundingClientRect().bottom),
          route).toBeLessThanOrEqual(width <= 850 ? 1 : 0);
          if (route === "operations") await expect(page.getByRole("button", { name: "Intake sample batch" })).toBeEnabled();
          if (route === "local") await expect(page.getByRole("status", { name: "Local API status" })).toContainText("Research-only");
          expect(await page.evaluate(() => document.documentElement.scrollWidth), route).toBe(width);
          await page.screenshot({ path: `test-results/porcelain/${info.project.name}/${mode}/${theme}/${name}/${route}.png` });
          if (name === "desktop") {
            await page.evaluate(axe.source);
            const result = await page.evaluate(async () => {
              return await (window as typeof window & { axe: typeof axe }).axe.run(document, {
                runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] },
              });
            });
            accessibility[route] = result.violations.map((violation) =>
              `${violation.id} [${violation.impact}]: ${violation.nodes.map((node) => node.target.join(" ")).join(", ")}`);
          }
        }
        await info.attach("accessibility", { body: JSON.stringify(accessibility), contentType: "application/json" });
        expect(failures).toEqual([]);
        expect(Object.values(accessibility).flat()).toEqual([]);
      });
    }
  }
}

const option = (page: Page, group: string, name: string) =>
  page.getByRole("radiogroup", { name: group }).getByRole("radio", { name, exact: true });
const navigate = (page: Page, name: string) =>
  page.getByRole("navigation", { name: "Workspace" }).getByRole("link", { name, exact: true }).click();

test("guided planner and analyst report matched evidence in each mode", async ({ page }, info) => {
  for (const root of [staticRoot, localRoot]) {
    await page.goto(`${root}/#/overview`);
    await page.getByRole("link", { name: "Plan an audit" }).click();
    await expect(page.locator("main")).toBeFocused();
    await option(page, "Review capacity", "10%").check();
    await option(page, "Exploration share", "20%").check();
    const tradeOff = page.getByRole("list", { name: "Equal-budget review outcomes" });
    await expect(tradeOff.getByText("20% exploration")).toBeVisible();
    await page.getByRole("button", { name: "Reset scenario" }).click();
    await expect(option(page, "Review capacity", "5%")).toBeChecked();
    await expect(tradeOff.getByText("10% exploration")).toBeVisible();
    await expect(tradeOff.getByText("3.89 pp")).toBeVisible();
    await page.getByText("Fictional financial assumptions", { exact: true }).click();
    await option(page, "Cost per review", "$60").check();
    await expect(page.getByText(/\$60\.00 per review/)).toBeVisible();
    await page.getByRole("button", { name: "Reset scenario" }).click();
    await expect(option(page, "Cost per review", "$30")).toBeChecked();
    await page.getByText("Fictional financial assumptions", { exact: true }).click();
    if (root === staticRoot) {
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.screenshot({ path: `test-results/release/${info.project.name}/static/desktop/planner-workflow.png` });
    }
    await navigate(page, "Analyst");
    await page.getByRole("button", { name: "Run query" }).click();
    await expect(page.getByRole("row", { name: /Uniform random.*1,009.*1.23 pp.*Design-aware/ })).toBeVisible();
    await page.getByRole("radio", { name: /Simulate a fictional budget/ }).check();
    await page.getByRole("button", { name: "Run query" }).click();
    await expect(page.getByText("-$3.75", { exact: true })).toBeVisible();
  }
});

test("local review verifies the chain and exposes case action history", async ({ page }, info) => {
  await page.goto(`${localRoot}/#/operations`);
  await page.getByRole("button", { name: "Intake sample batch" }).click();
  await page.getByLabel("Queue state").selectOption("queued");
  await expect(page.getByRole("table", { name: "Synthetic review queue" }).getByRole("row")).toHaveCount(3);
  await page.getByRole("button", { name: "Assign review", exact: true }).click();
  await page.getByText("Case actions", { exact: true }).click();
  await expect(page.getByRole("table", { name: "Persisted case actions" }).getByText("assign")).toBeVisible();
  await page.getByRole("button", { name: "Verify event chain" }).click();
  await expect(page.getByText(/Receipt projection and event chain verified/)).toBeVisible();
  await page.screenshot({ path: `test-results/porcelain/${info.project.name}/local-receipt.png` });
});

test("keyboard mobile navigation closes and restores focus, and load errors offer retry", async ({ page }, info) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ colorScheme: "dark" });
  await page.route("**/study.json", (route) => route.fulfill({ status: 503, body: "" }));
  await page.goto(`${staticRoot}/#/overview`);
  await expect(page.getByRole("button", { name: "Retry load" })).toBeVisible();
  await page.screenshot({ path: `test-results/porcelain/${info.project.name}/static/dark/mobile/study-error.png` });
  const toggle = page.getByRole("button", { name: "Open navigation" });
  await toggle.focus();
  await page.keyboard.press("Enter");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Overview", exact: true })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(toggle).toBeFocused();
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  await page.unroute("**/study.json");
  await page.getByRole("button", { name: "Retry load" }).click();
  await expect(page.getByRole("heading", { name: "Study overview" })).toBeVisible();
  await toggle.focus();
  await page.keyboard.press("Enter");
  await page.keyboard.press("Tab");
  await page.keyboard.press("Enter");
  await expect(page.locator("main")).toBeFocused();
});

test("theme follows the system before an explicit override and persists through navigation", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await page.goto(staticRoot);
  await expect(page.locator("html")).toHaveCSS("color-scheme", "dark");
  await page.emulateMedia({ colorScheme: "light" });
  await expect(page.locator("html")).toHaveCSS("color-scheme", "light");
  const toggle = page.getByRole("button", { name: "Switch to dark theme" });
  await toggle.focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("html")).toHaveCSS("color-scheme", "dark");
  await navigate(page, "Risk models");
  await page.reload();
  await expect(page.locator("html")).toHaveCSS("color-scheme", "dark");
});

test("chart values, financial sensitivity and review transitions are keyboard accessible", async ({ page }, info) => {
  await page.goto(staticRoot);
  const disclosure = page.getByText("Chart values", { exact: true });
  await disclosure.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("row", { name: /Greedy \(selected-only rate\).*16.87 pp.*36.77%/ })).toBeVisible();
  await navigate(page, "Financial scenarios");
  const slider = page.getByRole("slider", { name: /Adjust predicted disagreement/ });
  await slider.focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.locator("output")).toHaveText("-$2.88");
  await navigate(page, "Review simulation");
  await page.getByRole("button", { name: "Assign a review" }).focus();
  for (const next of ["Submit finding", "Advance clock", "Record correction", "Reset example", "Assign a review"]) {
    await page.keyboard.press("Enter");
    await expect(page.getByRole("button", { name: next })).toBeFocused();
    if (next === "Reset example") {
      await page.screenshot({ path: `test-results/porcelain/${info.project.name}/review-correction.png` });
    }
  }
});
