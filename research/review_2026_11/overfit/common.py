"""Shared harness. Everything truncated to 2026-03-31 BEFORE cleaning/alignment."""
import csv, math, sys, datetime as dt
import numpy as np
REPO = __import__("os").path.abspath(__import__("os").path.join(__import__("os").path.dirname(__file__), "..", "..", ".."))  # the repository root
sys.path.insert(0, REPO + "/research"); sys.path.insert(0, REPO + "/service")
from h5_weights import _drop_bad_prints  # noqa
from app import switch as sw  # noqa
sw.EXPIRIES = sw.third_thursdays(2004, 2031)
END = dt.date(2026, 3, 31)
START = dt.date(2006, 1, 3)
ERAS = [("2006-01-01", "2013-01-01"), ("2013-01-01", "2020-01-01"), ("2020-01-01", "2026-04-01")]

def read_px(name):
    rows = []
    for r in csv.DictReader(open(f"{REPO}/data/raw/{name}.csv")):
        try:
            a = float(r["adjusted"]); d = dt.date.fromisoformat(r["date"])
        except ValueError:
            continue
        if a > 0 and d <= END:
            rows.append((d, a))
    return _drop_bad_prints(rows)

def load_pair():
    s, n = dict(read_px("sbk")), dict(read_px("ned"))
    dates = sorted(set(s) & set(n))
    vix = {}
    for r in csv.DictReader(open(f"{REPO}/data/raw/vix.csv")):
        try:
            d = dt.date.fromisoformat(r["date"].strip('"'))
            if d <= END: vix[d] = float(r["vix"])
        except ValueError:
            pass
    vd = sorted(vix); vnum = np.array([d.toordinal() for d in vd])
    keep = [d for d in dates if np.searchsorted(vnum, d.toordinal() - 1, side="right") - 1 >= 0]
    ps = np.array([s[d] for d in keep]); pn = np.array([n[d] for d in keep])
    out = {"date": keep[1:], "r_sbk": np.diff(np.log(ps)), "r_ned": np.diff(np.log(pn))}
    assert max(out["date"]) <= END
    return out

def rolling(x, y, L):
    n = len(x); b = np.full(n, np.nan); z = np.full(n, np.nan); eg = np.full(n, np.nan)
    for t in range(L - 1, n):
        b[t], z[t], eg[t] = sw.window_stats(x[t - L + 1:t + 1], y[t - L + 1:t + 1])
    return b, z, eg

def run_rule(gate, b, z, dev, entry=1.5, exit_=0.0, stop=4.0, max_hold=60):
    sw.ENTRY, sw.EXIT, sw.STOP, sw.MAX_HOLD = entry, exit_, stop, max_hold
    try:
        return sw.trades((gate & dev).astype(np.int8), np.full(len(dev), 0.5), b, z, copula_on=False, hold_through=True)
    finally:
        sw.ENTRY, sw.EXIT, sw.STOP, sw.MAX_HOLD = 1.5, 0.0, 4.0, 60

def score(trs, dates, rs, rn, sched="futures", lo="2006-01-01"):
    daily, rows = sw.daily_returns(trs, dates, rs, rn, sched)
    rows = [dict(r, d_open=dates[r["open"]], d_close=dates[r["close"]]) for r in rows if r["complete"] and dates[r["open"]].isoformat() >= lo]
    return daily, rows

def tstat(v):
    v = np.asarray(v); return float(v.mean() / (v.std(ddof=1) / math.sqrt(len(v)))) if len(v) > 2 else float("nan")

def setup():
    d = load_pair(); dates = d["date"]; n = len(dates)
    x, y = np.cumsum(d["r_sbk"]), np.cumsum(d["r_ned"])
    rs, rn = np.expm1(d["r_sbk"]), np.expm1(d["r_ned"])
    dev = np.array([dt_ >= START for dt_ in dates])
    return d, dates, x, y, rs, rn, dev
