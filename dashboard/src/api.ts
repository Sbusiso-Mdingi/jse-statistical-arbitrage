export type Period = "live" | "walkforward" | "all";

export type Metrics = {
  total_return: number;
  cagr: number;
  sharpe: number;
  sortino: number;
  volatility: number;
  max_drawdown: number;
  trades: number;
  hit_rate: number | null;
  avg_hold_days: number | null;
  time_in_market: number;
  days: number;
  years: number;
};

export type Status = {
  freeze: string;
  as_of: string;
  source: "live" | "snapshot";
  fetched_at: string | null;
  error: string | null;
  prices: { sbk: number; ned: number } | null;
};

type Spec = { model: string; arma: string; dist: string; vix: boolean; bic: number };
type Copula = { family: number; name: string; par: number; par2: number; tau: number };

export type CostTier = "protocol" | "institutional" | "retail";
export type RuleParams = { entry: number; hold: number; cost_bps: number; costs: CostTier };
export const RULE_DEFAULTS: RuleParams = { entry: 90, hold: 5, cost_bps: 10, costs: "protocol" };

/** The instrument: Standard Bank against Nedbank on the score-driven copula, five-day hold, half of capital a side. */
export type PairBacktest = {
  strategy: "pair";
  period: Period;
  params: RuleParams & { round_trip_bps: number };
  start: string;
  end: string;
  metrics: Metrics;
  benchmark: Metrics;
  latest: { date: string; position: number; h: number };
  series: { date: string[]; equity: number[]; benchmark: number[]; position: number[]; h: number[]; level: number };
  trades: { open: string; close: string | null; side: string; return: number }[];
};

export type PairModel = {
  status: Status;
  fits: { train_end: string; sbk: Spec; ned: Spec; copula: Copula }[];
  latest: {
    train_end: string;
    sbk: Spec;
    ned: Spec;
    copula: Copula & { taildep: { lower: number; upper: number } };
    pit_ks: { sbk: number; ned: number };
  };
  pit: { walkforward: { u: number[]; v: number[] }; live: { u: number[]; v: number[] } };
  dependence: { model: "gas_t"; omega: number; beta: number; alpha: number; nu: number; rho_train_end: number; rho_live: number | null };
};

type Perf = { sharpe: number; sortino: number; cagr: number; mdd: number };
type Perf3 = { sharpe: number; cagr: number; mdd: number };
export type Research = {
  tests: {
    id: string;
    name: string;
    detail: string;
    pass_mark: string | null;
    passed?: boolean;
    design: Perf;
    validation: Perf;
    post_freeze: Perf;
    design_note?: string;
    edge_vs_h1?: { bps_per_year: number; t_stat: number };
    before_costs?: { design: Perf; validation: Perf };
    entries?: { design: number; validation: number; post_freeze: number };
  }[];
  cointegration: {
    engle_granger: { full_levels: number; full_logs: number; design_logs: number };
    crit5: number;
    rolling_share_rejecting: number;
    gregory_hansen: { level: number; regime: number };
    breaks: string[];
    segments: { from: string; to: string; slope: number }[];
  };
  decay: {
    banks: Record<string, string>;
    window: number;
    dates: string[];
    pairs: { a: string; b: string; acf: number[] }[];
    mean_acf: number[];
    reversal_by_year: { year: number; n: number; bps: number; se: number | null }[];
  };
  edge: {
    cost_round_trip_bps: number;
    hold: number;
    last_date: string;
    by_year: { year: number; n: number; bps: number; se: number; next_bps: number; next_se: number; partial: boolean }[];
    "2010_2019": { n: number; bps: number; se: number; next_bps: number };
    "2020_2026": { n: number; bps: number; se: number; next_bps: number };
    "2021_2026": { n: number; bps: number; se: number; next_bps: number };
    copula?: string;
  };
  costs?: {
    tiers: Record<CostTier, { label: string; round_trip_bps: number; design: Perf3; validation: Perf3; full: Perf3 }>;
    components_institutional: Record<string, number>;
    hold_until_normal: { avg_days_held: number; trades: number; tiers: Record<CostTier, { full: Perf3 }> };
  };
  redteam?: {
    lag_next_close_2010_2019_bps: number;
    lag_next_close_2021_2026_bps: number;
    lag_next_10am_2010_2019_bps: number;
    placebo_percentile_2010_2019: number;
    placebo_percentile_2021_2026: number;
    loo_best_year: number;
    loo_without_best_2010_2019_bps: number;
  };
  instrument?: {
    copula: string;
    validation_gain_per_day: number;
    dm_t: number;
    h_ks_p: number;
    static_h_ks_p: number;
    fires: number;
    rule: Record<"design" | "validation" | "post_freeze", { after: number; before: number }>;
    benchmark_walkforward_cagr: number;
  };
};

const BASE = import.meta.env.VITE_API_BASE ?? "";

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { signal });
  if (!res.ok) throw new Error(`Request failed (${res.status})`);
  return res.json();
}

export const getPairBacktest = (period: Period, p: RuleParams, signal?: AbortSignal) =>
  getJson<PairBacktest>(
    `/api/pair/backtest?${new URLSearchParams({ period, entry: String(p.entry), hold: String(p.hold), cost_bps: String(p.cost_bps), costs: p.costs })}`,
    signal,
  );
export const getPairModel = () => getJson<PairModel>("/api/pair/model");
export const getResearch = () => getJson<Research>("/api/research");
