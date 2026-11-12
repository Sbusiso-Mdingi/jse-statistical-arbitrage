import sys, csv, math, datetime as dt, numpy as np
sys.path.insert(0, "service")
from app import switch as SW
B = np.load("/tmp/jse-review/copula/base.npz"); dates = list(B["dates"]); N = len(dates); D = [dt.date.fromisoformat(x) for x in dates]
h = np.load("/tmp/jse-review/copula/h.npy"); ok = ~np.isnan(h); yr = np.array([d.year for d in D])
raw = {nm: {r["date"]: float(r["close"]) for r in csv.DictReader(open(f"data/raw/{nm}.csv")) if r["close"] not in ("NA", "")} for nm in ("sbk", "ned")}
idx = {x: i for i, x in enumerate(dates)}
dy = {"sbk": np.zeros(N), "ned": np.zeros(N)}
for r in csv.DictReader(open("research/results/h15_events.csv")):
    if r["kind"] == "ex_dividend" and r["date"] in idx:
        i = idx[r["date"]]; dy[r["bank"]][i] = float(r["amount"]) / raw[r["bank"]][dates[i - 1]]
rs, rn = B["rs"], B["rn"]
sp = 0.5 * (rs - rn); spT = 0.5 * ((rs + dy["sbk"]) - (rn + dy["ned"]))   # total-return relative
cs, csT = np.concatenate([[0.0], np.cumsum(sp)]), np.concatenate([[0.0], np.cumsum(spT)])
exany = (dy["sbk"] > 0) | (dy["ned"] > 0)
sig = np.flatnonzero(ok & (np.abs(h - .5) > .45) & (np.arange(N) + 7 < N)); s = np.sign(h[sig] - .5)
on_ex = exany[sig]
# share of ex-dates that fire (expected 10%)
exd = np.flatnonzero(exany & ok); one = np.flatnonzero(ok & ((dy["sbk"] > 0) ^ (dy["ned"] > 0)))
print(f"ex-dividend sessions 2010-Mar26 (either bank): {len(exd)}; fire on {np.mean(np.abs(h[exd]-.5)>.45)*100:.0f}% (only one bank ex: {len(one)}, fire {np.mean(np.abs(h[one]-.5)>.45)*100:.0f}%) vs 10% expected")
for nm, lo, hi in [("2010-19", 2010, 2020), ("2020", 2020, 2021), ("2021-26Q1", 2021, 2027), ("2010-26Q1", 2010, 2027)]:
    m = (yr[sig] >= lo) & (yr[sig] < hi)
    g = s * (cs[sig + 6] - cs[sig + 1]) * 1e4; gT = s * (csT[sig + 6] - csT[sig + 1]) * 1e4
    mm = m & ~on_ex
    print(f"{nm:10s} signals {m.sum():3d} on ex-date {np.sum(m&on_ex):2d} | price-return 5d {g[m].mean():6.1f} | total-return 5d {gT[m].mean():6.1f} | total-return, ex-date signals dropped {gT[mm].mean():6.1f} ({gT[mm].std(ddof=1)/math.sqrt(mm.sum()):.1f}, n {mm.sum()}) | ex-date signals alone price {g[m&on_ex].mean() if np.any(m&on_ex) else float('nan'):6.1f} total {gT[m&on_ex].mean() if np.any(m&on_ex) else float('nan'):6.1f}")
np.save("/tmp/jse-review/copula/dy.npy", np.vstack([dy["sbk"], dy["ned"]]))
