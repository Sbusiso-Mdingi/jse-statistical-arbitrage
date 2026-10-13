"""H1 evaluation: SBK against the equal-weight basket, five-day hold (research/PROTOCOL.md).

Reads data/h1_daily.csv from research/02_basket.R. Half of capital in SBK, half split
equally across FSR, ABG, NED and CPI. Long SBK / short basket when h > 0.5.
"""
import csv, json, math
import numpy as np

COST = 10 / 1e4
Q, HOLD = 0.90, 5
BASKET = ["fsr", "abg", "ned", "cpi"]
PERIODS = {
    "design": ("2010-01-01", "2020-01-01"),
    "validation": ("2020-01-01", "2026-04-01"),
    "post-freeze": ("2026-04-01", "2100-01-01"),
}

rows = list(csv.DictReader(open("data/h1_daily.csv")))
dates = [r["date"] for r in rows]
h = np.array([float(r["h"]) for r in rows])
rs = np.array([float(r["sbk"]) for r in rows])
rb = np.array([[float(r[k]) for k in BASKET] for r in rows]).mean(axis=1)
n = len(rows)

pos = np.zeros(n)
cur, left = 0.0, 0
for t in range(n):
    if abs(h[t] - 0.5) > Q / 2:
        cur, left = (1.0 if h[t] > 0.5 else -1.0), HOLD
    elif left > 0:
        left -= 1
    if left == 0:
        cur = 0.0
    pos[t] = cur


def evaluate(start, end, cost=COST):
    # Net returns on the full record, then sliced, so positions carry across period boundaries.
    held_all = np.concatenate([[0.0], pos[:-1]]) * 0.5
    turn_all = np.abs(np.diff(np.concatenate([[0.0], pos])))
    net_all = held_all * (rs - rb) - turn_all * cost
    m = np.array([start <= d < end for d in dates])
    net, p, held = net_all[m], pos[m], held_all[m]
    eq = np.cumprod(1 + net)
    yrs = len(net) / 252
    sd = net.std(ddof=1)
    return dict(
        start=dates[int(np.argmax(m))], end=dates[n - 1 - int(np.argmax(m[::-1]))],
        sharpe=round(net.mean() / sd * math.sqrt(252), 2), cagr=round(eq[-1] ** (1 / yrs) - 1, 4),
        total=round(eq[-1] - 1, 4), mdd=round(float((eq / np.maximum.accumulate(eq) - 1).min()), 4),
        in_market=round(float((p != 0).mean()), 3),
        entries=int(((p != 0) & (np.concatenate([[0.0], pos[:-1]])[m] != p)).sum()),
    )


out = {name: {"after_costs": evaluate(s, e), "before_costs": evaluate(s, e, 0.0)} for name, (s, e) in PERIODS.items()}
# The signal should be uniform if the model is right: share of days beyond the threshold.
out["signal_share"] = {name: round(float(np.mean([abs(h[i] - 0.5) > Q / 2 for i in range(n) if s <= dates[i] < e])), 3)
                       for name, (s, e) in PERIODS.items()}
out["copula_families"] = sorted({r["copula"] for r in rows})
for name, (s, e) in PERIODS.items():
    for k, r in out[name].items():
        print(f"{name:12s} {k:13s} SR {r['sharpe']:5.2f}  CAGR {r['cagr']*100:5.1f}%  MDD {r['mdd']*100:6.1f}%  entries {r['entries']:3d}  {r['start']} to {r['end']}")
print("signal share", out["signal_share"], "families", out["copula_families"])
json.dump(out, open("research/results/h1.json", "w"), indent=1)
