"""Decay study (research/PROTOCOL.md): how the short-term reversal between SA banks has faded.

1. One-year rolling lag-1 autocorrelation of the daily log-return spread for every pair
   of SBK, NED, FSR, ABG, CPI and INL, sampled at month ends.
2. The SBK/NED copula signal's next-day reversal by year: on days with |h - 0.5| > 0.45,
   the next session's return on the position the rule would take (long SBK when h > 0.5).
Descriptive only. Writes data/decay.json for the dashboard.
"""
import csv, json, math, sys
from datetime import date
from itertools import combinations
import numpy as np

sys.path.insert(0, "service")
from app.data import drop_bad_prints  # noqa: E402
from app.main import _rows  # noqa: E402

BANKS = {"sbk": "Standard Bank", "ned": "Nedbank", "fsr": "FirstRand", "abg": "Absa", "cpi": "Capitec", "inl": "Investec"}
WINDOW = 252


def load(k):
    s = {}
    for r in csv.DictReader(open(f"data/raw/{k}.csv")):
        if r["adjusted"] not in ("NA", "", "None") and float(r["adjusted"]) > 0:
            s[date.fromisoformat(r["date"])] = float(r["adjusted"])
    return drop_bad_prints(s)


px = {k: load(k) for k in BANKS}
days = sorted(set.intersection(*(set(s) for s in px.values())))
days = [d for d in days if d >= date(2009, 1, 1)]
lr = {k: np.diff(np.log([px[k][d] for d in days])) for k in BANKS}
days = days[1:]
month_end = [i for i in range(WINDOW, len(days)) if i == len(days) - 1 or days[i + 1].month != days[i].month]


def acf1(x):
    x = x - x.mean()
    return float((x[1:] * x[:-1]).sum() / (x * x).sum())


pairs = []
for a, b in combinations(BANKS, 2):
    sp = lr[a] - lr[b]
    pairs.append({"a": a, "b": b, "acf": [round(acf1(sp[i - WINDOW + 1 : i + 1]), 4) for i in month_end]})
dates = [days[i].isoformat() for i in month_end]
mean = np.mean([p["acf"] for p in pairs], axis=0)

h = _rows("all")
hn, rs, rn = h["h_ns"], np.expm1(h["r_sbk"]), np.expm1(h["r_ned"])
years = np.array([d.year for d in h["date"]])
sig = np.where(np.abs(hn - 0.5) > 0.45, np.sign(hn - 0.5), 0.0)
nxt = np.concatenate([sig[:-1] * (rs[1:] - rn[1:]) / 2, [np.nan]])  # half of capital per leg
by_year = []
for y in sorted(set(years)):
    m = (years == y) & (sig != 0) & ~np.isnan(nxt)
    x = nxt[m] * 1e4
    by_year.append({"year": int(y), "n": int(m.sum()), "bps": round(float(x.mean()), 1),
                    "se": round(float(x.std(ddof=1) / math.sqrt(len(x))), 1) if len(x) > 1 else None})

out = {"banks": BANKS, "window": WINDOW, "dates": dates, "pairs": pairs,
       "mean_acf": [round(float(v), 4) for v in mean], "reversal_by_year": by_year}
json.dump(out, open("data/decay.json", "w"))
for i in range(0, len(dates), 12):
    print(dates[i], f"mean ACF {mean[i]:+.3f}", f"SBK/NED {pairs[0]['acf'][i]:+.3f}")
for r in by_year:
    print(r)
