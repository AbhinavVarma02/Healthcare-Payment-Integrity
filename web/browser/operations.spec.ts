
import { expect, test } from "@playwright/test";

const staticUrl = "http://127.0.0.1:4173";
const localUrl = "http://127.0.0.1:5173";

test("aggregate release exposes the policy lab and a self-contained synthetic review", async ({ page }) => {
  const requests: string[] = [];
  const errors: string[] = [];
  page.on("request", (request) => requests.push(request.url()));
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto(`${staticUrl}/#/evidence`);
  await expect(page.getByRole("heading", { name: "Review policy and model updates" })).toBeVisible();
  await expect(page.getByRole("row", { name: /Matched fixed.*1,009/ })).toBeVisible();
  await page.getByRole("radiogroup", { name: "Reporting year" }).getByRole("radio", { name: "2024", exact: true }).check();
  await expect(page.getByRole("img", { name: "Estimation error and review yield by policy" })).toBeVisible();
  await page.screenshot({ path: "test-results/research-lab.png", fullPage: true });
  await page.getByRole("navigation", { name: "Workspace" }).getByRole("link", { name: "Review simulation" }).click();
  await page.getByRole("button", { name: "Assign a review" }).click();
  await page.getByRole("button", { name: "Submit finding" }).click();
  await expect(page.getByRole("table", { name: "Revealed illustrative findings" })).toHaveCount(0);
  await page.getByRole("button", { name: "Advance clock" }).click();
  await expect(page.getByRole("row", { name: /1 agree 1/ })).toBeVisible();
  await page.getByRole("button", { name: "Record correction" }).click();
  await expect(page.getByRole("row", { name: /2 disagree 2/ })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: "Follow a claim review" })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.body.scrollWidth)).toBe(390);
  expect(requests.every((url) => url.startsWith(staticUrl) || url.startsWith("data:"))).toBeTruthy();
  expect(errors).toEqual([]);
});

test("local operations workflow records delayed and corrected findings with receipts", async ({ page }) => {
  await page.goto(`${localUrl}/#/operations`);
  await expect(page.getByRole("heading", { name: "Review operations" })).toBeVisible();
  await page.getByRole("button", { name: "Intake sample batch" }).click();
  await expect(page.getByText("Fictional batch scored and allocated.")).toBeVisible();
  await expect(page.getByRole("table", { name: "Synthetic review queue" })).toBeVisible();
  await page.getByRole("button", { name: "Assign review", exact: true }).click();
  await page.getByRole("button", { name: "Submit delayed finding" }).click();
  await expect(page.getByText("No finding available at this simulation tick.")).toBeVisible();
  await page.getByRole("button", { name: "Advance clock one tick" }).click();
  await expect(page.getByRole("table", { name: "Finding history" })).toBeVisible();
  await page.getByRole("combobox", { name: "Finding", exact: true }).selectOption("disagree");
  await page.getByRole("button", { name: "Record correction" }).click();
  await expect(page.getByRole("table", { name: "Finding history" }).getByRole("row")).toHaveCount(2);
  await page.getByRole("button", { name: "Advance clock one tick" }).click();
  await expect(page.getByRole("table", { name: "Finding history" }).getByRole("row")).toHaveCount(3);
  await page.getByRole("button", { name: "Explain selected score" }).click();
  await expect(page.getByText(/Calibrated risk/)).toBeVisible();
  await page.reload();
  await expect(page.getByRole("table", { name: "Finding history" }).getByRole("row")).toHaveCount(3);
  await page.screenshot({ path: "test-results/operations-desktop.png", fullPage: true });
});
