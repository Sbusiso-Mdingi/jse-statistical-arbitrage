import math, numpy as np
B = np.load("/tmp/jse-review/copula/base.npz"); dates = list(B["dates"]); N = len(dates)
h = np.load("/tmp/jse-review/copula/h.npy"); ok = ~np.isnan(h); yr = np.array([int(x[:4]) for x in dates])
sp = 0.5 * (B["rs"] - B["rn"]); cs = np.concatenate([[0.0], np.cumsum(sp)])
sd = np.array([sp[max(0, t - 60):t].std() if t > 20 else np.nan for t in range(N)])
zz = sp / sd
from scipy import stats as st
m = ok & ~np.isnan(zz)
print("rank corr probit(h) vs -z_naive: %.3f" % st.spearmanr(st.norm.ppf(h[m]), -zz[m]).statistic)
thr = 1.71  # two-sided ~8.7% under normal
for name, sg in (("copula h tail", np.where(ok & (np.abs(h - .5) > .45), np.sign(h - .5), 0)), ("naive |spread move|/60d sd > 1.71", np.where(m & (np.abs(zz) > thr), -np.sign(zz), 0))):
    idx = np.flatnonzero((sg != 0) & (np.arange(N) + 7 < N))
    out = []
    for nm, lo, hi in [("2010-19", 2010, 2020), ("2021-26Q1", 2021, 2027)]:
        k = idx[(yr[idx] >= lo) & (yr[idx] < hi)]
        g = sg[k] * (cs[k + 6] - cs[k + 1]) * 1e4; g1 = sg[k] * (cs[k + 7] - cs[k + 2]) * 1e4
        out.append(f"{nm} n {len(k)} close {g.mean():.1f} ({g.std(ddof=1)/math.sqrt(len(k)):.1f}) next {g1.mean():.1f}")
    print(f"{name:36s} " + " | ".join(out))
