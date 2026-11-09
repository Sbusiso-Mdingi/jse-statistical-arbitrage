import { useEffect, useState } from "react";
import {
  BASKET_DEFAULTS,
  getBasketBacktest,
  getBasketModel,
  getResearch,
  type BasketBacktest,
  type BasketModel,
  type BasketParams,
  type Period,
  type Research,
} from "./api";
import { EdgeBars, EquityChart, PitScatter } from "./charts";
import { fmtDate, num, pct } from "./format";

const PERIODS: { id: Period; label: string }[] = [
  { id: "live", label: "Unseen since 1 April 2026" },
  { id: "walkforward", label: "Walk-forward, 2010 to March 2026" },
  { id: "all", label: "Full record" },
];

const MODEL_NAMES: Record<string, string> = { sGARCH: "GARCH", gjrGARCH: "GJR-GARCH", eGARCH: "EGARCH" };
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

function Metric({ value, label, sub, negative }: { value: string; label: string; sub?: string; negative?: boolean }) {
  return (
    <div className="metric">
      <div className={`value${negative ? " neg" : ""}`}>{value}</div>
      <div className="label">{label}</div>
      {sub && <div className="sub">{sub}</div>}
    </div>
  );
}

function useBacktest(period: Period, params: BasketParams) {
  const [bt, setBt] = useState<BasketBacktest | null>(null);
  const [error, setError] = useState<string | null>(null);
  const debounced = useDebounced(params, 200);
  useEffect(() => {
    const ctl = new AbortController();
    getBasketBacktest(period, debounced, ctl.signal)
      .then((r) => {
        setBt(r);
        setError(null);
      })
      .catch((e) => e.name !== "AbortError" && setError(String(e.message ?? e)));
    return () => ctl.abort();
  }, [period, debounced]);
  return { bt, error };
}

/** What a signal was worth before costs, year by year, against the cost of acting on it. */
function EdgePanel({ r }: { r: Research }) {
  const e = r.edge;
  const early = e["2010_2019"];
  const late = e["2021_2026"];
  const covid = e.by_year.find((y) => y.year === 2020);
  return (
    <section className="panel">
      <div className="panel-head">
        <h2 className="serif">
          What a signal <em>was worth</em>
        </h2>
        <div className="legend">
          <span style={{ color: "var(--primary)" }}>■ Above the cost</span>
          <span style={{ color: "var(--border-strong)" }}>■ Positive, below the cost</span>
          <span style={{ color: "var(--negative)" }}>■ Negative</span>
        </div>
      </div>
      <EdgeBars rows={e.by_year} cost={e.cost_round_trip_bps} label="Gross return per signal over the five-day hold, by year, against the cost of a round trip" />
      <p className="note">
        Each bar is the average return, in basis points of capital and before costs, from taking the position the signal points
        to and holding it {e.hold} sessions, for every day the signal fired that year. Whiskers are two standard errors; {e.last_date.slice(0, 4)} is
        partial. From 2010 to 2019 a signal was worth {num(early.bps, 0)} bps on average ({early.n} signals, standard error{" "}
        {num(early.se, 0)}); the round trip costs {num(e.cost_round_trip_bps, 0)}. Since 2021 it has been worth {num(late.bps, 0)} bps (
        {late.n} signals). {covid ? `The one year that paid, 2020, averaged ${num(covid.bps, 0)} bps on ${covid.n} signals.` : ""} The next
        session alone went from {num(early.next_bps, 0)} bps to {num(late.next_bps, 0)}.
      </p>
    </section>
  );
}

function LiveRecord({ bt, costBps, period }: { bt: BasketBacktest; costBps: number; period: Period }) {
  const m = bt.metrics;
  const short = m.years < 1;
  // Two standard deviations of the total return of a zero-mean strategy with this volatility, over this span.
  const band = 2 * m.volatility * Math.sqrt(m.years);
  const [showBench, setShowBench] = useState(false);
  return (
    <>
      <section className="metrics" aria-label="Performance">
        <Metric value={pct(m.total_return)} label="Total return" negative={m.total_return < 0} sub={`${fmtDate(bt.start)} to ${fmtDate(bt.end)}`} />
        <Metric value={num(m.sharpe)} label="Sharpe ratio" negative={m.sharpe < 0} sub={`Sortino ${num(m.sortino)} · annualised`} />
        <Metric value={pct(m.max_drawdown)} label="Max drawdown" negative />
        <Metric value={String(m.trades)} label="Trades" sub={m.avg_hold_days != null ? `Average ${m.avg_hold_days.toFixed(1)} days held` : undefined} />
        <Metric value={pct(m.hit_rate, 0)} label="Winning trades" sub={`In the market ${pct(m.time_in_market, 0)} of days`} />
        <Metric
          value={bt.latest.position > 0 ? "Long SBK" : bt.latest.position < 0 ? "Short SBK" : "Flat"}
          label={`Position into the next session`}
          sub={`P(basket | SBK) ${bt.latest.h.toFixed(3)} at ${fmtDate(bt.latest.date)}`}
        />
      </section>
      <p className="note">
        {short
          ? `${Math.round(m.years * 12)} months of unseen sessions so far. At this volatility a strategy with no edge would end this many months between ${pct(-band)} and ${pct(band)} about 95% of the time, so the record cannot yet tell the signal from noise. `
          : ""}
        Net of {costBps} bps per leg on every change of position, each side sized at half of capital. Holding half Standard Bank and half the
        basket returned {pct(bt.benchmark.total_return)} over the same dates.
      </p>
      <section className="panel">
        <div className="panel-head">
          <h2 className="serif">
            Growth of <em>R1</em>
          </h2>
          <div className="legend">
            <span style={{ color: "var(--primary)" }}>
              <i />
              Signal, after costs
            </span>
            <label className="toggle" style={{ fontFamily: "var(--font-mono)", fontSize: 11 }}>
              <input type="checkbox" checked={showBench} onChange={(e) => setShowBench(e.target.checked)} />
              Buy and hold
            </label>
            <span style={{ color: "var(--primary)" }}>■ Long SBK</span>
            <span style={{ color: "#b58b3c" }}>■ Long basket</span>
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
    </>
  );
}

function Instrument({ model }: { model: BasketModel }) {
  const latest = model.latest;
  return (
    <section className="panel split">
      <div>
        <div className="panel-head">
          <h2 className="serif">
            The instrument, <em>checked on unseen days</em>
          </h2>
          <div className="legend">
            <span style={{ color: "var(--border-strong)" }}>● Walk-forward days</span>
            <span style={{ color: "var(--primary)" }}>● Unseen days</span>
          </div>
        </div>
        <PitScatter history={model.pit.walkforward} live={model.pit.live} yLabel="Basket v → 1" />
        <p className="note">
          Each day’s returns, turned into probabilities by that month’s volatility models. If the models are right these fill the square
          evenly, and they do: the probability transforms pass uniformity tests in every one of {model.fits.length} monthly fits. The signal
          is P(basket ≤ today | Standard Bank = today) from the copula; it fires beyond 0.05 and 0.95.
        </p>
      </div>
      <div>
        <p className="eyebrow">Latest fit, to {fmtDate(latest.train_end)}</p>
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
                Student t, ρ {latest.copula.par.toFixed(3)}, ν {latest.copula.par2.toFixed(1)}
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
              <td>PIT uniformity, KS p</td>
              <td>
                SBK {latest.pit_ks.sbk.toFixed(2)} · basket {latest.pit_ks.bsk.toFixed(2)}
              </td>
            </tr>
          </tbody>
        </table>
        <p className="note">
          The basket is an equal-weight, daily-rebalanced mix of FirstRand, Absa, Nedbank and Capitec. Specifications come from 36
          ARMA-GARCH candidates by BIC each December; parameters and the copula (by AIC, Student t every time) are re-estimated at
          every month end and trade only the following month. Standard Bank and Nedbank are not cointegrated, which is why dependence
          is modelled day to day rather than through a long-run spread.
        </p>
      </div>
    </section>
  );
}

function EverythingElse({ r }: { r: Research }) {
  const verdict = (t: Research["tests"][number]) =>
    t.passed == null ? "Baseline" : !t.passed ? "Failed" : t.edge_vs_h1 && Math.abs(t.edge_vs_h1.t_stat) < 2 ? "Passed, within noise" : "Passed, narrowly";
  const tried = r.tests.filter((t) => t.id !== "h1");
  return (
    <section className="panel">
      <details>
        <summary className="serif" style={{ cursor: "pointer", fontSize: 20 }}>
          Everything else tried, <em>{tried.length} rules and baselines, one line each</em>
        </summary>
        <p className="note">
          Each was fixed on 2010 to 2019, written into the protocol with its pass mark, and validated once on 2020 to March 2026.
          Sharpe ratios after costs. None earned a place above; all stay on the record.
        </p>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Rule</th>
                <th className="num">Design</th>
                <th className="num">Validation</th>
                <th>Verdict</th>
              </tr>
            </thead>
            <tbody>
              {tried.map((t) => (
                <tr key={t.id}>
                  <td>
                    {t.name}
                    <div className="muted" style={{ fontSize: 12, maxWidth: 520 }}>
                      {t.detail}
                    </div>
                  </td>
                  <td className="num">{num(t.design.sharpe)}</td>
                  <td className="num" style={{ color: t.validation.sharpe < 0 ? "var(--negative)" : undefined }}>
                    {num(t.validation.sharpe)}
                  </td>
                  <td>{verdict(t)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </section>
  );
}

export function App({ embedded }: { embedded: boolean }) {
  const [period, setPeriod] = useState<Period>("live");
  const [cost, setCost] = useState(BASKET_DEFAULTS.cost_bps);
  const params: BasketParams = { ...BASKET_DEFAULTS, cost_bps: cost };
  const { bt, error } = useBacktest(period, params);
  const [model, setModel] = useState<BasketModel | null>(null);
  const [research, setResearch] = useState<Research | null>(null);
  useEffect(() => {
    getBasketModel().then(setModel).catch(() => undefined);
    getResearch().then(setResearch).catch(() => undefined);
  }, []);
  const status = model?.status;
  const h1 = research?.tests.find((t) => t.id === "h1");

  return (
    <main className="preview">
      <header className="head">
        <div>
          <p className="eyebrow">Live record · JSE banks · one copula-GARCH signal</p>
          {!embedded && (
            <h1 className="serif">
              Standard Bank against its peers:
              <br />
              <em>a signal that works, measuring an edge that costs more than it pays.</em>
            </h1>
          )}
        </div>
        {status && (
          <div className="status">
            <span>
              <i className={`dot${status.source === "live" ? "" : " stale"}`} />
              {status.source === "live" ? "Live prices" : "Stored prices (live feed unavailable)"} to {fmtDate(status.as_of)}
            </span>
            <span>Out of sample since {fmtDate("2026-04-01")} · refreshed after each JSE close</span>
          </div>
        )}
      </header>

      {research && <EdgePanel r={research} />}

      <section className="panel">
        <div className="panel-head">
          <h2 className="serif">
            The record, <em>after costs</em>
          </h2>
          {h1 && h1.before_costs && (
            <span className="legend">
              Validation Sharpe {num(h1.before_costs.validation.sharpe)} before costs, {num(h1.validation.sharpe)} after
            </span>
          )}
        </div>
        <div className="tabs" role="tablist">
          {PERIODS.map((p) => (
            <button key={p.id} role="tab" aria-selected={period === p.id} onClick={() => setPeriod(p.id)}>
              {p.label}
            </button>
          ))}
        </div>
        <section className="controls" aria-label="Cost assumption">
          <div className="control">
            <label>
              Cost per leg <output>{cost} bps</output>
            </label>
            <input type="range" min={0} max={50} value={cost} onChange={(e) => setCost(Number(e.target.value))} aria-label="Cost per leg" />
          </div>
          {cost !== BASKET_DEFAULTS.cost_bps && (
            <button className="reset" onClick={() => setCost(BASKET_DEFAULTS.cost_bps)}>
              Back to 10 bps
            </button>
          )}
        </section>
        {!bt && (error ? <p className="loading">Could not load the record: {error}</p> : <p className="loading">Filtering the latest prices…</p>)}
        {bt && <LiveRecord bt={bt} costBps={cost} period={period} />}
      </section>

      {model && <Instrument model={model} />}
      {research && <EverythingElse r={research} />}

      <section className="panel" style={{ borderBottom: 0 }}>
        <div className="panel-head">
          <h2 className="serif">
            How it is <em>tested</em>
          </h2>
        </div>
        <ul className="method">
          <li>
            <strong>Data</strong>
            Daily adjusted closes for Standard Bank, FirstRand, Absa, Nedbank and Capitec from Yahoo Finance since 2005, VIX from FRED.
            Single-day bad prints that reverse are removed.
          </li>
          <li>
            <strong>No look-ahead</strong>
            Every fit uses only data before the month it trades. A position set at today’s close earns tomorrow’s return.
          </li>
          <li>
            <strong>Pre-registration</strong>
            The rule was fixed on 2010 to 2019 and validated once on 2020 to March 2026 against a pass mark written down beforehand.
            Every later idea went through the same gate; the protocol and all results are in the repository.
          </li>
          <li>
            <strong>Unseen data</strong>
            Nothing since 1 April 2026 has been used to choose anything. The record grows by one session after each JSE close.
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
