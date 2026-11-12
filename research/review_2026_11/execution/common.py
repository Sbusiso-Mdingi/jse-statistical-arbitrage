import csv, math, sys, datetime as dt
from collections import defaultdict
import numpy as np
REPO = __import__("os").path.abspath(__import__("os").path.join(__import__("os").path.dirname(__file__), "..", "..", ".."))  # the repository root
sys.path.insert(0, REPO + "/research"); sys.path.insert(0, REPO + "/research/models"); sys.path.insert(0, REPO + "/service")
from pairdata import load_pair
from app import switch as sw
sw.EXPIRIES = sw.third_thursdays(2004, 2031)
CUT = dt.date(2026, 3, 31)

def load():
    d = load_pair()
    keep = np.array([t <= CUT for t in d["date"]])
    dates = [t for t in d["date"] if t <= CUT]
    lr_s, lr_n = d["r_sbk"][keep], d["r_ned"][keep]
    return dates, lr_s, lr_n

def daily_raw(name):
    out = {}
    for r in csv.DictReader(open(f"{REPO}/data/raw/{name}.csv")):
        try:
            dd = dt.date.fromisoformat(r["date"])
            if dd <= CUT: out[dd] = (float(r["close"]), float(r["adjusted"]))
        except ValueError:
            pass
    return out

def bars(name):
    """date -> {utc hour: (open, close, volume)}; bar time is its opening time."""
    b = defaultdict(dict)
    for r in csv.DictReader(open(f"{REPO}/data/raw/{name}_60m.csv")):
        t = dt.datetime.utcfromtimestamp(int(r["time"]))
        if t.date() <= CUT:
            b[t.date()][t.hour] = (float(r["open"]), float(r["close"]), float(r["Volume"] or 0))
    return b

def h16_trades(dates, x, y, crit=sw.GATE_CRIT, b=None, z=None, eg=None):
    if b is None:
        b, z, eg = sw.rolling(x, y)
    dev = np.array([t >= dt.date(2006, 1, 3) for t in dates])
    gate = ((eg < crit) & dev).astype(np.int8)
    trs = sw.trades(gate, np.full(len(dates), 0.5), b, z, copula_on=False, hold_through=True)
    return trs, b, z, eg

def per_trade(trs, dates, rs, rn, sched):
    _, rows = sw.daily_returns(trs, dates, rs, rn, sched)
    return [r for r in rows if r["complete"] and dates[r["open"]] >= dt.date(2006, 1, 1)]

def summ(v):
    v = np.asarray(v) * 1e4
    return dict(n=len(v), mean=round(float(v.mean()), 1), t=round(float(v.mean() / (v.std(ddof=1) / math.sqrt(len(v)))), 2), median=round(float(np.median(v)), 1))
