"""H7: intraday reversal of the SBK minus NED spread on 60-minute bars (research/PROTOCOL.md).

Signal at the 12:00 SAST close from the 10:00 to 12:00 divergence, position held to the 17:00 close.
Threshold is a trailing 250-day percentile chosen on design data from {90, 95, 97.5}; the chosen rule is
validated once. Writes research/results/h7.json, h7_log.json and h7_daily.csv.
"""
import csv, json, math, datetime as dt, os
from collections import defaultdict
import numpy as np

COST = 10 / 1e4
TRAIL = 250
PERIODS = {"design": ("2010-01-01", "2020-01-01"), "validation": ("2020-01-01", "2026-04-01"), "post-freeze": ("2026-04-01", "2100-01-01")}
LOG = "research/results/h7_log.json"
H0, H1_, HC = 7, 9, 14  # UTC bar open hours whose closes are 10:00, 12:00 and 17:00 SAST


def load(f):
    out = defaultdict(dict)
    for r in csv.DictReader(open(f)):
        t = dt.datetime.utcfromtimestamp(int(r["time"]))
        out[t.date()][t.hour] = float(r["close"])
    return out


S, N = load("data/raw/sbk_60m.csv"), load("data/raw/ned_60m.csv")
days = sorted(d for d in S if d in N and len(S[d]) == 8 and len(N[d]) == 8)
D = np.array([(math.log(S[d][H1_] / S[d][H0]) - math.log(N[d][H1_] / N[d][H0])) for d in days])
# Return of long SBK / short NED, half of capital each leg, from the 12:00 close to the 17:00 close.
rest = np.array([0.5 * ((S[d][HC] / S[d][H1_] - 1) - (N[d][HC] / N[d][H1_] - 1)) for d in days])
dates = [d.isoformat() for d in days]
n = len(days)
print(f"{n} full days from {dates[0]} to {dates[-1]}")


def positions(q):
    pos = np.zeros(n)
    absD = np.abs(D)
    for t in range(TRAIL, n):
        thr = np.percentile(absD[t - TRAIL:t], q)
        if absD[t] > thr:
            pos[t] = -1.0 if D[t] > 0 else 1.0
    return pos


def net_returns(pos, cost=COST):
    return pos * rest - np.abs(pos) * 2 * cost  # open and close the same day: two units of notional traded


def stats(net, pos, a, b):
    m = np.array([a <= d < b for d in dates])
    x, p, g = net[m], pos[m], (pos * rest)[m]
    if len(x) < 2:
        return None
    eq = np.cumprod(1 + x)
    sd = x.std(ddof=1)
    down = math.sqrt(np.mean(np.minimum(x, 0) ** 2))
    return dict(start=dates[int(np.argmax(m))], end=dates[n - 1 - int(np.argmax(m[::-1]))],
                sharpe=round(float(x.mean() / sd * math.sqrt(252)), 2) if sd > 0 else 0.0,
                sortino=round(float(x.mean() / down * math.sqrt(252)), 2) if down > 0 else 0.0,
                cagr=round(float(eq[-1] ** (252 / len(x)) - 1), 4), mdd=round(float((eq / np.maximum.accumulate(eq) - 1).min()), 4),
                in_market=round(float((p != 0).mean()), 3), entries=int((p != 0).sum()),
                hit_rate=round(float((x[p != 0] > 0).mean()), 3) if (p != 0).any() else None,
                mean_trade_bps=round(float(g[p != 0].mean() * 1e4), 1) if (p != 0).any() else None)


def evaluate(q, periods, note):
    pos = positions(q)
    res = {p: {"after_costs": stats(net_returns(pos), pos, *PERIODS[p]), "before_costs": stats(net_returns(pos, 0.0), pos, *PERIODS[p]),
               "at_5bps": stats(net_returns(pos, 5 / 1e4), pos, *PERIODS[p])} for p in periods}
    log = json.load(open(LOG)) if os.path.exists(LOG) else []
    log.append({"n": len(log) + 1, "when": dt.date.today().isoformat(), "q": q, "periods": periods, "note": note,
                "result": {p: {"sharpe": r["after_costs"]["sharpe"], "before": r["before_costs"]["sharpe"], "entries": r["after_costs"]["entries"]} for p, r in res.items()}})
    json.dump(log, open(LOG, "w"), indent=1)
    return res, pos


out = {"test": "H7", "trail_days": TRAIL, "grid": {}}
for q in (90, 95, 97.5):
    r, _ = evaluate(q, ["design"], "design grid")
    a, b = r["design"]["after_costs"], r["design"]["before_costs"]
    out["grid"][str(q)] = r["design"]
    print(f"q{q}: design SR {a['sharpe']:5.2f} (before costs {b['sharpe']:5.2f}, at 5 bps {r['design']['at_5bps']['sharpe']:5.2f})  trades {a['entries']}  hit {a['hit_rate']}  mean gross/trade {a['mean_trade_bps']} bps")
best = max(out["grid"], key=lambda k: out["grid"][k]["after_costs"]["sharpe"])
q = float(best)
print("chosen on design: q =", q)
res, pos = evaluate(q, ["design", "validation", "post-freeze"], "the one validation run of the chosen rule")
out.update({"chosen_q": q, **res})
out["passed"] = bool(res["validation"]["after_costs"]["sharpe"] > 0)
for p in ("design", "validation", "post-freeze"):
    a, b = res[p]["after_costs"], res[p]["before_costs"]
    print(f"{p:12s} SR {a['sharpe']:6.2f} (before {b['sharpe']:5.2f}, 5 bps {res[p]['at_5bps']['sharpe']:5.2f})  Sortino {a['sortino']:5.2f}  CAGR {a['cagr']*100:5.1f}%  MDD {a['mdd']*100:6.1f}%  trades {a['entries']}  hit {a['hit_rate']}  gross/trade {a['mean_trade_bps']} bps")
# Reported, not tested: the other grid points in validation.
out["other_grid_validation"] = {}
for qq in (90, 95, 97.5):
    if qq != q:
        rr, _ = evaluate(qq, ["validation"], "reported, not tested: other grid point in validation")
        out["other_grid_validation"][str(qq)] = rr["validation"]
        print(f"  (reported) q{qq} validation SR {rr['validation']['after_costs']['sharpe']:.2f}, before costs {rr['validation']['before_costs']['sharpe']:.2f}")
# By year, and paired against H1 on common validation days.
net = net_returns(pos)
yrs = sorted({d[:4] for d in dates})
out["by_year"] = {y: stats(net, pos, f"{y}-01-01", f"{int(y)+1}-01-01") for y in yrs if int(y) >= 2010}
print("by year (SR after costs):", {y: v["sharpe"] for y, v in out["by_year"].items() if v})
h1 = {r["date"]: float(r["net_h1"]) for r in csv.DictReader(open("research/results/h5_daily.csv"))}
a, b = PERIODS["validation"]
common = [(net[i], h1[d]) for i, d in enumerate(dates) if a <= d < b and d in h1]
diff = np.array([x - y for x, y in common])
out["vs_h1_validation"] = {"bps_per_year": round(float(diff.mean() * 252 * 1e4), 1), "t_stat": round(float(diff.mean() / (diff.std(ddof=1) / math.sqrt(len(diff)))), 2), "days": len(common)}
print("vs H1 on common validation days:", out["vs_h1_validation"])
print("PASSED" if out["passed"] else "FAILED")
json.dump(out, open("research/results/h7.json", "w"), indent=1)
with open("research/results/h7_daily.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["date", "divergence", "position", "gross", "net"])
    for i, d in enumerate(dates):
        w.writerow([d, f"{D[i]:.6f}", int(pos[i]), f"{pos[i]*rest[i]:.8f}", f"{net[i]:.8f}"])
