"""Compare dependence models on the pair by out-of-sample log copula density and h calibration.
Usage: compare.py <start> <end> [label]. Diebold-Mariano with Newey-West (5 lags) against static_t."""
import csv, math, sys
import numpy as np
from scipy import stats as st
lo, hi = sys.argv[1], sys.argv[2]
import os
rows = list(csv.DictReader(open(os.environ.get("COPULAS_CSV", "research/results/copulas_py.csv"))))
models = [m for m in ["static_t", "rolling_t_252", "gas_t", "ms_t"] if any(r["model"] == m for r in rows)]
by = {m: {r["date"]: (float(r["logc"]), float(r["h"])) for r in rows if r["model"] == m and lo <= r["date"] < hi} for m in models}
base = by["static_t"]
print(f"{sys.argv[3] if len(sys.argv) > 3 else ''} {lo} to {hi}")
out = {}
for m in models:
    dts = sorted(set(by[m]) & set(base))
    lc = np.array([by[m][dd][0] for dd in dts]); h = np.array([by[m][dd][1] for dd in dts])
    diff = lc - np.array([base[dd][0] for dd in dts])
    mu = diff.mean(); T = len(diff)
    g = lambda k: float(np.sum((diff[k:] - mu) * (diff[:-k] - mu)) / T) if k else float(np.var(diff))
    var = g(0) + 2 * sum((1 - k / 6) * g(k) for k in range(1, 6))
    dm = mu / math.sqrt(var / T) if var > 0 else 0.0
    ks = st.kstest(h, "uniform").pvalue
    fires = float(np.mean(np.abs(h - 0.5) > 0.45))
    dec = np.histogram(h, bins=10, range=(0, 1))[0] / len(h) * 10
    out[m] = dict(n=T, mean_logc=float(lc.mean()), vs_static_per_day=float(mu), dm_t=float(dm), h_ks_p=float(ks), fires=fires)
    print(f"  {m:14s} n {T:4d} mean logc {lc.mean():.4f}  vs static {mu*1e3:+.2f}e-3/day  DM t {dm:5.2f}  h KS p {ks:.3f}  fires {100*fires:4.1f}%  deciles " + " ".join(f"{x:.2f}" for x in dec))
if len(sys.argv) > 4:
    import json; json.dump(out, open(sys.argv[4], "w"), indent=1)
