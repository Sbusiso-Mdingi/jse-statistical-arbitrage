import sys, json; sys.path.insert(0, "/tmp/jse-review/overfit")
from common import *
d, dates, x, y, rs, rn, dev = setup(); n = len(dates)
Ls = (63, 84, 105, 126, 147, 168, 189, 252)
W = {L: rolling(x, y, L) for L in Ls}
def ev(L=126, c=-2.8, **kw):
    b, z, eg = W[L]
    trs = run_rule(eg < c, b, z, dev, **kw)
    _, rows = score(trs, dates, rs, rn)
    v = np.array([r["net"] for r in rows]) * 1e4
    return len(v), round(float(v.mean()), 1), round(tstat(v), 2)
out = {}
cuts = [round(-2.0 - 0.1 * i, 2) for i in range(19)] + [-3.34]
print("cutoff x window (trades, bps, t)")
for L in Ls:
    row = {c: ev(L, c) for c in cuts}
    out[f"L{L}"] = {str(c): v for c, v in row.items()}
    print(L, " ".join(f"{c}:{v[1]}/{v[2]}" for c, v in row.items()))
print("cutoff x entry at L126")
for e in (1.0, 1.25, 1.5, 1.75, 2.0):
    row = {c: ev(126, c, entry=e) for c in (-2.4, -2.6, -2.8, -3.0, -3.34)}
    out[f"entry{e}"] = {str(c): v for c, v in row.items()}
    print(e, row)
for name, grid, key in (("exit", (0.0, 0.25, 0.5), "exit_"), ("stop", (3.0, 3.5, 4.0, 5.0, 99.0), "stop"), ("max_hold", (20, 40, 60, 90, 120, 250), "max_hold")):
    for c in (-2.4, -2.8, -3.34):
        row = {g: ev(126, c, **{key: g}) for g in grid}
        out[f"{name}@{c}"] = {str(g): v for g, v in row.items()}
        print(name, c, row)
json.dump(out, open("/tmp/jse-review/overfit/fragility.json", "w"), indent=1)

# Execution lag: fill one close late on both legs (weights from the signal close)
b, z, eg = W[126]
for c in (-2.4, -2.8, -3.34):
    trs = run_rule(eg < c, b, z, dev)
    for lag in (0, 1, 2):
        tl = []
        for tr in trs:
            if tr["close"] is None or tr["close"] + lag >= n: continue
            tl.append(dict(tr, open=tr["open"] + lag, close=tr["close"] + lag))
        _, rows = score(tl, dates, rs, rn)
        v = np.array([r["net"] for r in rows]) * 1e4
        print("lag", lag, "cut", c, len(v), round(v.mean(), 1), round(tstat(v), 2))
