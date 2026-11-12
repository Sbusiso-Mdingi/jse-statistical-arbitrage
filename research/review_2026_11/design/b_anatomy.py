import sys; sys.path.insert(0, "/tmp/jse-review/design")
from core import *
import pickle, collections
w = pickle.load(open("/tmp/jse-review/design/w126.pkl", "rb"))
gate = w["eg"] < -2.8
trs = sim(w["z"], w["b"], gate)
r, done, tot = score(trs)
gross_daily = {}
by = collections.defaultdict(list)
rows = []
for tr, rr in zip(trs, score(trs)[1] + [None] * 5):
    pass
_, allrows = sw.daily_returns(trs, dates, rs, rn, "futures")
for tr, rr in zip(trs, allrows):
    if not rr["complete"]:
        continue
    o, c = tr["open"], tr["close"]
    g = tr["w_sbk"] * rs[o + 1:c + 1] + tr["w_ned"] * rn[o + 1:c + 1]
    path = np.cumsum(g) * 1e4
    gclosed = ~gate[o + 1:c + 1]
    # first session gate is shut during the trade
    first_shut = int(np.argmax(gclosed)) if gclosed.any() else None
    rows.append(dict(reason=tr["reason"], net=rr["net"] * 1e4, gross=rr["gross"] * 1e4, hold=c - o, mae=path.min(), mfe=path.max(),
                     after_shut=float(g[first_shut:].sum() * 1e4) if first_shut is not None else 0.0, shut_at_exit=bool(~gate[c]),
                     ever_shut=first_shut is not None, db=float(w["b"][c] - tr["b0"]), z0=tr["z0"], eg0=float(w["eg"][o]),
                     day1=float(g[0] * 1e4), year=dates[o].year, b0=tr["b0"],
                     # spread move in units of entry s on the frozen line vs on the rolling line
                     frozen_gap_exit=float((y[c] - w["a"][o] - w["b"][o] * x[c]) / w["s"][o])))
net = np.array([q["net"] for q in rows])
print("trades", len(rows), "mean", net.mean().round(1), "sd", net.std(ddof=1).round(1))
for k in ("target", "stop", "time"):
    v = [q for q in rows if q["reason"] == k]
    if v:
        print(f"{k:7s} n={len(v):3d} mean={np.mean([q['net'] for q in v]):7.1f} sum={np.sum([q['net'] for q in v]):8.0f} hold={np.mean([q['hold'] for q in v]):5.1f} "
              f"mae={np.mean([q['mae'] for q in v]):7.1f} mfe={np.mean([q['mfe'] for q in v]):6.1f} |db|={np.mean([abs(q['db']) for q in v]):.3f}")
ev = [q for q in rows if q["ever_shut"]]
print("trades where gate shut before exit:", len(ev), "net mean", np.mean([q["net"] for q in ev]).round(1), "pnl after shut (gross) sum", round(sum(q["after_shut"] for q in ev)),
      "mean", np.mean([q["after_shut"] for q in ev]).round(1), "of total gross", round(sum(q["gross"] for q in rows)))
nv = [q for q in rows if not q["ever_shut"]]
print("trades gate stayed open:", len(nv), "net mean", np.mean([q["net"] for q in nv]).round(1))
print("losers", sum(net < 0), "loss sum", net[net < 0].sum().round(0), "worst5", np.sort(net)[:5].round(0))
print("losers by reason", collections.Counter(q["reason"] for q in rows if q["net"] < 0))
print("MAE dist (gross bps): pctiles 10/25/50", np.percentile([q["mae"] for q in rows], [10, 25, 50]).round(0))
print("winners MAE median", np.median([q["mae"] for q in rows if q["net"] > 0]).round(0), "losers MAE median", np.median([q["mae"] for q in rows if q["net"] <= 0]).round(0))
print("day1 gross mean", np.mean([q["day1"] for q in rows]).round(1), "se", (np.std([q["day1"] for q in rows]) / math.sqrt(len(rows))).round(1))
print("hold pctiles", np.percentile([q["hold"] for q in rows], [10, 25, 50, 75, 90]))
print("frozen-line gap at target exits: median", np.median([q["frozen_gap_exit"] * np.sign(q["z0"]) for q in rows if q["reason"] == "target"]).round(2),
      "(>0 means price had NOT crossed the entry line; rolling line moved to price)")
print("|db| vs net corr", np.corrcoef([abs(q["db"]) for q in rows], net)[0, 1].round(3))
print("|z0| vs net corr", np.corrcoef([abs(q["z0"]) for q in rows], net)[0, 1].round(3), "eg0 vs net corr", np.corrcoef([q["eg0"] for q in rows], net)[0, 1].round(3))
for lo, hi in ((-99, -3.6), (-3.6, -3.34), (-3.34, -3.0), (-3.0, -2.8)):
    v = [q["net"] for q in rows if lo <= q["eg0"] < hi]
    print(f"eg at open [{lo},{hi}) n={len(v)} mean={np.mean(v):.1f}")
for lo, hi in ((1.5, 1.75), (1.75, 2.0), (2.0, 2.5), (2.5, 9)):
    v = [q["net"] for q in rows if lo <= abs(q["z0"]) < hi]
    print(f"|z0| [{lo},{hi}) n={len(v)} mean={np.mean(v):.1f}")
print("b0 range", np.percentile([q["b0"] for q in rows], [5, 50, 95]).round(2), "b<0.3:", [round(q["net"]) for q in rows if q["b0"] < 0.3])
# same-close re-entries after a stop
print("re-entries on stop close:", sum(1 for a, b_ in zip(trs, trs[1:]) if a["reason"] == "stop" and b_["sig"] == a["jsig"]))
# time in market
inmk = np.zeros(n, bool)
for tr in trs:
    if tr["close"] is not None: inmk[tr["open"] + 1:tr["close"] + 1] = True
print("time in market (dev sessions)", inmk[dev].mean().round(3), "gate open share", gate[dev].mean().round(3))
# execution lag
for lag in (0, 1, 2):
    line(f"lag {lag} close(s)", sim(w["z"], w["b"], gate, lag=lag))
# P&L by year
yr = collections.defaultdict(list)
for q in rows: yr[q["year"]].append(q["net"])
print({k: (len(v), round(sum(v))) for k, v in sorted(yr.items())})
pickle.dump(rows, open("/tmp/jse-review/design/rows.pkl", "wb"))
