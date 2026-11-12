from common import *
import csv as _csv
dates, ls, ln = load(); n = len(dates)
x, y = np.cumsum(ls), np.cumsum(ln); rs, rn = np.expm1(ls), np.expm1(ln)
trs, b, z, eg = h16_trades(dates, x, y)
done = [t for t in trs if t["close"] is not None and dates[t["open"]] >= dt.date(2006, 1, 1)]
def g(t, lo, lc):
    o, c = t["open"] + lo, t["close"] + lc
    return float(t["w_sbk"] * rs[o + 1:c + 1].sum() + t["w_ned"] * rn[o + 1:c + 1].sum())
base = np.array([g(t, 0, 0) for t in done])
print("lag profile (entry and exit both delayed by k closes): gross, paired diff vs base, se")
for k in range(0, 6):
    v = np.array([g(t, k, k) for t in done]); d = v - base
    print(k, round(v.mean() * 1e4, 1), round(d.mean() * 1e4, 1), round(d.std(ddof=1) / math.sqrt(len(d)) * 1e4, 1))
for lo, lc, lab in ((1, 0, "entry only +1"), (0, 1, "exit only +1")):
    v = np.array([g(t, lo, lc) if t["close"] + lc > t["open"] + lo else 0 for t in done]); d = v - base
    print(lab, round(v.mean() * 1e4, 1), round(d.mean() * 1e4, 1), round(d.std(ddof=1) / math.sqrt(len(d)) * 1e4, 1))
# by era for next close
for a, bnd in (("2006", "2013"), ("2013", "2020"), ("2020", "2027")):
    m = np.array([a <= dates[t["open"]].isoformat()[:4] < bnd for t in done])
    v1 = np.array([g(t, 1, 1) for t in done])
    print("era", a, bnd, "n", m.sum(), "gross base %.1f next-close %.1f" % (base[m].mean() * 1e4, v1[m].mean() * 1e4))

# H14 switch with the copula h, truncated
gas = {r["date"]: float(r["h"]) for r in _csv.DictReader(open(REPO + "/research/results/copulas_py.csv")) if r["model"] == "gas_t"}
keep = np.array([t.isoformat() in gas for t in dates]); first = int(np.argmax(keep))
mode_full = sw.modes(x, y, eg, "E", None)
sl = slice(first, None); D = dates[sl]; h = np.array([gas[t.isoformat()] for t in D])
RS, RN = rs[sl], rn[sl]
T = sw.trades(mode_full[sl], h, b[sl], z[sl])
nn = len(D)
def per(trs, lag, sched, lo="2010-01-01", hi="2020-01-01", method=None):
    tt = [dict(t, open=t["open"] + lag, close=t["close"] + lag) for t in trs if t["close"] is not None and t["close"] + lag < nn
          and lo <= D[t["open"]].isoformat() < hi and (method is None or t["method"] == method)]
    _, rows = sw.daily_returns(tt, D, RS, RN, sched)
    v = np.array([r["net"] for r in rows]) * 1e4
    return len(v), round(float(v.mean()), 1)
for per_lab, lo, hi in (("design", "2010-01-01", "2020-01-01"), ("validation", "2020-01-01", "2026-04-01")):
    for lag in (0, 1):
        print("H14", per_lab, "lag", lag, "all trades futures", per(T, lag, "futures", lo, hi), "spread-mode futures", per(T, lag, "futures", lo, hi, "spread"),
              "copula-mode futures", per(T, lag, "futures", lo, hi, "copula"), "gross all", per(T, lag, None, lo, hi))
