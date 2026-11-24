import { expect, it } from "vitest";
import { reviewOutcomes } from "./review-state";

it.each([0, 1, 2])("keeps findings hidden in workflow step %i", (step) => {
  expect(reviewOutcomes(step, "agree")).toEqual([]);
});

it("reveals only the original finding at the first eligible tick", () => {
  expect(reviewOutcomes(3, "disagree")).toEqual([[1, "disagree", 1]]);
});

it.each([
  ["agree", "disagree"],
  ["disagree", "agree"],
] as const)("retains original %s after correction to %s", (original, correction) => {
  expect(reviewOutcomes(4, original)).toEqual([[1, original, 1], [2, correction, 2]]);
});
