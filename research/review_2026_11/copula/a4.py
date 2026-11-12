import sys, csv, math, datetime as dt
import numpy as np
from scipy import stats as st
sys.path.insert(0, "service")
from app import switch as SW
B = np.load("/tmp/jse-review/copula/base.npz"); dates = list(B["dates"]); N = len(dates)
D = [dt.date.fromisoformat(x) for x in dates]
h = np.load("/tmp/jse-review/copula/h.npy"); h2 = B["h2"]; ok = ~np.isnan(h)
rs, rn = B["rs"], B["rn"]; sp = 0.5 * (rs - rn); cs = np.concatenate([[0.0], np.cumsum(sp)])
yr = np.array([d.year for d in D]); z, eg = B["z"], B["eg"]; u, v = B["u"], B["v"]
sig = np.flatnonzero(ok & (np.abs(h - .5) > .45) & (np.arange(N) + 7 < N)); s = np.sign(h[sig] - .5)
g0 = s * (cs[sig + 6] - cs[sig + 1]) * 1e4      # filled at signal close
g1 = s * (cs[sig + 7] - cs[sig + 2]) * 1e4      # filled at next close
volx = np.sqrt(0.5 * (B["sig_s"] ** 2 + B["sig_n"] ** 2))
med = np.array([np.nanmedian(volx[max(0, t - 252):t]) for t in range(N)])
exdiv = set()
for r in csv.DictReader(open("research/results/h15_events.csv")):
    if r["kind"] == "ex_dividend": exdiv.add(r["date"])
near_ex = np.array([any(dates[k] in exdiv for k in range(max(0, t - 1), min(N, t + 2))) for t in sig])
first = np.array([not np.any(np.abs(h[max(0, t - 5):t] - .5) > .45) for t in sig])
qs, qn = st.norm.ppf(u[sig]), st.norm.ppf(v[sig])
SL = {
    "all": np.ones(len(sig), bool),
    "|h-.5|>.48": np.abs(h[sig] - .5) > .48,
    "|h-.5|>.49": np.abs(h[sig] - .5) > .49,
    "agrees with z (|z|>1 same side)": s * z[sig] > 1,
    "disagrees/neutral z": ~(s * z[sig] > 1),
    "z agrees |z|>2": s * z[sig] > 2,
    "two-sided h2 also in tail": (np.abs(h2[sig] - .5) > .45),
    "high vol (above trailing-yr median)": volx[sig] > med[sig],
    "low vol": volx[sig] <= med[sig],
    "results months (Mar, Aug)": np.isin([D[t].month for t in sig], [3, 8]),
    "not results months": ~np.isin([D[t].month for t in sig], [3, 8]),
    "first of cluster": first,
    "repeat within 5 sessions": ~first,
    "NED-driven (|q_ned|>|q_sbk|)": np.abs(qn) > np.abs(qs),
    "SBK-driven": np.abs(qn) <= np.abs(qs),
    "EG gate open (<-2.8)": eg[sig] < -2.8,
    "near ex-dividend (+-1 day)": near_ex,
    "h>0.5 side (long SBK)": s > 0,
    "h<0.5 side (short SBK)": s < 0,
}
ERAS = [("2010-19", 2010, 2020), ("2021-26Q1", 2021, 2027)]
print("required gross per signal to break even: futures 33.8, cash 59.6 (five-day hold, no roll)")
print(f"{'slice':38s} " + " ".join(f"{nm:>36s}" for nm, _, _ in ERAS))
for k, m in SL.items():
    cells = []
    for nm, lo, hi in ERAS:
        mm = m & (yr[sig] >= lo) & (yr[sig] < hi)
        n = mm.sum()
        if n < 3: cells.append(f"{'n '+str(n):>36s}"); continue
        a, b_ = g0[mm], g1[mm]
        cells.append(f"n{n:4d} close {a.mean():6.1f}({a.std(ddof=1)/math.sqrt(n):4.1f}) next {b_.mean():6.1f}({b_.std(ddof=1)/math.sqrt(n):4.1f})")
    print(f"{k:38s} " + " ".join(cells))
print("slices examined (excluding 'all'):", len(SL) - 1)
