import { useEffect, useState } from "react";
import { getSwitch, type Switch } from "./api";
import { RuleLab } from "./Lab";
import { WatchItTrade } from "./Timeline";
import { fmtDate, num } from "./format";

type Tab = "lab" | "watch" | "live" | "how";
type Score = Switch["switch"];

const bps = (v: number | null | undefined) =>
  v == null
    ? "n/a"
    : `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(1)} bps`;

function LiveRecord({ s }: { s: Switch | null }) {
  if (!s)
    return (
      <p className="loading">
        Loading the live record (the server may need half a minute to wake)…
      </p>
    );
  const real =
    s.spread_gate_1600 && "complete" in s.spread_gate_1600
      ? s.spread_gate_1600
      : null;
  const rows: [string, string, Score | null][] = [
    [
      "Decided at 16:00, filled in the closing auction",
      "the version a person could trade",
      real,
    ],
    [
      "Decided and filled at the same close",
      "the rule as first found",
      s.spread_gate,
    ],
    ["The same, on prices with dividends", "", s.spread_gate_dividends ?? null],
  ];
  const lead = real ?? s.spread_gate;
  return (
    <div className="live">
      <section className="lab-intro">
        <h2 className="serif">
          Since <em>{fmtDate(s.spread_gate.score_from)}</em>
        </h2>
        <p className="lede">
          Every choice behind the rule used prices only to 31 March 2026. From 1
          April each trade is recorded as it happens and cannot be changed. The
          rule trades only while the two prices are tied together, and they have
          not been since{" "}
          {s.today.last_gate_day
            ? fmtDate(s.today.last_gate_day)
            : "the spring"}
          , so there is little to show yet. About four trades a year are
          expected.
        </p>
      </section>
      <div className="metrics">
        <div className="metric">
          <div className="value">{lead.complete}</div>
          <div className="label">Completed trades</div>
          <div className="sub">decided at 16:00</div>
        </div>
        <div className="metric">
          <div className="value">
            {lead.position.open ? "In a trade" : "Flat"}
          </div>
          <div className="label">Position today</div>
          <div className="sub">
            {lead.position.open
              ? `${lead.position.side} since ${fmtDate(lead.position.opened)}`
              : "waiting for the prices to tie"}
          </div>
        </div>
        <div className="metric">
          <div
            className={`value${s.today.eg < s.spread_gate.crit ? "" : " muted"}`}
          >
            {num(s.today.eg)}
          </div>
          <div className="label">Statistic today</div>
          <div className="sub">trades below {num(s.spread_gate.crit, 1)}</div>
        </div>
        <div className="metric">
          <div className="value">
            {lead.net_futures_bps == null ? "n/a" : bps(lead.net_futures_bps)}
          </div>
          <div className="label">Net a trade so far</div>
          <div className="sub">institutional single-stock futures</div>
        </div>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Version</th>
              <th className="num">Completed</th>
              <th className="num">Open</th>
              <th className="num">Net a trade, futures</th>
              <th className="num">Net a trade, shares</th>
            </tr>
          </thead>
          <tbody>
            {rows
              .filter(([, , r]) => r)
              .map(([name, sub, r]) => (
                <tr key={name}>
                  <td>
                    {name}
                    {sub && <span className="muted small"> · {sub}</span>}
                  </td>
                  <td className="num">{r!.complete}</td>
                  <td className="num">{r!.position.open ? 1 : 0}</td>
                  <td className="num">{bps(r!.net_futures_bps)}</td>
                  <td className="num">{bps(r!.net_cash_bps)}</td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
      <p className="note">
        The judgement comes at 40 completed trades or at the end of 2036,
        whichever is first. The two copula strategies the project also followed
        are still recorded ({s.switch.complete} and {s.copula_alone.complete}{" "}
        trades since 1 April, {bps(s.copula_alone.net_futures_bps)} a trade) and
        are no longer the project&apos;s focus.
      </p>
    </div>
  );
}

function How() {
  return (
    <section className="panel">
      <ul className="method">
        <li>
          <strong>The pair</strong>
          Standard Bank and Nedbank, daily since 2005, from Yahoo Finance; the
          16:00 prices from Yahoo&apos;s hourly bars. Prices are fetched when
          the page is used and not stored.
        </li>
        <li>
          <strong>Tied together</strong>
          Each session, log Nedbank is regressed on log Standard Bank over the
          previous 126 sessions, and the Engle-Granger statistic tests whether
          the gap from that line keeps returning to zero. Below −2.8 the two
          count as tied.
        </li>
        <li>
          <strong>The trade</strong>
          While tied: open when the gap passes 1.5 standard deviations, betting
          it closes; shut it when the gap is back to zero, passes 4, or after 60
          sessions. The two legs are sized by the regression slope at entry.
        </li>
        <li>
          <strong>Costs</strong>
          Institutional single-stock futures: commission and the exchange fee
          with VAT, a half-spread, funding on each leg and the cost of rolling
          at expiry. Shares are shown beside them, with the 0.25% securities
          transfer tax on purchases.
        </li>
        <li>
          <strong>The search</strong>
          The rule was chosen from a search on data to March 2026, so its
          backtest is flattered. The rule lab shows by how much, and what the
          same rule does on 22 other JSE pairs: the four other Big Four bank
          pairs and 18 that share a sector.
        </li>
      </ul>
    </section>
  );
}

export function App({ embedded }: { embedded: boolean }) {
  const [tab, setTab] = useState<Tab>(
    () => (new URLSearchParams(location.search).get("tab") as Tab) || "lab",
  );
  const [sw, setSw] = useState<Switch | null>(null);
  useEffect(() => {
    const load = () => getSwitch().then(setSw, () => setTimeout(load, 15000));
    load();
  }, []);
  return (
    <main className="preview">
      <header className="head">
        <div>
          <p className="eyebrow">Standard Bank against Nedbank</p>
          {!embedded && (
            <h1 className="serif">
              Trade the gap, <em>only while the two are tied</em>
            </h1>
          )}
        </div>
        <div className="status">
          <span>
            <i className={`dot${sw ? "" : " stale"}`} />
            {sw ? `Live prices to ${fmtDate(sw.as_of)}` : "Loading live prices"}
          </span>
          <span>Rules fixed on data to 31 Mar 2026</span>
        </div>
      </header>
      <nav className="tabs" role="tablist">
        {(
          [
            ["lab", "Find a rule"],
            ["watch", "Watch it trade"],
            ["live", "Live record"],
            ["how", "How it works"],
          ] as [Tab, string][]
        ).map(([id, label]) => (
          <button
            key={id}
            role="tab"
            aria-selected={tab === id}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </nav>
      {tab === "lab" && <RuleLab />}
      {tab === "watch" && <WatchItTrade live={sw} />}
      {tab === "live" && <LiveRecord s={sw} />}
      {tab === "how" && <How />}
      <p className="footer-note">
        Backtests and a live paper record, not investment advice. The
        half-spreads and funding in the costs are assumptions.
        {embedded
          ? ""
          : " Source: github.com/Sbusiso-Mdingi/jse-statistical-arbitrage."}
      </p>
    </main>
  );
}
