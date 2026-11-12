import sys, json; sys.path.insert(0, "/tmp/jse-review/overfit")
from common import *
from scipy import stats
d, dates, x, y, rs, rn, dev = setup(); n = len(dates)
b, z, eg = rolling(x, y, 126)
gate = eg < -2.8
trs = run_rule(gate, b, z, dev)
_, rows = score(trs, dates, rs, rn)
_, rows_g = score(trs, dates, rs, rn, None)
v = np.array([r["net"] for r in rows]) * 1e4
g = np.array([r["gross"] for r in rows_g]) * 1e4
hold = np.array([r["close"] - r["open"] for r in rows])
print("N", len(v), "mean", v.mean().round(1), "sd", v.std(ddof=1).round(1), "median", np.median(v).round(1), "win", (v > 0).mean().round(3))
print("gross mean", g.mean().round(1), "cost mean", (g - v).mean().round(1), "skew", stats.skew(v).round(2), "exkurt", stats.kurtosis(v).round(2))
srt = np.sort(v)
print("top3 sum share of total", (srt[-3:].sum() / v.sum()).round(3), "top5", (srt[-5:].sum() / v.sum()).round(3), "mean w/o top3", srt[:-3].mean().round(1), "w/o top5", srt[:-5].mean().round(1))
print("worst5", srt[:5].round(0), "best5", srt[-5:].round(0), "mean w/o worst5", srt[5:].mean().round(1))
# exit reasons
reasons = []
for r in rows:
    k = r["close"] - r["open"]; zc = z[r["close"]]
    reasons.append("stop" if abs(zc) > 4 else ("maxhold" if k >= 60 else "revert"))
reasons = np.array(reasons)
for k in ("revert", "stop", "maxhold"):
    m = reasons == k; print("exit", k, m.sum(), v[m].mean().round(1) if m.any() else None)
print("mean hold", hold.mean().round(1), "median", np.median(hold))
# by year
yrs = np.array([r["d_open"].year for r in rows])
by = {int(yv): (int((yrs == yv).sum()), round(float(v[yrs == yv].sum()), 0), round(float(v[yrs == yv].mean()), 1)) for yv in np.unique(yrs)}
print("by year (n, sum, mean):", by)
pos_years = sum(1 for k, t in by.items() if t[1] > 0); print("years positive", pos_years, "of", len(by))
# leave-one-year-out
loyo = {int(yv): round(float(v[yrs != yv].mean()), 1) for yv in np.unique(yrs)}
print("LOYO min", min(loyo.values()), "max", max(loyo.values()))
# episodes: contiguous gate-open runs, merging gaps <= G sessions
def episodes(G):
    ep = np.zeros(n, int); cur = 0; last_open = -10**9
    for t in range(n):
        if gate[t] and dev[t]:
            if t - last_open > G: cur += 1
            last_open = t
        ep[t] = cur
    return ep
for G in (0, 21, 63, 126):
    ep = episodes(G); e = np.array([ep[r["open"]] for r in rows])
    u, cnt = np.unique(e, return_counts=True)
    sums = np.array([v[e == k].sum() for k in u])
    print(f"G={G}: episodes with trades {len(u)}, trades/episode max {cnt.max()} mean {cnt.mean():.2f}, top-5 episodes share of total P&L {np.sort(sums)[-5:].sum()/v.sum():.2f}, positive episodes {(sums>0).mean():.2f}")
# serial dependence of consecutive trades
print("lag-1 autocorr of trade nets", np.corrcoef(v[:-1], v[1:])[0, 1].round(3), "lag2", np.corrcoef(v[:-2], v[2:])[0, 1].round(3))
gaps = np.array([rows[i + 1]["open"] - rows[i]["close"] for i in range(len(rows) - 1)])
print("gap between trades: median", np.median(gaps), "share <= 5 sessions", (gaps <= 5).mean().round(2), "share 0 (same-day reopen)", (gaps == 0).mean().round(2))
# same-side consecutive
sides = np.array([r["side"] for r in rows]); print("same side as previous", (sides[1:] == sides[:-1]).mean().round(2))
# within-trade P&L by held day (gross, bps)
byday = collections.defaultdict(list) if False else {}
for r in rows:
    for k in range(1, r["close"] - r["open"] + 1):
        t = r["open"] + k
        byday.setdefault(min(k, 11), []).append((r["w_sbk"] * rs[t] + r["w_ned"] * rn[t]) * 1e4)
print("gross bps by held day:", {k: (round(float(np.mean(a)), 1), round(float(np.std(a)/np.sqrt(len(a))), 1)) for k, a in sorted(byday.items())})
post = []
for r in rows:
    t = r["close"] + 1
    if t < n: post.append((r["w_sbk"] * rs[t] + r["w_ned"] * rn[t]) * 1e4)
print("day after exit, same weights, gross", round(float(np.mean(post)), 1), "se", round(float(np.std(post)/np.sqrt(len(post))), 1))
# daily-return Sharpe
daily, _ = sw.daily_returns(trs, dates, rs, rn, "futures")
m = dev; dr = daily[m]
print("daily ann Sharpe", round(dr.mean() / dr.std() * np.sqrt(252), 2), "share days in market", round(float(np.mean([any(r['open'] < t <= r['close'] for r in rows) for t in range(0, n, 5)])), 2))
json.dump({"v": v.tolist(), "open": [r["open"] for r in rows], "close": [r["close"] for r in rows], "year": yrs.tolist(), "ep21": [int(episodes(21)[r["open"]]) for r in rows], "ep63": [int(episodes(63)[r["open"]]) for r in rows]}, open("/tmp/jse-review/overfit/trades_h16.json", "w"))
