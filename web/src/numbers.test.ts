import { describe, expect, it } from "vitest";
import { cents, interval, label, number, percent, points, scenarioNet } from "./numbers";

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
describe("decision display units and numeric bounds", () => {
  it("distinguishes an absolute error in points from a percentage", () => {
    expect(points(0.03892637788910659)).toBe("3.89 pp");
    expect(percent(0.959, 1)).toBe("95.9%");
  });

  it("keeps unavailable values distinct from zero", () => {
    expect(cents(null)).toBe("Unavailable");
    expect(number(undefined)).toBe("Unavailable");
    expect(percent(null)).toBe("Unavailable");
    expect(points(null)).toBe("Unavailable");
    expect(interval(undefined)).toBe("Unavailable");
    expect(cents(0)).toBe("$0.00");
  });

  it("retains signed uncertainty intervals and policy labels", () => {
    expect(interval({ bounds: [-0.026, 0.0782], replicates: 400, confidence: 0.975 }, (x) =>
      percent(x, 2))).toBe("-2.60% to 7.82%");
    expect(label("hybrid-10")).toBe("10% exploration");
    expect(label("logistic-2")).toBe("Logistic · C=2");
  });

  it.each([
    [-1, 100, 35, 30], [101, 100, 35, 30], [30, -100, 35, 30], [30, 10000001, 35, 30],
    [30, 100, -1, 30], [30, 100, 101, 30], [30, 100, 35, -1], [30, 100, 35, 10000001],
    [30.1, 100, 35, 30],
  ])("rejects invalid monetary arguments (%i, %i, %i, %i)", (risk, exposure, relevance, cost) => {
    expect(scenarioNet(risk, exposure, relevance, cost)).toBeNull();
  });
});
