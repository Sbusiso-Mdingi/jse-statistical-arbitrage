export type Period = "live" | "walkforward" | "all";

export type Params = {
  rule: "probability" | "mispricing";
  entry: number;
  exit: number;
  vol_filter: boolean;
  vol_pct: number;
  threshold: number;
  cost_bps: number;
};

export const DEFAULTS: Params = {
  rule: "probability",
  entry: 90,
  exit: 50,
  vol_filter: true,
  vol_pct: 80,
  threshold: 0.6,
  cost_bps: 10,
};

export type Metrics = {
  total_return: number;
  cagr: number;
  sharpe: number;
  volatility: number;
  max_drawdown: number;
  trades: number;
  hit_rate: number | null;
  avg_hold_days: number | null;
  time_in_market: number;
  days: number;
  years: number;
};

export type Backtest = {
  period: Period;
  start: string;
  end: string;
  metrics: Metrics;
  benchmark: Metrics;
  latest: { date: string; position: number; h_ns: number; h_sn: number };
  series: {
    date: string[];
    equity: number[];
    benchmark: number[];
    position: number[];
    h_ns: number[];
    h_sn: number[];
    open_level: number[];
    close_level: number[];
  };
  trades: { open: string; close: string | null; side: string; return: number }[];
};

export type Spec = { model: string; arma: string; dist: string; vix: boolean; coef: Record<string, number>; bic: number };

export type Model = {
  status: {
    freeze: string;
    as_of: string;
    source: "live" | "snapshot";
    fetched_at: string | null;
    error: string | null;
    prices: { sbk: number; ned: number } | null;
  };
  folds: {
    id: number;
    train_end: string;
    trade_start: string;
    trade_end: string;
    final: boolean;
    sbk: Spec;
    ned: Spec;
    copula: { family: number; name: string; par: number; par2: number; tau: number; taildep: { lower: number; upper: number } };
    pit_ks: { sbk: number; ned: number };
  }[];
  pit: { walkforward: { u: number[]; v: number[] }; live: { u: number[]; v: number[]; date: string[] } };
};

const BASE = import.meta.env.VITE_API_BASE ?? "";

export async function getBacktest(period: Period, p: Params, signal?: AbortSignal): Promise<Backtest> {
  const q = new URLSearchParams({ period, ...Object.fromEntries(Object.entries(p).map(([k, v]) => [k, String(v)])) });
  const res = await fetch(`${BASE}/api/backtest?${q}`, { signal });
  if (!res.ok) throw new Error(`Backtest request failed (${res.status})`);
  return res.json();
}

export async function getModel(): Promise<Model> {
  const res = await fetch(`${BASE}/api/model`);
  if (!res.ok) throw new Error(`Model request failed (${res.status})`);
  return res.json();
}

export type BasketParams = { entry: number; hold: number; cost_bps: number };
export const BASKET_DEFAULTS: BasketParams = { entry: 90, hold: 5, cost_bps: 10 };

export type BasketBacktest = Omit<Backtest, "latest" | "series"> & {
  latest: { date: string; position: number; h: number };
  series: { date: string[]; equity: number[]; benchmark: number[]; position: number[]; h: number[]; level: number };
};

type ShortSpec = Omit<Spec, "coef">;
export type BasketModel = {
  status: Model["status"];
  basket: string[];
  fits: { train_end: string; sbk: ShortSpec; bsk: ShortSpec; copula: { family: number; name: string; par: number; par2: number; tau: number } }[];
  latest: {
    train_end: string;
    sbk: ShortSpec;
    bsk: ShortSpec;
    copula: Model["folds"][number]["copula"];
    pit_ks: { sbk: number; bsk: number };
  };
  pit: { walkforward: { u: number[]; v: number[] }; live: { u: number[]; v: number[] } };
};

type Perf = { sharpe: number; cagr: number; mdd: number };
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
  }[];
  decay: {
    banks: Record<string, string>;
    window: number;
    dates: string[];
    pairs: { a: string; b: string; acf: number[] }[];
    mean_acf: number[];
    reversal_by_year: { year: number; n: number; bps: number; se: number | null }[];
  };
};

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { signal });
  if (!res.ok) throw new Error(`Request failed (${res.status})`);
  return res.json();
}

export const getBasketBacktest = (period: Period, p: BasketParams, signal?: AbortSignal) =>
  getJson<BasketBacktest>(
    `/api/basket/backtest?${new URLSearchParams({ period, entry: String(p.entry), hold: String(p.hold), cost_bps: String(p.cost_bps) })}`,
    signal,
  );
export const getBasketModel = () => getJson<BasketModel>("/api/basket/model");
export const getResearch = () => getJson<Research>("/api/research");
