import math, numpy as np
B = np.load("/tmp/jse-review/copula/base.npz"); dates = list(B["dates"]); N = len(dates)
h = np.load("/tmp/jse-review/copula/h.npy"); ok = ~np.isnan(h); yr = np.array([int(x[:4]) for x in dates])
sp = 0.5 * (B["rs"] - B["rn"]); cs = np.concatenate([[0.0], np.cumsum(sp)])
sig = np.flatnonzero(ok & (np.abs(h - .5) > .45) & (np.arange(N) + 7 < N)); s = np.sign(h[sig] - .5)
g = s * (cs[sig + 6] - cs[sig + 1]) * 1e4
cl = np.cumsum(np.concatenate([[1], np.diff(sig) > 5]))
for nm, lo, hi in [("2010-19", 2010, 2020), ("2021-26Q1", 2021, 2027)]:
    m = (yr[sig] >= lo) & (yr[sig] < hi); x = g[m]; c = cl[m]
    mu = x.mean(); sums = np.array([np.sum(x[c == k] - mu) for k in np.unique(c)])
    se_c = math.sqrt(np.sum(sums ** 2)) / len(x)
    print(f"{nm}: mean {mu:.1f}, iid se {x.std(ddof=1)/math.sqrt(len(x)):.1f}, cluster-robust se {se_c:.1f} ({len(np.unique(c))} clusters)")
for nm, lo, hi in [("2010-14",2010,2015),("2015-19",2015,2020),("2021-23",2021,2024),("2024-26Q1",2024,2027)]:
    m=(yr>=lo)&(yr<hi); print(nm, "mean daily rel return %.2f bps -> 5d drift %.1f bps" % (sp[m].mean()*1e4, sp[m].mean()*5e4))
