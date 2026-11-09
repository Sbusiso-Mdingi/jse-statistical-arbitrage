"""The edge the instrument measures, year by year: what a signal was worth before costs.

For every day the H1 signal fires (|h - 0.5| > 0.45), the return of the position it points to over
the next five sessions, half of capital a side, before costs; and the next session alone. Grouped by
year with standard errors, against the 20 bps a round trip costs. Writes research/results/edge.json.
Descriptive, like the decay study.
"""
import csv, json, math
import numpy as np

BASKET = ["fsr", "abg", "ned", "cpi"]
HOLD = 5
rows = list(csv.DictReader(open("data/h1_daily.csv")))
dates = [r["date"] for r in rows]
h = np.array([float(r["h"]) for r in rows])
rs = np.array([float(r["sbk"]) for r in rows])
rb = np.array([[float(r[k]) for k in BASKET] for r in rows]).mean(axis=1)
spread = 0.5 * (rs - rb)
n = len(rows)
sig = np.flatnonzero((np.abs(h - 0.5) > 0.45) & (np.arange(n) + HOLD < n))
d = np.where(h[sig] > 0.5, 1.0, -1.0)
fwd5 = np.array([spread[t + 1:t + 1 + HOLD].sum() for t in sig]) * d
fwd1 = spread[sig + 1] * d
years = sorted({dates[t][:4] for t in sig})
out = {"cost_round_trip_bps": 20.0, "hold": HOLD, "by_year": [], "last_date": dates[-1]}
print("year   n   5-day gross/signal (bps)   se    next day (bps)")
for y in years:
    m = np.array([dates[t][:4] == y for t in sig])
    if m.sum() < 2:
        continue
    f5, f1 = fwd5[m] * 1e4, fwd1[m] * 1e4
    rec = {"year": int(y), "n": int(m.sum()), "bps": round(float(f5.mean()), 1), "se": round(float(f5.std(ddof=1) / math.sqrt(m.sum())), 1),
           "next_bps": round(float(f1.mean()), 1), "next_se": round(float(f1.std(ddof=1) / math.sqrt(m.sum())), 1), "partial": y == dates[-1][:4]}
    out["by_year"].append(rec)
    print(f"{y}  {rec['n']:3d}   {rec['bps']:7.1f}              {rec['se']:5.1f}   {rec['next_bps']:6.1f}")
for name, lo, hi in (("2010-2019", "2010", "2020"), ("2020-2026", "2020", "2100"), ("2021-2026", "2021", "2100")):
    m = np.array([lo <= dates[t][:4] < hi for t in sig])
    f5 = fwd5[m] * 1e4
    out[name.replace("-", "_")] = {"n": int(m.sum()), "bps": round(float(f5.mean()), 1), "se": round(float(f5.std(ddof=1) / math.sqrt(m.sum())), 1), "next_bps": round(float((fwd1[m] * 1e4).mean()), 1)}
    print(name, out[name.replace("-", "_")])
json.dump(out, open("research/results/edge.json", "w"), indent=1)
