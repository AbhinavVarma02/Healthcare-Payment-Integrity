export type Finding = "agree" | "disagree";

export const reviewSteps = ["Intake available", "Review assigned", "Finding pending", "Finding revealed", "Correction recorded"] as const;
export const reviewActions = ["Assign a review", "Submit finding", "Advance clock", "Record correction"] as const;

export function reviewOutcomes(step: number, finding: Finding): [number, Finding, number][] {
  if (step < 3) return [];
  const initial: [number, Finding, number] = [1, finding, 1];
  if (step === 3) return [initial];
  return [initial, [2, finding === "agree" ? "disagree" : "agree", 2]];
}
