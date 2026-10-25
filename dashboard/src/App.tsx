import { useEffect, useState } from "react";
import {
  BASKET_DEFAULTS,
  DEFAULTS,
  getBacktest,
  getBasketBacktest,
  getBasketModel,
  getModel,
  getResearch,
  type Backtest,
  type BasketBacktest,
  type BasketModel,
  type BasketParams,
  type Model,
  type Params,
  type Period,
  type Research,
} from "./api";
import { DecayChart, EquityChart, PitScatter, ReversalBars, SignalChart } from "./charts";
import { fmtDate, num, pct, side } from "./format";

const PERIODS: { id: Period; label: string }[] = [
  { id: "walkforward", label: "Walk-forward, 2010 to March 2026" },
  { id: "live", label: "Unseen since 1 April 2026" },
  { id: "all", label: "Full record" },
];

const MODEL_NAMES: Record<string, string> = { sGARCH: "GARCH", gjrGARCH: "GJR-GARCH", eGARCH: "EGARCH" };
type Strategy = "basket" | "pair";
const specLabel = (s: { arma: string; model: string; dist: string; vix: boolean }) =>
  `ARMA(${s.arma})-${MODEL_NAMES[s.model] ?? s.model}(1,1) ${s.dist === "std" ? "Student t" : "normal"}${s.vix ? " + VIX" : ""}`;

function useDebounced<T>(value: T, ms: number) {
  const [v, setV] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setV(value), ms);
    return () => clearTimeout(id);
  }, [value, ms]);
  return v;
}

function Slider({
  label,
  value,
  min,
  max,
  step = 1,
  format,
  onChange,
  disabled,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  format: (v: number) => string;
  onChange: (v: number) => void;
  disabled?: boolean;
}) {
  return (
    <div className="control" style={{ opacity: disabled ? 0.45 : 1 }}>
      <label>
        {label} <output>{format(value)}</output>
      </label>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(Number(e.target.value))}
        aria-label={label}
      />
    </div>
  );
}

function Metric({ value, label, sub, negative }: { value: string; label: string; sub?: string; negative?: boolean }) {
  return (
    <div className="metric">
      <div className={`value${negative ? " neg" : ""}`}>{value}</div>
      <div className="label">{label}</div>
      {sub && <div className="sub">{sub}</div>}
    </div>
  );
}

function useBacktest<P, B>(period: Period, params: P, load: (period: Period, p: P, s: AbortSignal) => Promise<B>) {
  const [bt, setBt] = useState<B | null>(null);
  const [error, setError] = useState<string | null>(null);
  const debounced = useDebounced(params, 200);
  useEffect(() => {
    const ctl = new AbortController();
    load(period, debounced, ctl.signal)
      .then((r) => {
        setBt(r);
        setError(null);
      })
      .catch((e) => e.name !== "AbortError" && setError(String(e.message ?? e)));
    return () => ctl.abort();
  }, [period, debounced, load]);
  return { bt, error };
}

function Performance({ bt, costBps, benchmarkLabel }: { bt: Backtest | BasketBacktest; costBps: number; benchmarkLabel: string }) {
  const m = bt.metrics;
  const shortPeriod = m.years < 1;
  // Two standard deviations of the total return of a zero-mean strategy with this volatility, over this span.
  const band = 2 * m.volatility * Math.sqrt(m.years);
  return (
    <>
      <section className="metrics" aria-label="Performance">
        <Metric value={pct(m.total_return)} label="Total return" negative={m.total_return < 0} sub={`${fmtDate(bt.start)} to ${fmtDate(bt.end)}`} />
        <Metric value={pct(m.cagr)} label="Annualised (CAGR)" negative={m.cagr < 0} />
        <Metric value={num(m.sharpe)} label="Sharpe ratio" negative={m.sharpe < 0} sub={`Sortino ${num(m.sortino)} · annualised, no risk-free rate`} />
        <Metric value={pct(m.max_drawdown)} label="Max drawdown" negative />
        <Metric value={String(m.trades)} label="Trades" sub={m.avg_hold_days != null ? `Average ${m.avg_hold_days.toFixed(1)} days held` : undefined} />
        <Metric value={pct(m.hit_rate, 0)} label="Winning trades" sub={`In the market ${pct(m.time_in_market, 0)} of days`} />
      </section>
      <p className="note">
        {shortPeriod
          ? `Only ${Math.round(m.years * 12)} months of unseen data so far, so the annualised figures will move as each session is added. ` +
            `At this volatility, a strategy with no edge at all would end this many months between ${pct(-band)} and ${pct(band)} about 95% of the time. `
          : ""}
        Returns are net of {costBps} bps per leg on every change of position, with each side sized at half of capital.{" "}
        {benchmarkLabel} returned {pct(bt.benchmark.total_return)} over the same dates.
      </p>
    </>
  );
}

function EquityPanel({ bt, period, other, benchmarkLabel }: { bt: Backtest | BasketBacktest; period: Period; other: string; benchmarkLabel: string }) {
  const [showBench, setShowBench] = useState(false);
  return (
    <section className="panel">
      <div className="panel-head">
        <h2 className="serif">
          Growth of <em>R1</em>
        </h2>
        <div className="legend">
          <span style={{ color: "var(--primary)" }}>
            <i />
            Strategy, after costs
          </span>
          <label className="toggle" style={{ fontFamily: "var(--font-mono)", fontSize: 11 }}>
            <input type="checkbox" checked={showBench} onChange={(e) => setShowBench(e.target.checked)} />
            {benchmarkLabel}
          </label>
          <span style={{ color: "var(--primary)" }}>■ Long SBK</span>
          <span style={{ color: "#b58b3c" }}>■ Long {other}</span>
        </div>
      </div>
      <EquityChart
        dates={bt.series.date}
        equity={bt.series.equity}
        benchmark={bt.series.benchmark}
        position={bt.series.position}
        showBenchmark={showBench}
        marker={period === "all" ? "2026-04-01" : undefined}
      />
    </section>
  );
}

function Trades({ trades }: { trades: { open: string; close: string | null; side: string; return: number }[] }) {
  if (!trades.length) return null;
  return (
    <section className="panel">
      <div className="panel-head">
        <h2 className="serif">
          Recent <em>trades</em>
        </h2>
        <span className="legend">
          Showing {Math.min(12, trades.length)} of {trades.length}
        </span>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Opened</th>
              <th>Closed</th>
              <th>Position</th>
              <th className="num">Return</th>
            </tr>
          </thead>
          <tbody>
            {trades
              .slice(-12)
              .reverse()
              .map((t) => (
                <tr key={t.open}>
                  <td className="mono">{t.open}</td>
                  <td className="mono">{t.close ?? "Open"}</td>
                  <td>{t.side}</td>
                  <td className="num" style={{ color: t.return < 0 ? "var(--negative)" : undefined }}>
                    {pct(t.return, 2)}
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Loading({ error, ready }: { error: string | null; ready: boolean }) {
  if (ready) return null;
  return error ? <p className="loading">Could not load the strategy: {error}</p> : <p className="loading">Filtering the latest prices…</p>;
}

function BasketView({ period }: { period: Period }) {
  const [params, setParams] = useState<BasketParams>(BASKET_DEFAULTS);
  const [model, setModel] = useState<BasketModel | null>(null);
  const { bt, error } = useBacktest(period, params, getBasketBacktest);
  const set = <K extends keyof BasketParams>(k: K, v: BasketParams[K]) => setParams((p) => ({ ...p, [k]: v }));
  useEffect(() => {
    getBasketModel().then(setModel).catch(() => undefined);
  }, []);
  const isDefault = JSON.stringify(params) === JSON.stringify(BASKET_DEFAULTS);
  const latest = model?.latest;
  const level = bt ? bt.series.date.map(() => bt.series.level) : [];

  return (
    <>
      <section className="controls" aria-label="Strategy settings">
        <Slider label="Open above" value={params.entry} min={75} max={99} format={(v) => `${v}th pct`} onChange={(v) => set("entry", v)} />
        <Slider label="Hold for" value={params.hold} min={1} max={20} format={(v) => `${v} day${v === 1 ? "" : "s"}`} onChange={(v) => set("hold", v)} />
        <Slider label="Cost per leg" value={params.cost_bps} min={0} max={50} format={(v) => `${v} bps`} onChange={(v) => set("cost_bps", v)} />
        {!isDefault && (
          <button className="reset" onClick={() => setParams(BASKET_DEFAULTS)}>
            Reset to the pre-registered settings
          </button>
        )}
      </section>
      <Loading error={error} ready={!!bt} />
      {bt && (
        <>
          <Performance bt={bt} costBps={params.cost_bps} benchmarkLabel="Buy and hold, half SBK and half the basket," />
          <EquityPanel bt={bt} period={period} other="basket" benchmarkLabel="Buy and hold SBK and the basket" />
          <section className="panel split">
            <div>
              <div className="panel-head">
                <h2 className="serif">
                  The signal, <em>day by day</em>
                </h2>
              </div>
              <SignalChart dates={bt.series.date} h={bt.series.h} open={level} position={bt.series.position} />
              <p className="note">
                Each dot is P(basket’s return ≤ today’s | Standard Bank’s return), from the copula fitted at the previous month
                end. Near 1, the other banks rose more than Standard Bank implies, so the rule buys Standard Bank and sells the
                basket. Dashed lines are the opening thresholds; a position runs for the holding period after the latest signal.
              </p>
            </div>
            <div className="signal-card">
              <p className="eyebrow">Latest close · {fmtDate(bt.latest.date)}</p>
              <p className="big">{bt.latest.position > 0 ? "Long SBK, short basket" : bt.latest.position < 0 ? "Short SBK, long basket" : "No position"}</p>
              <dl>
                <dt>P(basket | SBK)</dt>
                <dd>{bt.latest.h.toFixed(3)}</dd>
                <dt>Opens beyond</dt>
                <dd>
                  {(0.5 - bt.series.level).toFixed(3)} or {(0.5 + bt.series.level).toFixed(3)}
                </dd>
                {latest && (
                  <>
                    <dt>Model fitted to</dt>
                    <dd>{latest.train_end}</dd>
                  </>
                )}
              </dl>
              <p className="note">Research output, not a recommendation. The position shown is what the rule would hold into the next session.</p>
            </div>
          </section>
        </>
      )}
      {model && latest && (
        <>
          <section className="panel split">
            <div>
              <div className="panel-head">
                <h2 className="serif">
                  Standard Bank and <em>the sector</em>
                </h2>
                <div className="legend">
                  <span style={{ color: "var(--border-strong)" }}>● Walk-forward days</span>
                  <span style={{ color: "var(--primary)" }}>● Unseen days</span>
                </div>
              </div>
              <PitScatter history={model.pit.walkforward} live={model.pit.live} yLabel="Basket v → 1" />
            </div>
            <div>
              <p className="eyebrow">Latest model, fitted to {fmtDate(latest.train_end)}</p>
              <table style={{ marginTop: 14 }}>
                <tbody>
                  <tr>
                    <td>Standard Bank</td>
                    <td>{specLabel(latest.sbk)}</td>
                  </tr>
                  <tr>
                    <td>Basket</td>
                    <td>{specLabel(latest.bsk)}</td>
                  </tr>
                  <tr>
                    <td>Copula</td>
                    <td>
                      {latest.copula.name === "t" ? "Student t" : latest.copula.name}, ρ {latest.copula.par.toFixed(3)}
                      {latest.copula.par2 ? `, ν ${latest.copula.par2.toFixed(1)}` : ""}
                    </td>
                  </tr>
                  <tr>
                    <td>Kendall’s τ</td>
                    <td>{latest.copula.tau.toFixed(3)}</td>
                  </tr>
                  <tr>
                    <td>Tail dependence</td>
                    <td>{latest.copula.taildep.lower.toFixed(3)} in each tail</td>
                  </tr>
                  <tr>
                    <td>PIT uniformity (KS p)</td>
                    <td>
                      SBK {latest.pit_ks.sbk.toFixed(2)} · basket {latest.pit_ks.bsk.toFixed(2)}
                    </td>
                  </tr>
                </tbody>
              </table>
              <p className="note">
                The basket is an equal-weight, daily-rebalanced mix of FirstRand, Absa, Nedbank and Capitec. Specifications are
                chosen by BIC each December; parameters and the copula (by AIC) are re-estimated at every month end.
              </p>
            </div>
          </section>
          <section className="panel">
            <div className="panel-head">
              <h2 className="serif">
                Refitted every month, <em>never on the month it trades</em>
              </h2>
              <span className="legend">Last 12 of {model.fits.length} fits</span>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Fitted to</th>
                    <th>Standard Bank</th>
                    <th>Basket</th>
                    <th className="num">ρ</th>
                    <th className="num">ν</th>
                  </tr>
                </thead>
                <tbody>
                  {model.fits
                    .slice(-12)
                    .reverse()
                    .map((f, i) => (
                      <tr key={f.train_end} className={i === 0 ? "final" : undefined}>
                        <td className="mono">{f.train_end}</td>
                        <td>{specLabel(f.sbk)}</td>
                        <td>{specLabel(f.bsk)}</td>
                        <td className="num">{f.copula.par.toFixed(3)}</td>
                        <td className="num">{f.copula.par2 ? f.copula.par2.toFixed(1) : "–"}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
      {bt && <Trades trades={bt.trades} />}
    </>
  );
}

function PairView({ period }: { period: Period }) {
  const [params, setParams] = useState<Params>(DEFAULTS);
  const [model, setModel] = useState<Model | null>(null);
  const { bt, error } = useBacktest(period, params, getBacktest);
  const set = <K extends keyof Params>(k: K, v: Params[K]) => setParams((p) => ({ ...p, [k]: v }));
  useEffect(() => {
    getModel().then(setModel).catch(() => undefined);
  }, []);
  const isDefault = JSON.stringify(params) === JSON.stringify(DEFAULTS);
  const final = model?.folds.find((f) => f.final);

  return (
    <>
      <section className="controls" aria-label="Strategy settings">
        <div className="control">
          <span className="label">Signal rule</span>
          <div className="segmented">
            <button aria-pressed={params.rule === "probability"} onClick={() => set("rule", "probability")}>
              Daily probability
            </button>
            <button aria-pressed={params.rule === "mispricing"} onClick={() => set("rule", "mispricing")}>
              Mispricing index
            </button>
          </div>
        </div>
        {params.rule === "probability" ? (
          <>
            <Slider label="Open above" value={params.entry} min={75} max={99} format={(v) => `${v}th pct`} onChange={(v) => set("entry", v)} />
            <Slider label="Close below" value={params.exit} min={50} max={Math.min(80, params.entry - 1)} format={(v) => `${v}th pct`} onChange={(v) => set("exit", v)} />
          </>
        ) : (
          <Slider label="Index trigger" value={params.threshold} min={0.2} max={2} step={0.1} format={(v) => v.toFixed(1)} onChange={(v) => set("threshold", v)} />
        )}
        <div className="control">
          <span className="label">
            <span className="toggle">
              <input type="checkbox" checked={params.vol_filter} onChange={(e) => set("vol_filter", e.target.checked)} />
              Volatility filter
            </span>
            <output>{params.vol_filter ? `${params.vol_pct}th pct` : "off"}</output>
          </span>
          <input
            type="range"
            min={50}
            max={99}
            value={params.vol_pct}
            disabled={!params.vol_filter}
            onChange={(e) => set("vol_pct", Number(e.target.value))}
            aria-label="Volatility filter percentile"
          />
        </div>
        <Slider label="Cost per leg" value={params.cost_bps} min={0} max={50} format={(v) => `${v} bps`} onChange={(v) => set("cost_bps", v)} />
        {!isDefault && (
          <button className="reset" onClick={() => setParams(DEFAULTS)}>
            Reset to the report’s settings
          </button>
        )}
      </section>
      <Loading error={error} ready={!!bt} />
      {bt && (
        <>
          <Performance bt={bt} costBps={params.cost_bps} benchmarkLabel="Equal-weight buy and hold of both banks" />
          <EquityPanel bt={bt} period={period} other="NED" benchmarkLabel="Buy and hold both banks" />
          <section className="panel split">
            <div>
              <div className="panel-head">
                <h2 className="serif">
                  The signal, <em>day by day</em>
                </h2>
              </div>
              <SignalChart
                dates={bt.series.date}
                h={bt.series.h_ns}
                open={params.rule === "probability" ? bt.series.open_level : bt.series.h_ns.map(() => 0)}
                close={params.rule === "probability" ? bt.series.close_level : bt.series.h_ns.map(() => 0)}
                position={bt.series.position}
              />
              <p className="note">
                Each dot is P(Nedbank’s return ≤ today’s | Standard Bank’s return), from the copula. Near 1, Nedbank moved up more
                than Standard Bank implies; near 0, less. Dashed lines are the opening thresholds, solid lines the closing ones,
                both set from training data only.
              </p>
            </div>
            <div className="signal-card">
              <p className="eyebrow">Latest close · {fmtDate(bt.latest.date)}</p>
              <p className="big">{side(bt.latest.position)}</p>
              <dl>
                <dt>P(NED | SBK)</dt>
                <dd>{bt.latest.h_ns.toFixed(3)}</dd>
                <dt>P(SBK | NED)</dt>
                <dd>{bt.latest.h_sn.toFixed(3)}</dd>
                {model?.status.prices && (
                  <>
                    <dt>SBK adjusted close</dt>
                    <dd>R{(model.status.prices.sbk / 100).toFixed(2)}</dd>
                    <dt>NED adjusted close</dt>
                    <dd>R{(model.status.prices.ned / 100).toFixed(2)}</dd>
                  </>
                )}
              </dl>
              <p className="note">Research output, not a recommendation. The position shown is what the rule would hold into the next session.</p>
            </div>
          </section>
        </>
      )}
      {model && final && (
        <>
          <section className="panel split">
            <div>
              <div className="panel-head">
                <h2 className="serif">
                  How the banks <em>move together</em>
                </h2>
                <div className="legend">
                  <span style={{ color: "var(--border-strong)" }}>● Walk-forward days</span>
                  <span style={{ color: "var(--primary)" }}>● Unseen days</span>
                </div>
              </div>
              <PitScatter history={model.pit.walkforward} live={model.pit.live} />
            </div>
            <div>
              <p className="eyebrow">Frozen model, trained to {fmtDate(final.train_end)}</p>
              <table style={{ marginTop: 14 }}>
                <tbody>
                  <tr>
                    <td>Standard Bank</td>
                    <td>{specLabel(final.sbk)}</td>
                  </tr>
                  <tr>
                    <td>Nedbank</td>
                    <td>{specLabel(final.ned)}</td>
                  </tr>
                  <tr>
                    <td>Copula</td>
                    <td>
                      Student t, ρ {final.copula.par.toFixed(3)}, ν {final.copula.par2.toFixed(1)}
                    </td>
                  </tr>
                  <tr>
                    <td>Kendall’s τ</td>
                    <td>{final.copula.tau.toFixed(3)}</td>
                  </tr>
                  <tr>
                    <td>Tail dependence</td>
                    <td>{final.copula.taildep.lower.toFixed(3)} in each tail</td>
                  </tr>
                  <tr>
                    <td>PIT uniformity (KS p)</td>
                    <td>
                      SBK {final.pit_ks.sbk.toFixed(2)} · NED {final.pit_ks.ned.toFixed(2)}
                    </td>
                  </tr>
                </tbody>
              </table>
              <p className="note">
                The rule from the original group report. Each bank’s return is filtered through its own volatility model, turned
                into a probability, and the copula measures how those probabilities move together. Refitted once a year, then
                frozen on 31 March 2026.
              </p>
            </div>
          </section>
          <section className="panel">
            <div className="panel-head">
              <h2 className="serif">
                Refitted once a year, <em>never on the year it trades</em>
              </h2>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Trained to</th>
                    <th>Trades</th>
                    <th>Standard Bank</th>
                    <th>Nedbank</th>
                    <th className="num">ρ</th>
                    <th className="num">ν</th>
                  </tr>
                </thead>
                <tbody>
                  {[...model.folds].reverse().map((f) => (
                    <tr key={f.id} className={f.final ? "final" : undefined}>
                      <td className="mono">{f.train_end}</td>
                      <td className="mono">
                        {f.final ? `${f.trade_start} onward` : `${f.trade_start.slice(0, 4)}${f.trade_end.slice(5, 7) === "03" ? " Q1" : ""}`}
                      </td>
                      <td>{specLabel(f.sbk)}</td>
                      <td>{specLabel(f.ned)}</td>
                      <td className="num">{f.copula.par.toFixed(3)}</td>
                      <td className="num">{f.copula.par2.toFixed(1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
      {bt && <Trades trades={bt.trades} />}
    </>
  );
}

function ResearchSection() {
  const [r, setR] = useState<Research | null>(null);
  useEffect(() => {
    getResearch().then(setR).catch(() => undefined);
  }, []);
  if (!r) return null;
  const d = r.decay;
  const highlight = d.pairs.findIndex((p) => p.a === "sbk" && p.b === "ned");
  const at = (year: string) => d.mean_acf[d.dates.findIndex((x) => x >= year)];
  const early = d.reversal_by_year.filter((y) => y.year < 2020);
  const late = d.reversal_by_year.filter((y) => y.year >= 2020);
  const avg = (rows: typeof early) => rows.reduce((s, y) => s + y.bps * y.n, 0) / rows.reduce((s, y) => s + y.n, 0);
  const c = r.cointegration;
  const slopes = c.segments.map((s) => s.slope);
  return (
    <>
      <section className="panel">
        <div className="panel-head">
          <h2 className="serif">
            Cointegration, <em>tested first</em>
          </h2>
          <span className="legend">
            SBK and NED, {c.segments[0]!.from.slice(0, 4)} to March 2026
          </span>
        </div>
        <p className="note">
          The project began as a classic pairs trade, which needs the two prices to be cointegrated. They are not. The Engle-Granger
          statistic is {num(c.engle_granger.full_levels)} in price levels and {num(c.engle_granger.full_logs)} in logs, against a 5%
          critical value of {num(c.crit5)}, and Johansen and Phillips-Ouliaris tests agree at 5%. Two-year windows reject only{" "}
          {pct(c.rolling_share_rejecting, 0)} of the time, and allowing one break (Gregory-Hansen, {num(c.gregory_hansen.level)} and{" "}
          {num(c.gregory_hansen.regime)}) does not rescue it.
        </p>
        <div style={{ height: 18 }} />
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>From</th>
                <th>To</th>
                <th className="num">Hedge ratio, log NED on log SBK</th>
              </tr>
            </thead>
            <tbody>
              {c.segments.map((s) => (
                <tr key={s.from}>
                  <td className="mono">{s.from.slice(0, 7)}</td>
                  <td className="mono">{s.to.slice(0, 7)}</td>
                  <td className="num">{num(s.slope)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="note">
          Bai-Perron finds {c.breaks.length} breaks in the long-run relationship, and the hedge ratio swings between{" "}
          {num(Math.min(...slopes))} and {num(Math.max(...slopes))}. The two banks still move together, so the project models
          their dependence day to day instead: ARMA-GARCH filters each return series and a copula captures the joint tails. The
          classic z-score trade is still tested below, as H4.
        </p>
      </section>
      <section className="panel">
        <div className="panel-head">
          <h2 className="serif">
            The reversal <em>that faded</em>
          </h2>
          <div className="legend">
            <span style={{ color: "var(--primary)" }}>
              <i />
              Average of all 15 pairs
            </span>
            <span style={{ color: "#b58b3c" }}>
              <i />
              SBK and NED
            </span>
            <span style={{ color: "var(--border-strong)" }}>
              <i />
              Each other pair
            </span>
          </div>
        </div>
        <DecayChart dates={d.dates} pairs={d.pairs} mean={d.mean_acf} highlight={highlight} />
        <p className="note">
          One-year rolling lag-1 autocorrelation of the daily return gap between every pair of Standard Bank, Nedbank, FirstRand,
          Absa, Capitec and Investec. Below zero, a gap tends to close the next day, which is what a pairs trade needs. The average
          was {num(at("2011"))} in 2011 and {num(at("2026"))} at the start of 2026.
        </p>
      </section>
      <section className="panel split">
        <div>
          <div className="panel-head">
            <h2 className="serif">
              Next day after <em>an extreme signal</em>
            </h2>
          </div>
          <ReversalBars rows={d.reversal_by_year} />
        </div>
        <div>
          <p className="eyebrow">SBK and NED, before costs</p>
          <p className="note" style={{ marginTop: 14 }}>
            Average next-session return, in basis points of capital, from taking the position the copula signal points to on days
            beyond its 90th percentile. Whiskers are two standard errors. From 2010 to 2019 it averaged {num(avg(early), 1)} bps
            a signal; since 2020, {num(avg(late), 1)} bps. A round trip costs about 20 bps, so even the early edge was too thin
            to trade one day at a time.
          </p>
        </div>
      </section>
      <section className="panel">
        <div className="panel-head">
          <h2 className="serif">
            Every rule tested, <em>including the failures</em>
          </h2>
          <span className="legend">Sharpe ratio after costs</span>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Rule</th>
                <th className="num">Design 2010–19</th>
                <th className="num">Validation 2020–Mar 2026</th>
                <th className="num">Since April 2026</th>
                <th>Verdict</th>
              </tr>
            </thead>
            <tbody>
              {r.tests.map((t) => (
                <tr key={t.id}>
                  <td>
                    <strong style={{ fontWeight: 500 }}>{t.name}</strong>
                    <div className="muted" style={{ fontSize: 12, maxWidth: 420 }}>
                      {t.detail}
                      {t.design_note ? ` ${t.design_note}.` : ""}
                      {t.before_costs ? ` Before costs: ${num(t.before_costs.design.sharpe)} in design, ${num(t.before_costs.validation.sharpe)} in validation.` : ""}
                      {` Validation Sortino ${num(t.validation.sortino)}.`}
                      {t.entries ? ` ${t.entries.validation} trades in validation.` : ""}
                      {t.edge_vs_h1
                        ? ` Ahead of H1 in validation by ${num(t.edge_vs_h1.bps_per_year, 0)} bps a year (t = ${num(t.edge_vs_h1.t_stat)}), too small to tell from chance.`
                        : ""}
                    </div>
                  </td>
                  <td className="num">{num(t.design.sharpe)}</td>
                  <td className="num" style={{ color: t.validation.sharpe < 0 ? "var(--negative)" : undefined }}>
                    {num(t.validation.sharpe)}
                  </td>
                  <td className="num" style={{ color: t.post_freeze.sharpe < 0 ? "var(--negative)" : undefined }}>
                    {t.entries?.post_freeze === 0 ? "No trades" : num(t.post_freeze.sharpe)}
                  </td>
                  <td>
                    {t.passed == null
                      ? "Baseline"
                      : !t.passed
                        ? "Failed"
                        : t.edge_vs_h1 && Math.abs(t.edge_vs_h1.t_stat) < 2
                          ? "Passed, within noise"
                          : "Passed, narrowly"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="note">
          Every rule was fixed on design data and written into a protocol before its validation run, which was run once. Results
          since April 2026 are reported, never used to choose. The months since April are few, so those Sharpe ratios are noisy.
        </p>
      </section>
    </>
  );
}

export function App({ embedded }: { embedded: boolean }) {
  const [strategy, setStrategy] = useState<Strategy>("basket");
  const [period, setPeriod] = useState<Period>("walkforward");
  const [status, setStatus] = useState<Model["status"] | null>(null);
  useEffect(() => {
    getModel()
      .then((m) => setStatus(m.status))
      .catch(() => undefined);
  }, []);

  return (
    <main className="preview">
      <header className="head">
        <div>
          <p className="eyebrow">Live preview · JSE banks · Copula-GARCH pairs</p>
          {!embedded && (
            <h1 className="serif">
              Standard Bank against its peers,
              <br />
              <em>traded on data the model has not seen.</em>
            </h1>
          )}
        </div>
        {status && (
          <div className="status">
            <span>
              <i className={`dot${status.source === "live" ? "" : " stale"}`} />
              {status.source === "live" ? "Live prices" : "Stored prices (live feed unavailable)"} to {fmtDate(status.as_of)}
            </span>
            <span>Out-of-sample since {fmtDate("2026-04-01")} · refreshed after each JSE close</span>
          </div>
        )}
      </header>

      <div className="strategy-switch segmented" role="radiogroup" aria-label="Strategy">
        <button aria-pressed={strategy === "basket"} onClick={() => setStrategy("basket")}>
          Against a bank basket <span>the new rule, refitted monthly</span>
        </button>
        <button aria-pressed={strategy === "pair"} onClick={() => setStrategy("pair")}>
          Against Nedbank <span>the original report rule</span>
        </button>
      </div>

      <div className="tabs" role="tablist">
        {PERIODS.map((p) => (
          <button key={p.id} role="tab" aria-selected={period === p.id} onClick={() => setPeriod(p.id)}>
            {p.label}
          </button>
        ))}
      </div>

      {strategy === "basket" ? <BasketView period={period} /> : <PairView period={period} />}

      <ResearchSection />

      <section className="panel" style={{ borderBottom: 0 }}>
        <div className="panel-head">
          <h2 className="serif">
            How it is <em>tested</em>
          </h2>
        </div>
        <ul className="method">
          <li>
            <strong>Data</strong>
            Daily adjusted closes for Standard Bank, Nedbank, FirstRand, Absa, Capitec and Investec from Yahoo Finance since 2005,
            VIX from FRED, trading volumes, and GDELT news coverage from 2015. Single-day bad prints that reverse are removed.
          </li>
          <li>
            <strong>Marginal models</strong>
            Each refit chooses an ARMA-GARCH model per series from 36 candidates (GARCH, GJR or EGARCH; normal or Student t; with or
            without lagged VIX) by BIC on its training data.
          </li>
          <li>
            <strong>Dependence</strong>
            A bivariate copula is fitted to the training probability transforms, family chosen by AIC. It has been Student t in
            every fit.
          </li>
          <li>
            <strong>Pre-registration</strong>
            Rules were chosen on 2010 to 2019, then validated once on 2020 to March 2026 against a pass mark written down
            beforehand. Changes to the protocol are dated and disclosed.
          </li>
          <li>
            <strong>No look-ahead</strong>
            Every fit uses only data before the days it trades. A position set at today’s close earns tomorrow’s return.
          </li>
          <li>
            <strong>Unseen data</strong>
            Nothing since 1 April 2026 was used to choose anything. The record grows by one session after each JSE close.
          </li>
        </ul>
        <p className="footer-note">
          Backtest and live paper record, not investment advice. Costs cover brokerage on every leg; slippage, short borrow fees and
          securities transfer tax are not modelled. Extended from a group project with Matlhatse Makgopa.
        </p>
      </section>
    </main>
  );
}
