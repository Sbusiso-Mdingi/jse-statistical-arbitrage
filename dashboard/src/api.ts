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
    margin_oos?: { years: number; sbk_fail_years: number[]; ned_fail_years: number[] };
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

type SwitchScore = {
  trades: { opened: string; closed: string | null; method: "spread" | "copula"; side: string; gross_bps: number; net_cash_bps: number; net_futures_bps: number }[];
  complete: number;
  spread_trades: number;
  net_cash_bps: number | null;
  net_futures_bps: number | null;
  t_cash: number | null;
  t_futures: number | null;
  position: { open: false } | { open: true; method: "spread" | "copula"; opened: string; side: string };
};

/** The long-run relationship on a rolling half-year, which method the strategy uses, and both methods' live records. */
export type Switch = {
  frozen_on: string;
  score_from: string;
  window: number;
  crit: number;
  as_of: string;
  today: {
    eg: number;
    hedge_ratio: number;
    z: number;
    holds: boolean;
    mode: "spread" | "copula";
    last_spread_day: string | null;
    gate_open: boolean;
    last_gate_day: string | null;
  };
  segment: { from: string; to: string; slope: number; intercept: number };
  reference: Record<"design" | "validation_already_seen", {
    spread_mode_share: number;
    switch_vs_copula_t: number;
    switch: { cash: number; futures: number; trades: number };
    copula_alone: { cash: number; futures: number; trades: number };
  }>;
  series: { date: string[]; eg: (number | null)[]; mode: number[]; gate: number[] };
  spread_share_by_year: Record<string, number>;
  switch: SwitchScore;
  copula_alone: SwitchScore;
  /** The spread rule decided on the 16:00 price and filled in the closing auction. */
  spread_gate_1600?: SwitchScore & { score_from: string } | { available: false };
  /** The spread rule on prices corrected for dividends. */
  spread_gate_dividends?: SwitchScore & { score_from: string };
  spread_gate: SwitchScore & {
    crit: number;
    frozen_on: string;
    score_from: string;
    verdict_at: string;
    expected_live_bps: [number, number];
    development: {
      from: string;
      to: string;
      specifications_searched: number;
      trades: number;
      futures_bps: number;
      cash_bps: number;
      t_futures: number;
      median_bps: number;
      win: number;
      drop_top3_bps: number;
      mean_days: number;
      trades_per_year: number;
      eras: { from: string; to: string; trades: number; futures_bps: number }[];
      by_cutoff: Record<string, number>;
    };
  };
};
export const getSwitch = () => getJson<Switch>("/api/switch");

export type Schedule = "futures" | "cash";
export type PnlTrade = { opened: string; closed: string | null; net_futures_bps: number; net_cash_bps: number };
export type Pnl = {
  as_of: string;
  date: string[];
  score_from: string;
  development_end: string;
  last_refit: string | null;
  last_refit_from: string | null;
  strategies: Record<"spread_gate" | "switch" | "copula_alone", { cum: Record<Schedule, number[]>; trades: PnlTrade[] }>;
};

export const getPnl = () => getJson<Pnl>("/api/pnl");
