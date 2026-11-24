import { describe, expect, it } from "vitest";
import { scenarioNet } from "./numbers";

describe("financial scenario", () => {
  it("calculates cents and rounds half away from zero", () => {
    expect(scenarioNet(30, 25_000, 35, 3_000)).toBe(-375);
    expect(scenarioNet(1, 50, 100, 0)).toBe(1);
    expect(scenarioNet(1, 50, 100, 1)).toBe(-1);
  });
  it("rejects out-of-domain inputs", () => {
    expect(scenarioNet(101, 50, 100, 0)).toBeNull();
    expect(scenarioNet(10, Number.NaN, 100, 0)).toBeNull();
  });
});
