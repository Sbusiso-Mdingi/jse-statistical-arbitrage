import sys; sys.path.insert(0, "/tmp/jse-review/overfit")
from common import *
from scipy import stats
d, dates, x, y, rs, rn, dev = setup(); n = len(dates)
b, z, eg = rolling(x, y, 126)
trs = run_rule(eg < -2.8, b, z, dev)
daily, rows = score(trs, dates, rs, rn)
v = np.array([r["net"] for r in rows]) * 1e4; h = np.array([r["close"] - r["open"] for r in rows])
dr = daily[dev] * 1e4
inm = np.zeros(n, bool)
for r in rows: inm[r["open"] + 1:r["close"] + 1] = True
gross_d = np.zeros(n)
for r in rows: gross_d[r["open"]+1:r["close"]+1] = (r["w_sbk"] * rs + r["w_ned"] * rn)[r["open"]+1:r["close"]+1] * 1e4
sd_in = gross_d[inm].std()
print("in-market daily gross sd", round(sd_in, 1), "Wald-implied per-trade sd", round(sd_in * np.sqrt(h.mean()), 1), "observed per-trade sd", round(v.std(ddof=1), 1))
def nw(xv, L):
    xv = xv - xv.mean(); T = len(xv); s = xv @ xv / T
    for l in range(1, L + 1): s += 2 * (1 - l / (L + 1)) * (xv[l:] @ xv[:-l]) / T
    return np.sqrt(s / T)
print("daily t iid", round(dr.mean() / (dr.std(ddof=1) / np.sqrt(len(dr))), 2), "NW20", round(dr.mean() / nw(dr, 20), 2), "NW60", round(dr.mean() / nw(dr, 60), 2))
print("ann. return %", round(dr.mean() * 252 / 100, 2), "ann vol %", round(dr.std() * np.sqrt(252) / 100, 2))
# per-trade P&L vs hold length
for lo, hi in ((0, 5), (5, 10), (10, 20), (20, 40), (40, 61)):
    m = (h > lo) & (h <= hi); print(f"hold {lo+1}-{hi}: {m.sum()} trades, mean {v[m].mean():.0f}")
print("corr(net, hold)", np.corrcoef(v, h)[0, 1].round(2))
yrs = np.array([r["d_open"].year for r in rows])
for a, bb in ((2006, 2009), (2010, 2019), (2020, 2026)):
    m = (yrs >= a) & (yrs <= bb); print(a, bb, m.sum(), v[m].mean().round(1), round(tstat(v[m]), 2))
# power of the registered verdict (40 trades, one-sided t>1.65) via resampling the dev trades shifted to a true mean mu
rng = np.random.default_rng(3)
for mu in (91, 60, 45, 30, 0):
    w = v - v.mean() + mu
    s = w[rng.integers(0, len(w), (20000, 40))]
    t = s.mean(1) / (s.std(1, ddof=1) / np.sqrt(40))
    print(f"power at true {mu} bps (dev shape, 40 trades): {np.mean(t > 1.65):.2f}")
