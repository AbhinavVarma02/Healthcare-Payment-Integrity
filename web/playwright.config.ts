import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./browser",
  workers: 1,
  timeout: 25_000,
  use: { channel: "msedge", headless: true, trace: "retain-on-failure" },
  projects: [{ name: "edge" }],
});
