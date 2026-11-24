export type Part = "Part B" | "DME";
export type Nullable = number | null;
export type Claim = { part: Part; provider_type: string; visible_lines: number; provider_types: number };
export type Interval = { bounds: [number, number] | null; replicates: number; confidence: number };
export type Study = {
  schema: 1; protocol: string; freeze_commit: string; freeze_sha256: string;
  cohorts: Cohort[]; models: ModelCohort[];
  selection: { challenger: string; scoring: string };
  split: Record<string, number>;
  finance: FinanceCohort[];
  finance_primary: Omit<ScenarioRow, "budget_percent" | "plans">;
  replay: {
    seeds: number; timeline: Timeline[]; policies: Policy[];
    conclusions: {
      status: string;
      components: {
        hybrid_vs_greedy: { rmse_improvement: number; yield_ratio: number; supported: boolean };
        stratified_vs_uniform: { rmse_improvement: number; coverage: number; supported: boolean };
        ipw_vs_unweighted: { mc_interval: [number, number]; brier_improvement: Simulation; supported: boolean };
      };
    };
  };
  validation: { active: string; status: string; promotion: string; cohorts: Monitor[];
                thresholds: Record<string, number> };
  ledger: { run: string; sha256: string }[];
};
export type Cohort = {
  year: number; version: string; rows: number; in_scope_rows: number; claims: number;
  disagreements: number; parts: Record<Part, { claims: number; visible_lines: number; missing_provider: Nullable }>;
};
export type Model = {
  ap: Nullable; auroc: Nullable; brier: Nullable; ece: Nullable;
  calibration_intercept: Nullable; calibration_slope: Nullable;
  calibration: { bin: number; claims: number; observed: number; predicted: number }[];
  pr_curve: [number, number][];
  capacity: Record<string, { findings: number; reviews: number; precision: Nullable; recall: Nullable }>;
};
export type ModelCohort = {
  year: number; claims: number; findings: number; excluded_unknown: number;
  models: Record<string, Model>;
  comparison: { status: string; average_precision_delta: number; precision_at_5_delta: number;
                intervals: Record<string, Interval> };
};
export type Plan = {
  reviews: number; capacity: number; findings: number; yield_rate: Nullable; nonfinding_per_finding: Nullable;
  minutes: number; expected_scenario_net_cents: number; observed_scenario_net_cents: number;
  observed_weighted_findings_cents: number; review_share: Record<Part, Nullable>;
};
export type ScenarioRow = {
  exposure: string; relevant_percent: number; review_cost_cents: number; budget_percent: number;
  plans: Record<string, Plan>;
};
export type FinanceCohort = {
  year: number; eligible: number; grid: ScenarioRow[];
  primary: { status: string; relative_weighted_gain: number; burden_delta: number;
             intervals: Record<string, Interval>; constrained: Plan & { exploratory_reviews: number } };
};
export type Simulation = { mean: Nullable; mcse: Nullable; quantiles: number[] | null; n: number };
export type Policy = {
  year: number; budget_percent: number; strategy: string; weight: string; review_count: number; learning_waves: number;
  seeds: number;
  metrics: {
    yield_rate: Simulation; findings: Simulation; cumulative_findings: Simulation; burden: Simulation;
    truth: Simulation; ess: Simulation; training_ess: Simulation; coverage: Simulation; brier: Simulation;
    ap: Simulation; ece: Simulation; naive_bias: Simulation; ht_bias: Simulation;
    naive_rmse: Nullable; ht_rmse: Nullable;
  };
};
type Timeline = { year: number; decision: string; label_available: string; claims: number; unknown_outcomes: number };
type Monitor = {
  year: number; drift: Record<string, number>; covariate_alerts: string[]; brier: number; observed_rate: number;
  labelled_claims: number;
};
export type Score = {
  calibrated_risk: number; model: string; status: string; feature_schema: string; input_support: string;
  explanation: { method: string; case_raw_risk: number; part_raw_risk?: number; provider_raw_risk?: number };
};
export type LocalPlan = {
  summary: { reviews: number; expected_scenario_net_cents: number; minutes: number; unused_capacity: number;
             unused_minutes?: number };
  model: string; selected_input_positions: number[]; exploration_count: number; scope: string;
};
export type Job = {
  id: string; status: string; seeds_requested: number; seeds_completed: number; error?: string;
  summary?: { status: string; seeds: number };
};

export async function studyData(signal: AbortSignal): Promise<Study> {
  const endpoint = new URL("./study.json", window.location.href);
  const response = await fetch(endpoint, { signal });
  if (!response.ok) throw new Error("The aggregate study file could not be loaded.");
  const value: Partial<Study> | null = await response.json().catch(() => null);
  if (value?.schema !== 1 || !value.cohorts?.length || !value.models?.length || !value.finance?.length ||
      !value.finance_primary || !value.selection || !value.split || !value.validation?.cohorts ||
      !value.replay?.timeline?.length || !value.replay.policies?.length || !value.replay.conclusions?.components ||
      !Array.isArray(value.ledger)) {
    throw new Error("The aggregate study file uses an unsupported schema.");
  }
  return value as Study;
}

export async function localRequest<T>(path: string, data?: unknown): Promise<T> {
  const response = await fetch(`http://127.0.0.1:8000${path}`, {
    method: data === undefined ? "GET" : "POST",
    headers: data === undefined ? undefined : { "content-type": "application/json" },
    body: data === undefined ? undefined : JSON.stringify(data),
    signal: AbortSignal.timeout(10_000),
  });
  const value = await response.json().catch(() => null);
  if (!response.ok || value === null) throw new Error(value?.error?.message ?? "The local request did not complete.");
  return value as T;
}
