import sys, csv, math, json
import numpy as np
from scipy import stats as st
B = np.load("/tmp/jse-review/copula/base.npz")
dates = B["dates"]; N = len(dates)
ref = {r["date"]: float(r["h"]) for r in csv.DictReader(open("research/results/copulas_py.csv")) if r["model"] == "gas_t" and r["date"] <= "2026-03-31"}
h = np.array([ref.get(x, np.nan) for x in dates]); h2 = B["h2"]
rs, rn = B["rs"], B["rn"]; sp = 0.5 * (rs - rn)
yr = np.array([int(x[:4]) for x in dates])
ok = ~np.isnan(h)
BLK = [("2010-14", 2010, 2015), ("2015-19", 2015, 2020), ("2020", 2020, 2021), ("2021-23", 2021, 2024), ("2024-26Q1", 2024, 2027)]
def bm(lo, hi): return ok & (yr >= lo) & (yr < hi)
print("== 1a calibration of h (GAS, out of sample) ==")
for nm, lo, hi in BLK + [("2010-19", 2010, 2020), ("2020-26Q1", 2020, 2027)]:
    m = bm(lo, hi); x = h[m]; g = st.norm.ppf(np.clip(x, 1e-9, 1 - 1e-9))
    ac1 = np.corrcoef(g[1:], g[:-1])[0, 1]; ac1a = np.corrcoef(np.abs(g[1:]), np.abs(g[:-1]))[0, 1]
    lb = st.chi2.sf(len(g) * sum((np.corrcoef(g[k:], g[:-k])[0, 1]) ** 2 * (len(g) + 2) / (len(g) - k) for k in range(1, 6)), 5)
    print(f"{nm:10s} n {m.sum():5d} KS p {st.kstest(x,'uniform').pvalue:.3f}  fire {np.mean(np.abs(x-.5)>.45)*100:4.1f}% (10)  h>.95 {np.mean(x>.95)*100:4.1f}% h<.05 {np.mean(x<.05)*100:4.1f}%  |h-.5|>.48 {np.mean(np.abs(x-.5)>.48)*100:4.1f}% (4)  sd(Phi^-1 h) {g.std():.3f}  ac1 {ac1:+.3f} ac1|.| {ac1a:+.3f} LB5 p {lb:.3f}")
# Berkowitz-style: mean/var of probit h overall
cs = np.concatenate([[0.0], np.cumsum(sp)])
def fwd(t, a, k): return cs[t + a + k] - cs[t + a]  # sum sp[t+a .. t+a+k-1]
sig = np.flatnonzero(ok & (np.abs(h - .5) > .45) & (np.arange(N) + 11 <= N - 1))
s = np.where(h[sig] > .5, 1.0, -1.0)
print("\n== 1b event study: s * cumulative relative return (bps), day 0 = signal day's own move ==")
for nm, lo, hi in BLK + [("2010-19", 2010, 2020), ("2021-26Q1", 2021, 2027)]:
    m = (yr[sig] >= lo) & (yr[sig] < hi); t = sig[m]; ss = s[m]
    d0 = ss * sp[t] * 1e4
    path = np.array([[ss[i] * fwd(t[i], 1, k) * 1e4 for k in (1, 2, 3, 5, 10)] for i in range(len(t))])
    se = path.std(0, ddof=1) / math.sqrt(len(t))
    # first-of-cluster (no signal in previous 5 sessions)
    first = np.array([not np.any(np.abs(h[max(0, x - 5):x] - .5) > .45) for x in t])
    print(f"{nm:10s} n {len(t):3d} (first {first.sum():3d}) day0 mean {d0.mean():6.1f} | mean k=1,2,3,5,10: " + " ".join(f"{a:6.1f}" for a in path.mean(0)) + "  se5 %.1f" % se[3] + " | median: " + " ".join(f"{a:6.1f}" for a in np.median(path, 0)) + " | first-only k5 %.1f" % path[first, 3].mean() + " | hit5 %.0f%%" % (100*np.mean(path[:,3]>0)))
print("\n== 1c continuous predictive slope: fwd 5d rel return (bps) on probit(h), all days, and tail-only ==")
g = st.norm.ppf(np.clip(h, 1e-9, 1 - 1e-9))
for nm, lo, hi in BLK + [("2010-19", 2010, 2020), ("2021-26Q1", 2021, 2027)]:
    idx = np.flatnonzero(bm(lo, hi) & (np.arange(N) + 6 <= N - 1))
    f5 = np.array([fwd(t, 1, 5) for t in idx]) * 1e4; f1 = sp[idx + 1] * 1e4
    b5 = np.polyfit(g[idx], f5, 1)[0]; b1 = np.polyfit(g[idx], f1, 1)[0]
    # NW t for slope 5d (overlap): crude via block of non-overlapping every 5th
    sub = idx[::5]; f5s = np.array([fwd(t, 1, 5) for t in sub]) * 1e4
    r = st.linregress(g[sub], f5s)
    print(f"{nm:10s} slope fwd1 {b1:+.2f} bps/sd  fwd5 {b5:+.2f} bps/sd  (non-overlap t {r.slope/r.stderr:+.2f})  corr(g, fwd1) {np.corrcoef(g[idx], f1)[0,1]:+.3f}")
# day 0 spread autocorr per block
print("\n== 2a lag-1 autocorrelation of daily relative return and 5-day variance ratio ==")
for nm, lo, hi in [("2006-09", 2006, 2010)] + BLK:
    m = (yr >= lo) & (yr < hi); x = sp[m]
    ac = np.corrcoef(x[1:], x[:-1])[0, 1]
    x5 = np.add.reduceat(x, np.arange(0, len(x) - len(x) % 5, 5))[: len(x) // 5]
    vr = x5.var() / (5 * x.var())
    print(f"{nm:10s} ac1 {ac:+.3f}  VR5 {vr:.3f}  daily sd {x.std()*1e4:.0f} bps  signals/yr {np.sum(m & ok & (np.abs(h-.5)>.45))/max(1,len(set(yr[m]))):.1f}  |day0| at signals {np.mean(np.abs(sp[m & ok & (np.abs(h-.5)>.45)]))*1e4 if np.any(m&ok) else float('nan'):.0f}")
np.save("/tmp/jse-review/copula/h.npy", h)
