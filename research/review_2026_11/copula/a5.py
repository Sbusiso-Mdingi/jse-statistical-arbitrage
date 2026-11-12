import csv, math, numpy as np
B = np.load("/tmp/jse-review/copula/base.npz"); dates = list(B["dates"]); N = len(dates)
h = np.load("/tmp/jse-review/copula/h.npy")
raw = {nm: {r["date"]: (float(r["close"]), float(r["adjusted"])) for r in csv.DictReader(open(f"data/raw/{nm}.csv")) if r["close"] not in ("NA", "") and r["adjusted"] not in ("NA","")} for nm in ("sbk", "ned")}
ev = [(r["bank"], r["date"], float(r["amount"])) for r in csv.DictReader(open("research/results/h15_events.csv")) if r["kind"] == "ex_dividend"]
idx = {x: i for i, x in enumerate(dates)}
print("bank exdate  div  raw_ret  adj_ret  raw-adj  adj ret day+1  h(exdate) h(+1)")
rows = []
for bk, x, amt in ev:
    if x not in idx or x > "2026-03-31": continue
    i = idx[x]; p = dates[i - 1]; nx = dates[i + 1] if i + 1 < N else None
    R = raw[bk]
    if p not in R or x not in R: continue
    rr = R[x][0] / R[p][0] - 1; ra = R[x][1] / R[p][1] - 1
    rnext = R[nx][1] / R[x][1] - 1 if nx in R else float('nan')
    rows.append((bk, x, amt / R[p][0], rr, ra))
    if x >= "2010": print(f"{bk} {x} {amt/R[p][0]*100:5.2f}% {rr*100:6.2f}% {ra*100:6.2f}% {(rr-ra)*100:6.2f}% {rnext*100:6.2f}%  {h[i]:.3f} {h[i+1] if i+1<N else float('nan'):.3f}")
r = np.array([[a[2], a[3], a[4]] for a in rows])
print("mean div yield %.2f%%, mean raw ret %.2f%%, mean adj ret %.2f%%" % tuple(r.mean(0) * 100))
