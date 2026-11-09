"""Trading the pair through single stock futures or CFDs (research/PROTOCOL.md, "Amendment: trading the pair
through derivatives"). Reporting only: same positions, same gross returns as research/pair.py; only the costs change.
Writes research/results/derivative_costs.json.

Sources, retrieved 9 November 2026:
- JSE, 2026 Price List, Issuers Services and Trading, p26: single stock futures 0.548 bps on screen, 0.957 reported,
  of the underlying value, excluding VAT. No securities transfer tax is charged on a futures or CFD trade: the
  STT Act taxes transfers of a "security", defined as a share or depository receipt (or members' interest), and
  neither contract is one. Physically settled futures held to expiry would transfer shares; these are rolled first.
- JSE Clear, All Contract Details Report, 6 November 2026: SBK and NED futures are 100 shares a contract, initial
  margin R3,779 and R4,489 (about 12% and 15% of value); expiries on the third Thursday of each month. The JSE's
  daily statistics for 6 November 2026 show no SBK or NED futures trades, so there is no screen spread to quote.
- Standard Bank Online Share Trading fees: R50 plus VAT a trade on Top 40 futures; "0.4% of the value of the underlying
  traded value" included in the bid and offer; no additional fee for shorting.
- PSG, Single Stock Futures key information document, 27 August 2026: brokerage 0.4% plus VAT, market maker's fee
  0.1% plus VAT; funding at about prime less 2% on longs, earned at about prime less 2% on shorts.
- IG South Africa, share CFD product details, 7 August 2026: commission 0.20%, minimum R50; financing at benchmark
  plus or minus a funding adjustment of usually 2.5% a year; short borrow charge including a 0.5% administration fee.
  IG South Africa's charges page says it no longer provides trading accounts.
- Sharenet fee schedule: CFD brokerage 0.30%, minimum R115; financing at the market rate plus 2% on longs, less 2% on shorts.
- SARB, current market rates, 9 November 2026: three-month JIBAR 7.25%, prime 10.75%.
VAT at 15% is charged on every commission and fee. Financing is charged as the spread over the benchmark, the
benchmark being the opportunity cost of capital as in the cash schedule. Assumptions are marked and varied: the
institutional futures commission and dealer spread, the CFD half-spread, the short borrow and the futures funding
spread where no figure was published. Account and administration fees are left out, as for the cash schedule.
"""
import csv, json, math, sys
import datetime as dt
import numpy as np
sys.path.insert(0, "research"); sys.path.insert(0, "research/models"); sys.path.insert(0, "service")
from h5_weights import positions, PERIODS  # noqa: E402
from costs import TIERS as CASH, VAT, round_trip as cash_round_trip, costs as cash_costs  # noqa: E402
from pairdata import load_pair  # noqa: E402

HOLD = 5
CAPITAL = 250_000.0  # rand; R125,000 a leg, about four futures contracts each. Only the flat fees depend on it.
d = load_pair()
gas = {r["date"]: float(r["h"]) for r in csv.DictReader(open("research/results/copulas_py.csv")) if r["model"] == "gas_t"}
keep = [i for i, x in enumerate(d["date"]) if x.isoformat() in gas]
dates = [d["date"][i].isoformat() for i in keep]; n = len(dates)
h = np.array([gas[x] for x in dates])
rs, rn = np.expm1(d["r_sbk"][keep]), np.expm1(d["r_ned"][keep])
spread = 0.5 * (rs - rn)
years = np.array([int(x[:4]) for x in dates])
sig_idx = np.flatnonzero((np.abs(h - 0.5) > 0.45) & (np.arange(n) + HOLD < n))
direction = np.where(h[sig_idx] > 0.5, 1.0, -1.0)
pos = positions(h)

JSE_SSF = 0.548  # bps, on screen
SCHEDULES = {
    "ssf_institutional": dict(label="Futures, institutional", commission=5.0, min_rand=0.0, flat_rand=0.0, exchange=JSE_SSF, half_spread=10.0,
                              funding_long=0.5, funding_short=0.5, borrow=0.0, rolls=True,
                              assumed=["commission", "half_spread", "funding"]),
    "ssf_standard_bank": dict(label="Futures, Standard Bank online", commission=0.0, min_rand=0.0, flat_rand=50.0, exchange=JSE_SSF, half_spread=40.0,
                              funding_long=2.0, funding_short=2.0, borrow=0.0, rolls=True, assumed=["funding"]),
    "ssf_psg": dict(label="Futures, PSG", commission=50.0, min_rand=0.0, flat_rand=0.0, exchange=JSE_SSF, half_spread=0.0,
                    funding_long=1.5, funding_short=-1.5, borrow=0.0, rolls=True, assumed=[]),
    "cfd_ig": dict(label="CFD, IG", commission=20.0, min_rand=50.0, flat_rand=0.0, exchange=0.0, half_spread=5.0,
                   funding_long=2.5, funding_short=2.5, borrow=1.0, rolls=False, assumed=["half_spread", "borrow"]),
    "cfd_sharenet": dict(label="CFD, Sharenet", commission=30.0, min_rand=115.0, flat_rand=0.0, exchange=0.0, half_spread=5.0,
                         funding_long=2.0, funding_short=2.0, borrow=1.0, rolls=False, assumed=["half_spread", "borrow"]),
}
# PSG: longs pay prime - 2% = 8.75% and shorts earn the same, 1.5 points either side of JIBAR, so the pair nets to zero.
# Standard Bank publishes no futures funding rate; 2% either side is assumed, as for the CFD providers.


def per_exec_bps(s):
    leg = 0.5 * CAPITAL
    commission = max(s["commission"] / 1e4 * leg, s["min_rand"]) + s["flat_rand"]
    return (commission / leg * 1e4 + s["exchange"]) * (1 + VAT) + s["half_spread"]


def round_trip(s):
    """Open and close once over a five-day hold, in bps of capital: four executions at half of capital, plus financing."""
    fin = 0.5 * (s["funding_long"] + s["funding_short"] + s["borrow"]) * 1e2 * HOLD / 252
    return 4 * 0.5 * per_exec_bps(s) + fin


def third_thursdays(y0=2009, y1=2027):
    out = []
    for y in range(y0, y1 + 1):
        for m in range(1, 13):
            first = dt.date(y, m, 1)
            out.append(first + dt.timedelta(days=(3 - first.weekday()) % 7 + 14))
    return out


EXPIRIES = third_thursdays()


def daily_costs(s):
    pe = per_exec_bps(s) / 1e4
    prev = np.concatenate([[0.0], pos[:-1]])
    dpos = pos - prev
    c = np.abs(dpos) * pe  # both legs, each 0.5 * |d| of capital
    c += 0.5 * np.abs(prev) * (s["funding_long"] + s["funding_short"] + s["borrow"]) / 100 / 252
    rolls = 0
    if s["rolls"]:
        # Open in the first expiry at least ten sessions away; roll both legs when a held spell reaches it.
        expiry = None
        for t in range(n):
            today = dt.date.fromisoformat(dates[t])
            if pos[t] != 0 and (prev[t] == 0 or np.sign(pos[t]) != np.sign(prev[t])):
                ahead = dt.date.fromisoformat(dates[min(t + 10, n - 1)])
                expiry = next(e for e in EXPIRIES if e >= ahead)
            elif pos[t] != 0 and expiry is not None and today >= expiry:
                c[t] += 2 * np.abs(pos[t]) * pe  # close and reopen both legs
                rolls += 1
                ahead = dt.date.fromisoformat(dates[min(t + 10, n - 1)])
                expiry = next(e for e in EXPIRIES if e >= ahead)
    return c, rolls


def stats(x):
    eq = np.cumprod(1 + x); sd = x.std(ddof=1)
    return {"sharpe": round(float(x.mean() / sd * math.sqrt(252)), 2) if sd > 0 else 0.0,
            "cagr": round(float(eq[-1] ** (252 / len(x)) - 1), 4)}


def per_signal(lag):
    vals, yrs = [], []
    for t, dd in zip(sig_idx, direction):
        a = t + 1 + lag
        if a + HOLD > n:
            continue
        vals.append(dd * spread[a:a + HOLD].sum() * 1e4); yrs.append(years[t])
    return np.array(vals), np.array(yrs)


PER = (("2010_2019", 2010, 2020), ("2021_2026", 2021, 2100))
SPANS = {"design": PERIODS["design"], "validation": PERIODS["validation"], "full": ("2010-01-01", "2026-04-01")}
held = np.concatenate([[0.0], pos[:-1]]); gross = held * spread
gs = {lag: per_signal(lag) for lag in (0, 1)}


def report(c, rt):
    net = gross - c
    rec = {"round_trip_bps": round(rt, 1)}
    for lag in (0, 1):
        v, y = gs[lag]
        rec[f"net_per_signal_lag{lag}"] = {nm: round(float(v[(y >= lo) & (y < hi)].mean() - rt), 1) for nm, lo, hi in PER}
    for sp, (a, b) in SPANS.items():
        m = np.array([a <= x < b for x in dates]); rec[sp] = stats(net[m])
    return rec


out = {"capital_rand": CAPITAL, "gross_per_signal": {f"lag{lag}": {nm: round(float(gs[lag][0][(gs[lag][1] >= lo) & (gs[lag][1] < hi)].mean()), 1) for nm, lo, hi in PER} for lag in (0, 1)},
       "cash": {}, "derivatives": {}, "sensitivity": {}}
for k in ("institutional", "retail"):
    out["cash"][k] = {"label": CASH[k]["label"], **report(cash_costs(pos, CASH[k]), cash_round_trip(CASH[k]) + 0.5 * CASH[k]["borrow"] * HOLD / 252)}
for k, s in SCHEDULES.items():
    c, rolls = daily_costs(s)
    out["derivatives"][k] = {"label": s["label"], "per_execution_bps": round(per_exec_bps(s), 2), "rolls": rolls, "assumed": s["assumed"], **report(c, round_trip(s))}
# The one schedule that could beat cash rests on two assumptions; vary them.
for hs in (5.0, 10.0, 20.0):
    for cm in (2.0, 5.0, 10.0):
        s = {**SCHEDULES["ssf_institutional"], "half_spread": hs, "commission": cm}
        c, _ = daily_costs(s)
        out["sensitivity"][f"half_spread_{hs:g}_commission_{cm:g}"] = report(c, round_trip(s))
json.dump(out, open("research/results/derivative_costs.json", "w"), indent=1)
print("gross per signal", out["gross_per_signal"])
for grp in ("cash", "derivatives"):
    for k, r in out[grp].items():
        print(f"{k:20s} rt {r['round_trip_bps']:6.1f}  net/signal lag0 {r['net_per_signal_lag0']}  lag1 {r['net_per_signal_lag1']}  SR design {r['design']['sharpe']:5.2f} valid {r['validation']['sharpe']:5.2f}  rolls {r.get('rolls','-')}")
for k, r in out["sensitivity"].items():
    print(f"{k:32s} rt {r['round_trip_bps']:5.1f}  lag0 {r['net_per_signal_lag0']}  lag1 {r['net_per_signal_lag1']}")
