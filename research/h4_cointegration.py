"""H4: the classic cointegration trade on SBK and NED (research/PROTOCOL.md).

A rolling OLS of log NED on log SBK gives the hedge ratio and the z-score of today's residual. H4a trades
the z-score whenever it is extreme; H4b opens only when the Engle-Granger test on the same window rejects
no cointegration at 5%. The best of 18 rules for each is chosen on design data and validated once.
"""
import csv, json, math, sys
from datetime import date
import numpy as np

sys.path.insert(0, "service")
sys.path.insert(0, "research")
from app.data import drop_bad_prints  # noqa: E402
import h1_evaluate as h1  # noqa: E402

COST = 10 / 1e4
STOP, MAX_HOLD = 4.0, 60
EG_CRIT = -3.34
LOOKBACKS, ENTRIES, EXITS = (126, 252, 504), (1.5, 2.0, 2.5), (0.0, 0.5)
PERIODS = {
    "design": ("2010-01-01", "2020-01-01"),
    "validation": ("2020-01-01", "2026-04-01"),
    "post-freeze": ("2026-04-01", "2100-01-01"),
}


def load(name):
    rows = csv.DictReader(open(f"data/raw/{name}.csv"))
    s = {date.fromisoformat(r["date"]): float(r["adjusted"]) for r in rows if r["adjusted"] not in ("", "NA") and float(r["adjusted"]) > 0}
    return drop_bad_prints(s)


sbk, ned = load("sbk"), load("ned")
days = sorted(set(sbk) & set(ned))
dates = [d.isoformat() for d in days]
ps = np.array([sbk[d] for d in days])
pn = np.array([ned[d] for d in days])
x, y = np.log(ps), np.log(pn)
rs = np.concatenate([[0.0], ps[1:] / ps[:-1] - 1])
rn = np.concatenate([[0.0], pn[1:] / pn[:-1] - 1])
n = len(days)


def rolling(L):
    """Hedge ratio, z-score and Engle-Granger statistic at each close, from the last L sessions to it."""
    b = np.full(n, np.nan); z = np.full(n, np.nan); eg = np.full(n, np.nan)
    for t in range(L - 1, n):
        xi, yi = x[t - L + 1:t + 1], y[t - L + 1:t + 1]
        X = np.column_stack([np.ones(L), xi])
        coef, *_ = np.linalg.lstsq(X, yi, rcond=None)
        u = yi - X @ coef
        sd = u.std(ddof=2)
        b[t], z[t] = coef[1], u[-1] / sd
        # ADF on the residuals: du_t = g u_{t-1} + c du_{t-1} + e, no constant.
        du = np.diff(u)
        A = np.column_stack([u[1:-1], du[:-1]])
        yy = du[1:]
        g, *_ = np.linalg.lstsq(A, yy, rcond=None)
        e = yy - A @ g
        s2 = e @ e / (len(yy) - 2)
        se = math.sqrt(s2 * np.linalg.inv(A.T @ A)[0, 0])
        eg[t] = g[0] / se
    return b, z, eg


def positions(b, z, eg, e, xexit, gate):
    """Weights on NED and SBK set at each close, and the trades."""
    wn = np.zeros(n); ws = np.zeros(n)
    side, held, cur = 0, 0, (0.0, 0.0)
    for t in range(n):
        if side and not np.isnan(z[t]):
            held += 1
            back = (side == -1 and z[t] < xexit) or (side == 1 and z[t] > -xexit)
            if back or abs(z[t]) > STOP or held >= MAX_HOLD:
                side, cur = 0, (0.0, 0.0)
        if not side and not np.isnan(z[t]) and abs(z[t]) > e and (not gate or eg[t] < EG_CRIT):
            # z above e: NED rich, so short NED and long SBK (side -1 on the spread).
            side, held = (-1 if z[t] > 0 else 1), 0
            k = abs(b[t])
            cur = (side / (1 + k), -side * k / (1 + k))
        wn[t], ws[t] = cur
    return wn, ws


def daily(wn, ws, cost=COST):
    hn = np.concatenate([[0.0], wn[:-1]]); hs = np.concatenate([[0.0], ws[:-1]])
    turn = np.abs(np.diff(np.concatenate([[0.0], wn]))) + np.abs(np.diff(np.concatenate([[0.0], ws])))
    # As in H1: a change of position at the close of t is paid on day t and the new position earns t + 1.
    return hn * rn + hs * rs - turn * cost


def evaluate(net, wn, start, end):
    m = np.array([start <= d < end for d in dates])
    r, p = net[m], wn[m]
    eq = np.cumprod(1 + r)
    yrs = len(r) / 252
    sd = r.std(ddof=1)
    down = math.sqrt(np.mean(np.minimum(r, 0) ** 2))
    prev = np.concatenate([[0.0], wn[:-1]])[m]
    return dict(
        start=dates[int(np.argmax(m))], end=dates[n - 1 - int(np.argmax(m[::-1]))],
        sharpe=round(float(r.mean() / sd * math.sqrt(252)), 2) if sd > 0 else 0.0,
        sortino=round(float(r.mean() / down * math.sqrt(252)), 2) if down > 0 else 0.0,
        cagr=round(float(eq[-1] ** (1 / yrs) - 1), 4), total=round(float(eq[-1] - 1), 4),
        mdd=round(float((eq / np.maximum.accumulate(eq) - 1).min()), 4),
        in_market=round(float((p != 0).mean()), 3),
        entries=int(((p != 0) & (np.sign(prev) != np.sign(p))).sum()),
    )


grid = []
rolled = {L: rolling(L) for L in LOOKBACKS}
for L in LOOKBACKS:
    b, z, eg = rolled[L]
    for e in ENTRIES:
        for xe in EXITS:
            for gate in (False, True):
                wn, ws = positions(b, z, eg, e, xe, gate)
                net, gross = daily(wn, ws), daily(wn, ws, 0.0)
                grid.append(dict(
                    test="H4b" if gate else "H4a", lookback=L, entry=e, exit=xe,
                    **{name: {"after_costs": evaluate(net, wn, s, t), "before_costs": evaluate(gross, wn, s, t)}
                       for name, (s, t) in PERIODS.items()}))

out = {"rules": grid, "chosen": {}}
for test in ("H4a", "H4b"):
    rules = [r for r in grid if r["test"] == test]
    best = max(rules, key=lambda r: r["design"]["after_costs"]["sharpe"])
    out["chosen"][test] = best
    v = best["validation"]["after_costs"]["sharpe"]
    print(f"{test}: L={best['lookback']} e={best['entry']} x={best['exit']}  verdict {'passed' if v > 0 else 'failed'}")
    for name in PERIODS:
        for k in ("after_costs", "before_costs"):
            r = best[name][k]
            print(f"  {name:12s} {k:13s} SR {r['sharpe']:5.2f}  Sortino {r['sortino']:5.2f}  CAGR {r['cagr']*100:5.1f}%  MDD {r['mdd']*100:6.1f}%  entries {r['entries']:3d}  in market {r['in_market']:.2f}")

# Share of design days on which the gate was open, per lookback: how often the classic method would have had a pair at all.
out["gate_open_share"] = {}
for L in LOOKBACKS:
    eg = rolled[L][2]
    out["gate_open_share"][str(L)] = {name: round(float(np.mean([eg[i] < EG_CRIT for i in range(n) if s <= dates[i] < t and not np.isnan(eg[i])])), 3)
                                      for name, (s, t) in PERIODS.items()}
print("gate open share", out["gate_open_share"])

# Each chosen rule against H1 in validation, on paired daily net returns. Reported, not part of the pass mark.
h1_net = dict(zip(h1.dates, h1.net_returns()))
for test, r in out["chosen"].items():
    net = dict(zip(dates, daily(*positions(*rolled[r["lookback"]], r["entry"], r["exit"], test == "H4b"))))
    lo, hi = PERIODS["validation"]
    diff = np.array([net[d] - h1_net[d] for d in dates if lo <= d < hi and d in h1_net])
    r["vs_h1_validation"] = {"bps_per_year": round(float(diff.mean() * 252 * 1e4), 1),
                             "t_stat": round(float(diff.mean() / (diff.std(ddof=1) / math.sqrt(len(diff)))), 2), "days": len(diff)}
    print(test, "vs H1 in validation", r["vs_h1_validation"])
json.dump(out, open("research/results/h4.json", "w"), indent=1)
