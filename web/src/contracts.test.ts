import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { localRequest, studyData } from "./contracts";
import approved from "../public/study.json";

const signal = new AbortController().signal;
const fake = vi.fn<typeof fetch>();

beforeEach(() => {
  fake.mockReset();
  vi.stubGlobal("fetch", fake);
  vi.stubGlobal("window", { location: { href: "https://site.invalid/demo/#/planner" } });
});

afterEach(() => vi.unstubAllGlobals());

describe("released aggregate adapter", () => {
  it("reads approved bytes relative to a nested static mount and propagates the abort signal", async () => {
    fake.mockResolvedValue(Response.json(approved));
    const result = await studyData(signal);
    expect(fake.mock.calls[0]).toEqual([new URL("https://site.invalid/demo/study.json"), { signal }]);
    expect(result.cohorts.reduce((sum, row) => sum + row.claims, 0)).toBe(199052);
  });

  it("reports a failed aggregate request before trying to parse it", async () => {
    fake.mockResolvedValue(new Response("Unavailable", { status: 503 }));
    await expect(studyData(signal)).rejects.toThrow("could not be loaded");
  });

  it.each([
    ["unrecognized-schema", { ...approved, schema: 2 }],
    ["missing-cohort", { ...approved, cohorts: [] }],
    ["missing-models", { ...approved, models: [] }],
    ["missing-finance", { ...approved, finance: [] }],
    ["missing-finance-primary", { ...approved, finance_primary: null }],
    ["missing-selection", { ...approved, selection: null }],
    ["missing-split", { ...approved, split: null }],
    ["missing-validation", { ...approved, validation: null }],
    ["empty-replay", { ...approved, replay: { ...approved.replay, timeline: [] } }],
    ["missing-policies", { ...approved, replay: { ...approved.replay, policies: [] } }],
    ["missing-conclusions", { ...approved, replay: { ...approved.replay, conclusions: null } }],
    ["corrupt-ledger", { ...approved, ledger: {} }],
  ])("rejects an aggregate with %s", async (_id, aggregate) => {
    fake.mockResolvedValue(Response.json(aggregate));
    await expect(studyData(signal)).rejects.toThrow("unsupported schema");
  });

  it("reports a stable error for malformed JSON", async () => {
    fake.mockResolvedValue(new Response("<!doctype html>"));
    await expect(studyData(signal)).rejects.toThrow("unsupported schema");
  });
});

describe("loopback data adapter", () => {
  it("uses a bounded GET for read-only local resources", async () => {
    fake.mockResolvedValue(Response.json({ status: "ready" }));
    await expect(localRequest("/ready")).resolves.toEqual({ status: "ready" });
    expect(fake).toHaveBeenCalledWith("http://127.0.0.1:8000/ready", {
      method: "GET", headers: undefined, body: undefined, signal: expect.any(AbortSignal),
    });
  });

  it("uses JSON for explicitly submitted command bodies", async () => {
    fake.mockResolvedValue(Response.json({ status: "ok" }));
    await localRequest("/v1/analyst/tool?role=analyst", { tool: "report" });
    expect(fake).toHaveBeenCalledWith("http://127.0.0.1:8000/v1/analyst/tool?role=analyst", {
      method: "POST", headers: { "content-type": "application/json" }, body: '{"tool":"report"}',
      signal: expect.any(AbortSignal),
    });
  });

  it("returns a safe bounded service error with actionable detail", async () => {
    fake.mockResolvedValue(Response.json({ error: { message: "The local model is unavailable." } }, { status: 503 }));
    await expect(localRequest("/ready")).rejects.toThrow("The local model is unavailable.");
  });

  it("returns a fallback error when a local port responds with HTML", async () => {
    fake.mockResolvedValue(new Response("<!doctype html>"));
    await expect(localRequest("/ready")).rejects.toThrow("The local request did not complete.");
  });
});
