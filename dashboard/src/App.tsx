import { useEffect, useState } from "react";
import {
  BASKET_DEFAULTS,
  getBasketBacktest,
  getBasketModel,
  getResearch,
  type BasketBacktest,
  type BasketModel,
  type BasketParams,
  type CostTier,
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
const TIER_LABEL: Record<CostTier, string> = { protocol: "Protocol: 10 bps a leg, brokerage only", institutional: "JSE, institutional", retail: "JSE, retail brokerage" };

function EdgePanel({ r, tier }: { r: Research; tier: CostTier }) {
  const e = r.edge;
  const cost = r.costs?.tiers[tier].round_trip_bps ?? e.cost_round_trip_bps;
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
      <EdgeBars rows={e.by_year} cost={cost} label="Gross return per signal over the five-day hold, by year, against the cost of a round trip" />
      <p className="note">
        Each bar is the average return, in basis points of capital and before costs, from taking the position the signal points
        to and holding it {e.hold} sessions, for every day the signal fired that year. Whiskers are two standard errors; {e.last_date.slice(0, 4)} is
        partial. From 2010 to 2019 a signal was worth {num(early.bps, 0)} bps on average ({early.n} signals, standard error{" "}
        {num(early.se, 0)}); a round trip costs {num(cost, 0)} bps under the cost schedule chosen below. Since 2021 it has been worth {num(late.bps, 0)} bps (
        {late.n} signals). {covid ? `The one year that paid, 2020, averaged ${num(covid.bps, 0)} bps on ${covid.n} signals.` : ""} The next
        session alone went from {num(early.next_bps, 0)} bps to {num(late.next_bps, 0)}.
      </p>
    </section>
  );
}

function LiveRecord({ bt, tier, roundTrip, period }: { bt: BasketBacktest; tier: CostTier; roundTrip: number; period: Period }) {
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
        Net of {TIER_LABEL[tier].toLowerCase()}, about {num(roundTrip, 0)} bps of capital a round trip, each side sized at half of capital. Holding half
        Standard Bank and half the basket returned {pct(bt.benchmark.total_return)} over the same dates.
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

function Instrument({ model, research }: { model: BasketModel; research: Research | null }) {
  const latest = model.latest;
  const dep = model.dependence;
  const ins = research?.instrument;
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
          {ins && dep.model === "gas_t"
            ? ` The copula’s correlation moves with the data (a score-driven update), chosen over a fixed correlation by a pre-registered forecast test on 2020 to March 2026: ${num(ins.validation_gain_per_day * 1000, 0)} thousandths of a log point a day better, t = ${num(ins.dm_t)}, and the signal is calibrated out of sample (KS p ${num(ins.h_ks_p)} against ${num(ins.static_h_ks_p, 3)} for the fixed correlation).`
            : ""}
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
                {dep.model === "gas_t"
                  ? `Student t, score-driven: ρ ${(dep.rho_live ?? dep.rho_train_end).toFixed(3)} today, ν ${dep.nu.toFixed(1)}`
                  : `Student t, ρ ${latest.copula.par.toFixed(3)}, ν ${latest.copula.par2.toFixed(1)}`}
              </td>
            </tr>
            {dep.model === "gas_t" && (
              <tr>
                <td>Correlation dynamics</td>
                <td>
                  β {dep.beta.toFixed(3)}, α {dep.alpha.toFixed(3)}
                </td>
              </tr>
            )}
            <tr>
              <td>Kendall’s τ, static fit</td>
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
          ARMA-GARCH candidates by BIC each December; parameters and the copula (Student t in every fit) are re-estimated at
          every month end and trade only the following month. Standard Bank and Nedbank are not cointegrated, which is why dependence
          is modelled day to day rather than through a long-run spread.
        </p>
      </div>
    </section>
  );
}

export function App({ embedded }: { embedded: boolean }) {
  const [period, setPeriod] = useState<Period>("live");
  const [tier, setTier] = useState<CostTier>("protocol");
  const params: BasketParams = { ...BASKET_DEFAULTS, costs: tier };
  const { bt, error } = useBacktest(period, params);
  const [model, setModel] = useState<BasketModel | null>(null);
  const [research, setResearch] = useState<Research | null>(null);
  useEffect(() => {
    getBasketModel().then(setModel).catch(() => undefined);
    getResearch().then(setResearch).catch(() => undefined);
  }, []);
  const status = model?.status;
  const h1 = research?.tests.find((t) => t.id === "h1");
  const ins = research?.instrument;

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

      {research && <EdgePanel r={research} tier={tier} />}

      <section className="panel">
        <div className="panel-head">
          <h2 className="serif">
            The record, <em>after costs</em>
          </h2>
          {ins ? (
            <span className="legend">
              Validation Sharpe {num(ins.rule.validation.before)} before costs, {num(ins.rule.validation.after)} after · the rule passed its
              pre-registered mark at {num(ins.rule_static.validation.after)} on the fixed-correlation copula
            </span>
          ) : (
            h1 &&
            h1.before_costs && (
              <span className="legend">
                Validation Sharpe {num(h1.before_costs.validation.sharpe)} before costs, {num(h1.validation.sharpe)} after
              </span>
            )
          )}
        </div>
        <div className="tabs" role="tablist">
          {PERIODS.map((p) => (
            <button key={p.id} role="tab" aria-selected={period === p.id} onClick={() => setPeriod(p.id)}>
              {p.label}
            </button>
          ))}
        </div>
        <section className="controls" aria-label="Cost schedule">
          <div className="control">
            <span className="label">Costs</span>
            <div className="segmented">
              {(Object.keys(TIER_LABEL) as CostTier[]).map((t) => (
                <button key={t} aria-pressed={tier === t} onClick={() => setTier(t)}>
                  {TIER_LABEL[t]}
                  {research?.costs ? <span>{num(research.costs.tiers[t].round_trip_bps, 0)} bps a round trip</span> : null}
                </button>
              ))}
            </div>
          </div>
        </section>
        {research?.costs && tier !== "protocol" && (
          <p className="note">
            A round trip is four executions at half of capital each, two of them purchases. Securities transfer tax of 0.25% on the purchases is{" "}
            {num(research.costs.components_institutional.stt, 0)} bps of capital on its own; brokerage with VAT {num(research.costs.components_institutional.brokerage_incl_vat, 0)} at
            institutional rates, half-spreads {num(research.costs.components_institutional.spread, 0)}, Strate and the levy under 1, borrow about 1 over a five-day hold. The
            half-spread and borrow are assumptions. The pre-registered verdicts were set at the protocol’s flat 10 bps a leg.
          </p>
        )}
        {!bt && (error ? <p className="loading">Could not load the record: {error}</p> : <p className="loading">Filtering the latest prices…</p>)}
        {bt && <LiveRecord bt={bt} tier={tier} roundTrip={bt.params.round_trip_bps} period={period} />}
      </section>

      {model && <Instrument model={model} research={research} />}

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
            Nine later trading rules went through the same gate: news filters, the classic z-score trade, learned exits, a direct edit to the
            fitted copula, an exit network and an intraday rule. Four failed and five passed within noise; none earned a place here. The protocol
            and every result are in the repository.
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
