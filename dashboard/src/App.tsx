import { useEffect, useState } from "react";
import {
  RULE_DEFAULTS,
  getPairBacktest,
  getPairModel,
  getResearch,
  getSwitch,
  type PairBacktest,
  type Switch,
  type PairModel,
  type RuleParams,
  type CostTier,
  type Period,
  type Research,
} from "./api";
import { EdgeBars, EquityChart, GateChart, PitScatter } from "./charts";
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

function useBacktest(period: Period, params: RuleParams) {
  const [bt, setBt] = useState<PairBacktest | null>(null);
  const [error, setError] = useState<string | null>(null);
  const debounced = useDebounced(params, 200);
  useEffect(() => {
    const ctl = new AbortController();
    getPairBacktest(period, debounced, ctl.signal)
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
        {late.n} signals, standard error {num(late.se, 0)}). The first session after a signal was worth {num(early.next_bps, 0)} bps before 2020 and {num(late.next_bps, 0)} since.
        {r.redteam
          ? ` These figures assume a fill at the close that produced the signal. Filled at the next close, the 2010 to 2019 figure is ${num(r.redteam.lag_next_close_2010_2019_bps, 0)} bps, and filled at 10:00 the next morning, ${num(r.redteam.lag_next_10am_2010_2019_bps, 0)}. Against 10,000 random entry sets the 2010 to 2019 figure sits at the ${num(r.redteam.placebo_percentile_2010_2019, 1)}th percentile, and the 2021 onward figure at the ${num(r.redteam.placebo_percentile_2021_2026, 0)}th.`
          : ""}
      </p>
    </section>
  );
}

function LiveRecord({ bt, tier, roundTrip, period }: { bt: PairBacktest; tier: CostTier; roundTrip: number; period: Period }) {
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
        <Metric value={String(m.trades)} label="Trades" sub={m.avg_hold_days != null ? `Average ${m.avg_hold_days.toFixed(1)} sessions held; a new signal restarts the five` : undefined} />
        <Metric value={pct(m.hit_rate, 0)} label="Winning trades" sub={`In the market ${pct(m.time_in_market, 0)} of days`} />
        <Metric
          value={bt.latest.position > 0 ? "Long SBK" : bt.latest.position < 0 ? "Short SBK" : "Flat"}
          label={`Position into the next session`}
          sub={`P(NED | SBK) ${bt.latest.h.toFixed(3)} at ${fmtDate(bt.latest.date)}`}
        />
      </section>
      <p className="note">
        {short
          ? `${Math.round(m.years * 12)} months of unseen sessions so far. At this volatility a strategy with no edge would end this many months between ${pct(-band)} and ${pct(band)} about 95% of the time, so the record cannot yet tell the signal from noise. `
          : ""}
        Net of costs ({TIER_LABEL[tier]}), about {num(roundTrip, 0)} bps of capital a round trip, each side sized at half of capital. Holding half
        Standard Bank and half Nedbank returned {pct(bt.benchmark.total_return)} over the same dates.
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
            <span style={{ color: "#b58b3c" }}>■ Long NED</span>
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

type Score = Switch["switch"];

const signed = (v: number | null | undefined, d = 1) => (v == null ? "n/a" : `${v > 0 ? "+" : v < 0 ? "−" : ""}${num(Math.abs(v), d)}`);
const bps = (v: number | null | undefined, d = 1) => (v == null ? "n/a" : `${signed(v, d)} bps`);

/** Is the relationship holding: the rolling test against both rules' cutoffs. */
function Relationship({ s }: { s: Switch }) {
  const t = s.today;
  const g = s.spread_gate;
  return (
    <section className="panel">
      <div className="panel-head">
        <h2 className="serif">
          1. Are the two prices <em>tied together</em> right now?
        </h2>
        <div className="legend">
          <span style={{ color: "var(--foreground)" }}>— Test statistic, last {s.window} sessions</span>
          <span style={{ color: "var(--primary)", opacity: 0.5 }}>■ Below {num(g.crit, 1)}</span>
          <span style={{ color: "var(--primary)" }}>■ Below {num(s.crit)}</span>
        </div>
      </div>
      <section className="metrics" aria-label="The relationship today">
        <Metric
          value={t.holds ? "Holding" : t.gate_open ? "Holding, weakly" : "Not holding"}
          label="Relationship today"
          negative={!t.gate_open}
          sub={`Statistic ${num(t.eg)} on ${fmtDate(s.as_of)}`}
        />
        <Metric
          value={t.gate_open ? "Below now" : t.last_gate_day ? fmtDate(t.last_gate_day, { day: "numeric", month: "short", year: "numeric" }) : "Never"}
          label={`Last below ${num(g.crit, 1)}`}
          sub="The spread strategy trades only below this"
        />
        <Metric
          value={t.holds ? "Below now" : t.last_spread_day ? fmtDate(t.last_spread_day, { day: "numeric", month: "short", year: "numeric" }) : "Never"}
          label={`Last below ${num(s.crit)}`}
          sub="The switching strategy trades the spread only below this"
        />
        <Metric
          value={num(Math.abs(t.hedge_ratio) < 0.005 ? 0 : t.hedge_ratio)}
          label={`Hedge ratio, last ${s.window} sessions`}
          sub={`Long-run segment since ${fmtDate(s.segment.from, { month: "short", year: "numeric" })}: ${num(s.segment.slope)}`}
        />
      </section>
      <GateChart
        dates={s.series.date}
        stat={s.series.eg}
        lines={[
          { value: g.crit, label: `spread strategy trades below ${num(g.crit, 1)}` },
          { value: s.crit, label: `switching strategy uses the spread below ${num(s.crit)}` },
        ]}
        bands={[
          { mode: s.series.gate, opacity: 0.1 },
          { mode: s.series.mode, opacity: 0.14 },
        ]}
        label="Rolling Engle-Granger statistic for log Nedbank on log Standard Bank, with the two cutoffs and the sessions below each shaded"
      />
      <p className="note">
        Each session, log Nedbank is regressed on log Standard Bank over the last {s.window} sessions, about six months, and the gap left
        over is tested for whether it drifts back to zero (an Engle-Granger test). The more negative the statistic, the stronger the evidence
        that the two prices are tied together and a gap between them closes. {num(s.crit)} is the textbook 5% critical value. {num(g.crit, 1)} is
        a looser cutoff that worked better on the history. Over the whole record since 2005 the two prices are not tied together; the
        relationship comes and goes in stretches, such as 2011 to 2013, 2018, 2022 and 2024. Today the statistic is {num(t.eg)}, so{" "}
        {t.gate_open ? "the relationship is holding." : "the relationship is not holding, and neither spread rule will open a trade."}
      </p>
    </section>
  );
}

function stateText(p: Score["position"]) {
  if (!p.open) return "Flat";
  return `${p.side}, since ${fmtDate(p.opened, { day: "numeric", month: "short" })}`;
}

/** What each strategy is doing today, and why. */
function Strategies({ s, h }: { s: Switch; h: number | null }) {
  const t = s.today;
  const g = s.spread_gate;
  const cop = s.copula_alone.position;
  const fired = h != null && Math.abs(h - 0.5) > 0.45;
  const rows = [
    {
      name: "Spread strategy",
      best: true,
      how: `Trades the gap between the two prices while the statistic is below ${num(g.crit, 1)}: opens when the gap is 1.5 standard deviations wide, closes when it is back to zero, at 4 standard deviations or after 60 sessions. Holds nothing otherwise.`,
      today: stateText(g.position),
      why: g.position.open
        ? "The trade stays open until its own exit, even if the relationship weakens."
        : t.gate_open
          ? `The relationship is holding, but the gap is ${num(Math.abs(t.z), 1)} standard deviations, inside the 1.5 needed to open.`
          : `The statistic is ${num(t.eg)}, above ${num(g.crit, 1)}, so it waits.${t.last_gate_day ? ` It was last below on ${fmtDate(t.last_gate_day)}.` : ""}`,
    },
    {
      name: "Switching strategy",
      best: false,
      how: `The same spread trade while the statistic is below ${num(s.crit)}; otherwise it follows the copula signal.`,
      today: s.switch.position.open ? `${stateText(s.switch.position)} (${s.switch.position.method === "spread" ? "spread" : "copula"})` : "Flat",
      why: t.holds
        ? "The relationship is holding at 5%, so it trades the spread."
        : `The statistic is above ${num(s.crit)}, so it is following the copula signal and makes the same trades as the copula signal.`,
    },
    {
      name: "Copula signal",
      best: false,
      how: "Each day asks how unusual Nedbank's move was given Standard Bank's, from a copula on top of each bank's own volatility model. Beyond 5% in either tail it takes the side that bets on the move reversing, for five sessions.",
      today: stateText(cop),
      why: cop.open
        ? "A signal fired in the last five sessions."
        : h == null
          ? "No signal in the last five sessions."
          : `No signal in the last five sessions. Today's reading is ${num(h, 3)}; it fires below 0.05 or above 0.95${fired ? "." : ", so it is quiet."}`,
    },
  ];
  return (
    <section className="panel">
      <div className="panel-head">
        <h2 className="serif">
          2. What each strategy is <em>doing</em> today
        </h2>
        <span className="legend">Positions carried into the session after {fmtDate(s.as_of)}</span>
      </div>
      <div className="table-wrap">
        <table className="strategies">
          <thead>
            <tr>
              <th>Strategy</th>
              <th>How it trades</th>
              <th>Today</th>
              <th>Why</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.name}>
                <td>
                  <strong>{r.name}</strong>
                  {r.best && <span className="tag">Best record on the history</span>}
                </td>
                <td>{r.how}</td>
                <td className="state">{r.today}</td>
                <td>{r.why}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="note">
        The three share one question. When the two prices are tied together, a gap between them tends to close, and the spread trade bets
        on that. When they are not, there is no gap to trade, and the copula signal looks instead for single days when one bank moved
        unusually far against the other. On the history to March 2026, the spread strategy is the only one of the three that made money after
        institutional costs, which is why it is the current best bet. It is also the slowest: about {num(g.development.trades_per_year, 0)} trades
        a year, and none while the relationship is not holding. None of the three has a live record long enough to judge yet.
      </p>
    </section>
  );
}

/** What each has earned live, and what the history suggested. */
function Records({ s }: { s: Switch }) {
  const g = s.spread_gate;
  const dv = g.development;
  const d = s.reference.design;
  const v = s.reference.validation_already_seen;
  const started = new Date() >= new Date(`${g.score_from}T00:00:00Z`);
  const live: [string, Score, string][] = [
    ["Spread strategy", g, "40 completed trades or the end of 2036"],
    ["Switching strategy", s.switch, "225 completed trades or the end of 2030"],
    ["Copula signal", s.copula_alone, "Reported beside the other two"],
  ];
  const open = (r: Score) => (r.position.open ? 1 : 0);
  return (
    <section className="panel">
      <div className="panel-head">
        <h2 className="serif">
          3. What they have <em>earned</em>, and what the history suggested
        </h2>
      </div>
      <p className="eyebrow">Live: trades opened from {fmtDate(g.score_from)}</p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Strategy</th>
              <th className="num">Completed</th>
              <th className="num">Open</th>
              <th className="num">Net a trade, futures</th>
              <th className="num">Net a trade, shares</th>
              <th className="num">t, futures</th>
              <th>Judged at</th>
            </tr>
          </thead>
          <tbody>
            {live.map(([name, r, when]) => (
              <tr key={name}>
                <td>{name}</td>
                <td className="num">{r.complete}</td>
                <td className="num">{open(r)}</td>
                <td className="num">{bps(r.net_futures_bps)}</td>
                <td className="num">{bps(r.net_cash_bps)}</td>
                <td className="num">{r.t_futures == null ? "n/a" : num(r.t_futures)}</td>
                <td>{when}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="note">
        {started ? "" : `Scoring starts on ${fmtDate(g.score_from)}. `}
        The spread and switching strategies were fixed on {fmtDate(g.frozen_on)}, and the copula signal on 31 March 2026; nothing about them changes from here. For all three, only trades opened from{" "}
        {fmtDate(g.score_from)} count. A strategy passes if its average trade after futures costs is above zero with a t-statistic above 1.65.
        If the relationship does not hold before the deadline, the spread strategy will have made few or no trades, and there is no evidence
        either way.
      </p>
      <p className="eyebrow" style={{ marginTop: 22 }}>
        History: development data to 31 March 2026
      </p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Strategy</th>
              <th>Period</th>
              <th className="num">Trades</th>
              <th className="num">Net a trade, futures</th>
              <th className="num">Net a trade, shares</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Spread strategy</td>
              <td>
                {dv.from.slice(0, 4)} to March 2026
              </td>
              <td className="num">{dv.trades}</td>
              <td className="num">{bps(dv.futures_bps)}</td>
              <td className="num">{bps(dv.cash_bps)}</td>
            </tr>
            {dv.eras.map((e) => (
              <tr key={e.from} className="sub-row">
                <td />
                <td>
                  {e.from.slice(0, 4)} to {e.to < "2026-04-01" ? Number(e.to.slice(0, 4)) - 1 : "March 2026"}
                </td>
                <td className="num">{e.trades}</td>
                <td className="num">{bps(e.futures_bps)}</td>
                <td />
              </tr>
            ))}
            {(
              [
                ["Switching strategy", "switch"],
                ["Copula signal", "copula_alone"],
              ] as const
            ).map(([name, k]) =>
              [
                ["2010 to 2019", d],
                ["2020 to March 2026", v],
              ].map(([per, r], i) => {
                const x = (r as typeof d)[k];
                return (
                  <tr key={`${name}-${per}`}>
                    <td>{i === 0 ? name : ""}</td>
                    <td>{per as string}</td>
                    <td className="num">{x.trades}</td>
                    <td className="num">{bps(x.futures)}</td>
                    <td className="num">{bps(x.cash)}</td>
                  </tr>
                );
              }),
            )}
          </tbody>
        </table>
      </div>
      <p className="note">
        The spread strategy was found by searching the history: {dv.specifications_searched} versions were tried on data to March 2026
        (different cutoffs, windows, entry levels, exits, a sector-hedged spread and forecast-based filters), and this one did best. Its
        figures are therefore flattering. Cutoffs from −2.4 to −3.34 made {num(Math.min(...Object.values(dv.by_cutoff)), 0)} to{" "}
        {num(Math.max(...Object.values(dv.by_cutoff)), 0)} bps a trade, so it is not a lone lucky number. The median trade made{" "}
        {num(dv.median_bps, 0)} bps, {pct(dv.win, 0)} of trades made money, and without its three best trades the average is still{" "}
        {num(dv.drop_top3_bps, 0)} bps. A trade lasts about {num(dv.mean_days, 0)} sessions. Expect less live: something like{" "}
        {g.expected_live_bps[0]} to {g.expected_live_bps[1]} bps a trade would be no surprise. The switching strategy and the copula signal
        were designed on 2010 to 2019; 2020 to March 2026 had already been seen when the switch was designed.
      </p>
      <p className="note">
        Costs are institutional. Single stock futures carry commission, the exchange fee and VAT, a half-spread, funding and a roll at each
        expiry. Shares carry brokerage and VAT, securities transfer tax of 0.25% on purchases, Strate, the levy, a half-spread and borrow on
        the short side. The half-spreads and borrow are assumptions.
      </p>
    </section>
  );
}

function Instrument({ model, research }: { model: PairModel; research: Research | null }) {
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
        <PitScatter history={model.pit.walkforward} live={model.pit.live} yLabel="Nedbank v → 1" />
        <p className="note">
          Each day’s returns, turned into probabilities by that year’s volatility models. If the models are right these fill the square
          evenly.
          {ins?.margin_oos
            ? ` Tested year by year on the days each fit had not seen, Standard Bank's probabilities ${ins.margin_oos.sbk_fail_years.length ? `fail in ${ins.margin_oos.sbk_fail_years.join(", ")}` : `pass in all ${ins.margin_oos.years} years`} and Nedbank's ${ins.margin_oos.ned_fail_years.length ? `fail in ${ins.margin_oos.ned_fail_years.length} (${ins.margin_oos.ned_fail_years.join(", ")})` : `pass in all ${ins.margin_oos.years}`}, so Nedbank is the weaker margin (KS at 5%).`
            : ""} The signal is P(Nedbank ≤ today | Standard Bank = today) from the
          copula; it fires beyond 0.05 and 0.95.
          {ins && dep.model === "gas_t"
            ? ` The copula’s correlation moves with the data (a score-driven update), chosen over a fixed correlation by a pre-registered forecast test on 2020 to March 2026: ${num(ins.validation_gain_per_day * 1000, 0)} thousandths of a log point a day better, t = ${num(ins.dm_t)}, and the signal is calibrated out of sample (KS p ${num(ins.h_ks_p)} against ${num(ins.static_h_ks_p, 3)} for the fixed correlation).`
            : ""}
        </p>
      </div>
      <div>
        <p className="eyebrow">Final fit, frozen {fmtDate(latest.train_end)}</p>
        <table style={{ marginTop: 14 }}>
          <tbody>
            <tr>
              <td>Standard Bank</td>
              <td>{specLabel(latest.sbk)}</td>
            </tr>
            <tr>
              <td>Nedbank</td>
              <td>{specLabel(latest.ned)}</td>
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
              <td>PIT uniformity, KS p, in sample</td>
              <td>
                SBK {latest.pit_ks.sbk.toFixed(2)} · NED {latest.pit_ks.ned.toFixed(2)}
              </td>
            </tr>
          </tbody>
        </table>
        <p className="note">
          Specifications come from 36 ARMA-GARCH candidates by BIC each December, fitted on data to that year end and used only for
          the following year. The final fit was frozen on 31 March 2026, and every session since is filtered forward from it. Over the
          whole record Standard Bank and Nedbank are not cointegrated, which is why dependence is modelled day to day rather than through a long-run spread.
        </p>
      </div>
    </section>
  );
}

export function App({ embedded }: { embedded: boolean }) {
  const [period, setPeriod] = useState<Period>("live");
  const [tier, setTier] = useState<CostTier>("institutional");
  const params: RuleParams = { ...RULE_DEFAULTS, costs: tier };
  const { bt, error } = useBacktest(period, params);
  const [model, setModel] = useState<PairModel | null>(null);
  const [research, setResearch] = useState<Research | null>(null);
  const [sw, setSw] = useState<Switch | null>(null);
  const [swError, setSwError] = useState<string | null>(null);
  useEffect(() => {
    getSwitch()
      .then(setSw)
      .catch((e) => setSwError(String(e.message ?? e)));
    getPairModel().then(setModel).catch(() => undefined);
    getResearch().then(setResearch).catch(() => undefined);
  }, []);
  const status = model?.status;
  const ins = research?.instrument;
  const h = bt && bt.latest.date === sw?.as_of ? bt.latest.h : null;

  return (
    <main className="preview">
      <header className="head">
        <div>
          <p className="eyebrow">Live paper record · Standard Bank and Nedbank · three strategies</p>
          {!embedded && (
            <h1 className="serif">
              Standard Bank against Nedbank:
              <br />
              <em>trade the gap only while the two prices are tied together.</em>
            </h1>
          )}
        </div>
        {status && (
          <div className="status">
            <span>
              <i className={`dot${status.source === "live" ? "" : " stale"}`} />
              {status.source === "live" ? "Live prices" : "Stored prices (live feed unavailable)"} to {fmtDate(status.as_of)}
            </span>
            <span>Refreshed after each JSE close</span>
          </div>
        )}
      </header>

      {!sw && <p className="loading">{swError ? `Could not load the relationship test: ${swError}` : "Testing the relationship on the latest prices…"}</p>}
      {sw && <Relationship s={sw} />}
      {sw && <Strategies s={sw} h={h} />}
      {sw && <Records s={sw} />}

      <section className="panel">
        <div className="panel-head">
          <h2 className="serif">
            4. The copula signal, <em>since 1 April 2026</em>
          </h2>
          {ins && (
            <span className="legend">
              Sharpe {num(ins.rule.validation.before)} before costs and {num(ins.rule.validation.after)} after, 2020 to March 2026
            </span>
          )}
        </div>
        <p className="note" style={{ marginTop: 0 }}>
          The copula signal has the longest live record of the three: every session since its models were frozen on 31 March 2026. Its
          signal is real, but since 2021 it has been worth less than the cost of acting on it.
        </p>
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
                  {research?.costs ? <span>{" · "}{num(research.costs.tiers[t].round_trip_bps, 0)} bps a round trip</span> : null}
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
            half-spread and borrow are assumptions.
          </p>
        )}
        {!bt && (error ? <p className="loading">Could not load the record: {error}</p> : <p className="loading">Filtering the latest prices…</p>)}
        {bt && <LiveRecord bt={bt} tier={tier} roundTrip={bt.params.round_trip_bps} period={period} />}
      </section>

      <details className="more">
        <summary>How the copula signal is built, and what a signal was worth by year</summary>
        {research && <EdgePanel r={research} tier={tier} />}
        {model && <Instrument model={model} research={research} />}
      </details>

      <section className="panel" style={{ borderBottom: 0 }}>
        <div className="panel-head">
          <h2 className="serif">
            How it is <em>tested</em>
          </h2>
        </div>
        <ul className="method">
          <li>
            <strong>Data</strong>
            Daily adjusted closes for Standard Bank and Nedbank from Yahoo Finance since 2005, VIX from FRED. Single-day bad prints that
            reverse are removed.
          </li>
          <li>
            <strong>No look-ahead</strong>
            Every test, fit and position uses only data to that day’s close, and a position set at the close earns the next session’s return.
          </li>
          <li>
            <strong>Fixed, then scored</strong>
            Each strategy was written down and fixed before the sessions it is scored on: the copula signal on 31 March 2026, the switching
            and spread strategies on 11 November 2026. Everything before those dates was used to build them, so the history figures are not
            tests. The live record is the test, and the deadlines and pass marks were set in advance.
          </li>
          <li>
            <strong>What did not work</strong>
            Many other rules were tried on the pair and failed: a five-day hold, news filters, an intraday rule, volatility gauges, a
            forecast of whether the gap closes built on currencies, dividends, rates and news, and a spread hedged against FirstRand and
            Absa. They are recorded in the repository with the rest of the research.
          </li>
        </ul>
        <p className="footer-note">
          Backtest and live paper record, not investment advice. The half-spreads and borrow in the costs are assumptions. Extended from a
          group project with Matlhatse Makgopa.
        </p>
      </section>
    </main>
  );
}
