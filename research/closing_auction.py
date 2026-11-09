"""Closing auction: the signal computed from the 16:00 prices, filled at the official close (research/PROTOCOL.md).

Each margin's mean and volatility for a session are known before it opens, so the return to the last trade by 16:00
(the close of the 15:00 to 16:00 SAST hourly bar, with the day's dividend adjustment) gives a 16:00 probability
transform for each bank; the H8 copula's correlation and degrees of freedom for the session are unchanged.
Writes research/results/closing_auction.json. Hourly bars: TradingView export, February 2009 to 2 June 2026.
"""
import csv, json, math, sys
import datetime as dt
from collections import defaultdict
import numpy as np
from scipy import stats as st
sys.path.insert(0, "research"); sys.path.insert(0, "research/models"); sys.path.insert(0, "service")
from copulas_py import d, dates, n, folds, ends, gas_fit, gas_score, CL  # noqa: E402
from h5_weights import _filter_full  # noqa: E402
from app.model import pit  # noqa: E402

HOLD, BAR = 5, 13  # bar opening 13:00 UTC = 15:00 SAST, closing 16:00
PERIODS = {"design": ("2010-01-01", "2020-01-01"), "validation": ("2020-01-01", "2026-04-01"), "post_freeze": ("2026-04-01", "2100-01-01")}
RT = {k: v["round_trip_bps"] for k, v in (("cash_institutional", json.load(open("research/results/derivative_costs.json"))["cash"]["institutional"]),
                                          ("futures_institutional", json.load(open("research/results/derivative_costs.json"))["derivatives"]["ssf_institutional"]))}


def bars(name):
    b = defaultdict(dict)
    for r in csv.DictReader(open(f"data/raw/{name}_60m.csv")):
        t = dt.datetime.utcfromtimestamp(int(r["time"])); b[t.date()][t.hour] = float(r["close"])
    return b


def daily(name):
    out = {}
    for r in csv.DictReader(open(f"data/raw/{name}.csv")):
        try:
            out[dt.date.fromisoformat(r["date"])] = (float(r["close"]), float(r["adjusted"]))
        except ValueError:
            pass
    return out


def pre_close_returns(name):
    """log(16:00 price / previous close) + log(adjustment factor today / yesterday); NaN where no bar."""
    b, px = bars(name), daily(name)
    out = np.full(n, np.nan)
    for t in range(1, n):
        a, p = dates[t], dates[t - 1]
        if BAR in b.get(a, {}) and a in px and p in px:
            fac_a, fac_p = px[a][1] / px[a][0], px[p][1] / px[p][0]
            out[t] = math.log(b[a][BAR] / px[p][0]) + math.log(fac_a / fac_p)
    return out


pre = {"sbk": pre_close_returns("sbk"), "ned": pre_close_returns("ned")}
ok = ~np.isnan(pre["sbk"]) & ~np.isnan(pre["ned"])

h_close, h_pre, parity = np.full(n, np.nan), np.full(n, np.nan), 0.0
stored = {r["date"]: float(r["h"]) for r in csv.DictReader(open("research/results/copulas_py.csv")) if r["model"] == "gas_t"}
for k, f in enumerate(folds):
    n_train = sum(1 for x in dates if x.isoformat() <= f["train_end"])
    n_all = sum(1 for x in dates if x.isoformat() <= ends[k + 1]) if k + 1 < len(folds) else n
    if n_all <= n_train:
        continue
    up, uc = {}, {}
    for s in ("sbk", "ned"):
        fm = _filter_full(f[s], d[f"r_{s}"][:n_all], d["vix"][:n_all], n_train)
        sh = f[s]["coef"].get("shape")
        uc[s] = np.clip(fm["u"], CL, 1 - CL)
        z = (np.nan_to_num(pre[s][:n_all]) - fm["mu"]) / fm["sigma"]
        up[s] = np.clip(pit(z, f[s]["dist"], sh), CL, 1 - CL)
    pg = gas_fit(uc["sbk"][:n_train], uc["ned"][:n_train], f["copula"]["par"])
    _, hc, rho, par = gas_score(pg, uc["sbk"], uc["ned"], n_train)
    nu = par["nu"]; sl = slice(n_train, n_all)
    x, y = st.t.ppf(up["sbk"][sl], nu), st.t.ppf(up["ned"][sl], nu)
    h_pre[sl] = st.t.cdf((y - rho * x) / np.sqrt((nu + x * x) * (1 - rho * rho) / (nu + 1)), nu + 1)
    h_close[sl] = hc
    parity = max([parity] + [abs(stored[dates[t].isoformat()] - hc[i]) for i, t in enumerate(range(n_train, n_all)) if dates[t].isoformat() in stored])

rs, rn = np.expm1(d["r_sbk"]), np.expm1(d["r_ned"]); spread = 0.5 * (rs - rn)
ds = np.array([x.isoformat() for x in dates]); idx = np.arange(n)
valid = ~np.isnan(h_close) & ok & (idx + HOLD < n)
sig_c = valid & (np.abs(h_close - 0.5) > 0.45)
sig_p = valid & (np.abs(h_pre - 0.5) > 0.45)
ret = lambda hh, t: (1.0 if hh[t] > 0.5 else -1.0) * spread[t + 1:t + 1 + HOLD].sum() * 1e4


def summ(sig, hh, m):
    v = np.array([ret(hh, t) for t in np.flatnonzero(sig & m)])
    if len(v) < 2:
        return None
    mu, se = float(v.mean()), float(v.std(ddof=1) / math.sqrt(len(v)))
    return {"n": len(v), "gross_bps": round(mu, 1), "se": round(se, 1), **{f"net_{k}": round(mu - c, 1) for k, c in RT.items()}}


out = {"parity_h_close_max_abs": parity, "pre_close_return_corr": {}, "round_trips": RT, "periods": {}}
for s in ("sbk", "ned"):
    m = ok & ~np.isnan(h_close)
    out["pre_close_return_corr"][s] = round(float(np.corrcoef(pre[s][m], d[f"r_{s}"][m])[0, 1]), 3)
for p, (a, b) in PERIODS.items():
    m = (ds >= a) & (ds < b)
    both = sig_c & sig_p & m & (np.sign(h_close - 0.5) == np.sign(h_pre - 0.5))
    out["periods"][p] = {"close_signals": int((sig_c & m).sum()), "pre_signals": int((sig_p & m).sum()), "both_same_side": int(both.sum()),
                         "close_signal_at_close": summ(sig_c, h_close, m), "pre_signal_at_close": summ(sig_p, h_pre, m),
                         "pre_signal_only": summ(sig_p & ~sig_c, h_pre, m), "close_signal_missed_at_16": summ(sig_c & ~sig_p, h_close, m)}
json.dump(out, open("research/results/closing_auction.json", "w"), indent=1)
print(json.dumps(out, indent=1))
