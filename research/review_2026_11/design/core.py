"""Scratch harness. Development data only: everything truncated to 2026-03-31."""
import sys, math, csv, os, datetime as dt
import numpy as np
REPO = __import__("os").path.abspath(__import__("os").path.join(__import__("os").path.dirname(__file__), "..", "..", ".."))  # the repository root
sys.dont_write_bytecode = True
sys.path.insert(0, REPO + "/research"); sys.path.insert(0, REPO + "/research/models"); sys.path.insert(0, REPO + "/service")
os.chdir(REPO)
from pairdata import load_pair
from app import switch as sw
sw.EXPIRIES = sw.third_thursdays(2004, 2031)
END = dt.date(2026, 3, 31); START = dt.date(2006, 1, 3)

d = load_pair()
keep = [i for i, t in enumerate(d["date"]) if t <= END]
dates = [d["date"][i] for i in keep]; n = len(dates)
lr_s, lr_n = d["r_sbk"][keep], d["r_ned"][keep]
x, y = np.cumsum(lr_s), np.cumsum(lr_n)
rs, rn = np.expm1(lr_s), np.expm1(lr_n)
assert dates[-1] <= END
dev = np.array([t >= START for t in dates])


def wstats(x, y, L=126):
    out = {k: np.full(len(x), np.nan) for k in ("a", "b", "s", "z", "eg", "phi")}
    for t in range(L - 1, len(x)):
        xi, yi = x[t - L + 1:t + 1], y[t - L + 1:t + 1]
        b, z, eg = sw.window_stats(xi, yi)
        a = yi.mean() - b * xi.mean(); u = yi - a - b * xi
        out["a"][t], out["b"][t], out["z"][t], out["eg"][t] = a, b, z, eg
        out["s"][t] = math.sqrt(u @ u / (L - 2))
        out["phi"][t] = float(u[1:] @ u[:-1] / (u[:-1] @ u[:-1]))
    return out


def h_series():
    h = {}
    for r in csv.DictReader(open("research/results/h14_daily.csv")):
        t = dt.date.fromisoformat(r["date"])
        if t <= END:
            h[t] = float(r["h"])
    return np.array([h.get(t, np.nan) for t in dates])


def sim(z, b, gate, entry=1.5, exit_=0.0, stop=4.0, hold=60, lag=0, exit_on_gate=False, size=None, enter_ok=None,
        zexit=None):
    """One trade at a time. Signal at close t, filled at close t+lag with b from the signal close. Exit decided on
    z (or zexit) at close j, filled at close j+lag. A new trade may be signalled on the exit-signal close."""
    ze = z if zexit is None else zexit
    out = []; t = 0; N = len(z)
    while t < N:
        if gate[t] and dev[t] and not np.isnan(z[t]) and abs(z[t]) > entry and (enter_ok is None or enter_ok[t]):
            side = -1 if z[t] > 0 else 1; k = abs(b[t]); m = 1.0 if size is None else float(size[t])
            o = t + lag
            if o >= N - 1:
                break
            jsig = None; reason = "open"; held = 0
            for j in range(t + 1, N):
                held += 1
                zj = ze[j]
                if (side == -1 and zj < exit_) or (side == 1 and zj > -exit_): reason = "target"
                elif abs(zj) > stop: reason = "stop"
                elif held >= hold: reason = "time"
                elif exit_on_gate and not gate[j]: reason = "gate"
                else: continue
                jsig = j; break
            close = None if jsig is None or jsig + lag >= N else jsig + lag
            out.append({"open": o, "close": close, "method": "spread", "side": side, "w_sbk": -side * k / (1 + k) * m,
                        "w_ned": side / (1 + k) * m, "reason": reason if close is not None else "open", "sig": t,
                        "z0": float(z[t]), "b0": float(b[t]), "jsig": jsig})
            if close is None:
                break
            t = jsig
        else:
            t += 1
    return out


def score(trs, sched="futures"):
    tot, rows = sw.daily_returns(trs, dates, rs, rn, sched)
    rows = [dict(r, reason=trs[i].get("reason")) for i, r in enumerate(rows)]
    done = [r for r in rows if r["complete"]]
    v = np.array([r["net"] for r in done]) * 1e4
    dd = tot[dev]; eq = np.cumsum(dd); mdd = float((eq - np.maximum.accumulate(eq)).min()) * 1e4
    sh = float(dd.mean() / dd.std() * math.sqrt(252)) if dd.std() > 0 else float("nan")
    res = {"n": len(v), "bps": round(float(v.mean()), 1) if len(v) else None,
           "t": round(float(v.mean() / (v.std(ddof=1) / math.sqrt(len(v)))), 2) if len(v) > 2 else None,
           "sum": round(float(v.sum())), "sharpe": round(sh, 2), "mdd": round(mdd),
           "win": round(float((v > 0).mean()), 2) if len(v) else None}
    return res, done, tot


ERAS = [("2006-01-01", "2013-01-01"), ("2013-01-01", "2020-01-01"), ("2020-01-01", "2026-04-01")]


def eras(done):
    o = []
    for a, b_ in ERAS:
        v = [r["net"] * 1e4 for r in done if a <= dates[r["open"]].isoformat() < b_]
        o.append((len(v), round(float(np.mean(v)), 1) if v else None))
    return o


def line(name, trs, extra=""):
    r, done, _ = score(trs)
    c = score(trs, "cash")[0]["bps"]
    print(f"{name:42s} n={r['n']:3d} fut={r['bps']} t={r['t']} cash={c} sum={r['sum']} SR={r['sharpe']} mdd={r['mdd']} win={r['win']} eras={eras(done)} {extra}", flush=True)
    return r
