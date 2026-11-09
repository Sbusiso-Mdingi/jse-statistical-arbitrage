"""Headline measurement under each copula's h for the basket instrument: gross five-day return per signal by year. Reported."""
import csv, json, math, sys
import numpy as np
sys.path.insert(0, "research")
from h5_weights import load, BASKET
d = load(); idx = {x.isoformat(): i for i, x in enumerate(d["date"])}
spread = 0.5 * (d["simple"]["sbk"] - np.mean([d["simple"][k] for k in BASKET], axis=0))
rows = list(csv.DictReader(open("research/results/copulas_basket.csv")))
out = {}
for model in ("static_t", "gas_t", "ms_t"):
    hs = {r["date"]: float(r["h"]) for r in rows if r["model"] == model}
    f5 = {}
    for dd, h in hs.items():
        if abs(h - 0.5) <= 0.45: continue
        t = idx[dd]
        if t + 5 >= len(spread): continue
        f5.setdefault(dd[:4], []).append((1.0 if h > 0.5 else -1.0) * spread[t + 1:t + 6].sum() * 1e4)
    by_year = []
    for y in sorted(f5):
        x = np.array(f5[y])
        by_year.append({"year": int(y), "n": len(x), "bps": round(float(x.mean()), 1), "se": round(float(x.std(ddof=1) / math.sqrt(len(x))), 1) if len(x) > 1 else None, "partial": y == d["date"][-1].isoformat()[:4]})
    per = {}
    for name, lo, hi in (("2010_2019", 2010, 2020), ("2020_2026", 2020, 2100), ("2021_2026", 2021, 2100)):
        x = np.array([v for y, vs in f5.items() if lo <= int(y) < hi for v in vs])
        per[name] = {"n": len(x), "bps": round(float(x.mean()), 1), "se": round(float(x.std(ddof=1) / math.sqrt(len(x))), 1)}
    out[model] = {"by_year": by_year, **per}
    print(model, {k: (v["n"], v["bps"], v["se"]) for k, v in per.items()})
json.dump(out, open("research/results/h9_edge.json", "w"), indent=1)
