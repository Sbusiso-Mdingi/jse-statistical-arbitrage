"""Gross five-day return per signal on the SBK/NED pair under each copula's h, by period. Reported, not tested."""
import csv, math, sys
import numpy as np
sys.path.insert(0, "research/models")
from pairdata import load_pair
d = load_pair(); idx = {x.isoformat(): i for i, x in enumerate(d["date"])}
spread = 0.5 * (np.expm1(d["r_sbk"]) - np.expm1(d["r_ned"]))  # long SBK / short NED, half of capital a side
rows = list(csv.DictReader(open("research/results/copulas_py.csv")))
PER = {"design": ("2010-01-01", "2020-01-01"), "validation": ("2020-01-01", "2026-04-01"), "post-freeze": ("2026-04-01", "2100-01-01")}
out = {}
for model in ("static_t", "gas_t", "ms_t", "rolling_t_252"):
    hs = {r["date"]: float(r["h"]) for r in rows if r["model"] == model}
    out[model] = {}
    for p, (lo, hi) in PER.items():
        f5 = []
        for dd, h in hs.items():
            if not (lo <= dd < hi) or abs(h - 0.5) <= 0.45: continue
            t = idx[dd]
            if t + 5 >= len(spread): continue
            dsign = 1.0 if h > 0.5 else -1.0  # NED high relative to SBK: long SBK / short NED
            f5.append(dsign * spread[t + 1:t + 6].sum() * 1e4)
        f5 = np.array(f5)
        out[model][p] = {"n": len(f5), "bps": round(float(f5.mean()), 1) if len(f5) else None, "se": round(float(f5.std(ddof=1) / math.sqrt(len(f5))), 1) if len(f5) > 1 else None}
        print(f"{model:14s} {p:12s} signals {len(f5):4d}  gross/signal {out[model][p]['bps']} bps  se {out[model][p]['se']}")
import json; json.dump(out, open("research/results/h8_edge.json", "w"), indent=1)
