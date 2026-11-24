import type { Interval, Nullable } from "./contracts";

export const number = (value: Nullable | undefined, decimals = 0) => value == null ? "Unavailable" :
  new Intl.NumberFormat("en-US", { maximumFractionDigits: decimals, minimumFractionDigits: decimals }).format(value);
export const percent = (value: Nullable | undefined, decimals = 1) => value == null ? "Unavailable" : `${number(value * 100, decimals)}%`;
export const cents = (value: Nullable | undefined) => value == null ? "Unavailable" :
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value / 100);
export const interval = (value: Interval | undefined, formatter = percent) => value?.bounds
  ? `${formatter(value.bounds[0])} to ${formatter(value.bounds[1])}` : "Unavailable";
export const label = (name: string) => ({
  lookup: "Hierarchical lookup", historical: "Historical rates", global: "Overall rate",
  "xgb-4": "Boosted trees · depth 4", "xgb-2": "Boosted trees · depth 2",
  "logistic-no-counts": "Logistic · counts excluded",
  uniform: "Uniform random", greedy: "Greedy risk", "hybrid-5": "5% exploration",
  "hybrid-10": "10% exploration", "hybrid-20": "20% exploration", stratified: "Score-stratified",
  ipw: "Inverse propensity", clipped: "Clipped weights", unweighted: "Unweighted",
  risk: "Risk only", value: "Scenario value", value_per_minute: "Value per minute",
}[name] ?? name.replaceAll("_", " ").replace("logistic-", "Logistic · C="));

export function scenarioNet(riskPercent: number, exposure: number, relevantPercent: number, cost: number) {
  if (![riskPercent, exposure, relevantPercent, cost].every(Number.isSafeInteger) ||
      riskPercent < 0 || riskPercent > 100 || relevantPercent < 0 || relevantPercent > 100 ||
      exposure < 0 || exposure > 10_000_000 || cost < 0 || cost > 10_000_000) return null;
  const numerator = riskPercent * exposure * relevantPercent - cost * 10_000;
  return Math.sign(numerator) * Math.floor((Math.abs(numerator) + 5_000) / 10_000);
}
