import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./browser",
  workers: 1,
  timeout: 25_000,
  use: { headless: true, trace: "retain-on-failure" },
  projects: [
    { name: "edge", use: { channel: "msedge" } },
    { name: "firefox", use: { browserName: "firefox" } },
  ],
});
