import sys, json, os; sys.path.insert(0, "/tmp/jse-review/overfit")
from common import *
from multiprocessing import Pool
d, dates, x, y, rs, rn, dev = setup(); n = len(dates)
r2 = np.column_stack([d["r_sbk"], d["r_ned"]])
CUTS = (-2.0, -2.4, -2.6, -2.8, -3.0, -3.34, -3.6)
def per_trade(trs, rs_, rn_):
    _, rows = sw.daily_returns(trs, dates, rs_, rn_, "futures")
    v = np.array([r["net"] for r in rows if r["complete"] and dates[r["open"]] >= START]) * 1e4
    return (len(v), float(v.mean()) if len(v) else np.nan, tstat(v) if len(v) > 2 else np.nan)
def family(x_, y_, rs_, rn_):
    """explore_gap's plain EG family: L126 x 7 cutoffs, L63/L252 x 3, entries at -2.8. Returns dict."""
    W = {L: rolling(x_, y_, L) for L in (63, 126, 252)}
    out = {}
    for L in (63, 126, 252):
        b, z, eg = W[L]
        for c in CUTS:
            if L != 126 and c not in (-2.4, -2.8, -3.34): continue
            out[f"L{L}|{c}"] = per_trade(run_rule(eg < c, b, z, dev), rs_, rn_)
    b, z, eg = W[126]
    for e in (1.0, 1.25, 1.75, 2.0):
        out[f"L126|-2.8|e{e}"] = per_trade(run_rule(eg < -2.8, b, z, dev, entry=e), rs_, rn_)
    out["always"] = per_trade(run_rule(np.ones(n, bool), b, z, dev), rs_, rn_)
    return out
def sim(args):
    mode, seed = args
    rng = np.random.default_rng(seed)
    if mode == "iid":
        ii = rng.integers(0, n, n)
    else:
        blk = int(mode.split("_")[1]); ii = np.empty(n, int); t = 0
        while t < n:
            s = rng.integers(0, n); l = rng.geometric(1 / blk); take = min(l, n - t)
            ii[t:t + take] = (s + np.arange(take)) % n; t += take
    lr = r2[ii]
    return family(np.cumsum(lr[:, 0]), np.cumsum(lr[:, 1]), np.expm1(lr[:, 0]), np.expm1(lr[:, 1]))
b, z, eg = rolling(x, y, 126)
def shift(k):
    egk = np.roll(eg, k)
    return {c: per_trade(run_rule(egk < c, b, z, dev), rs, rn) for c in CUTS}
if __name__ == "__main__":
    mode = sys.argv[1]; R = int(sys.argv[2])
    with Pool(8) as p:
        if mode == "shift":
            ks = np.linspace(126, n - 126, R).astype(int)
            res = p.map(shift, ks)
            res = [{str(c): v for c, v in r.items()} for r in res]
        else:
            res = p.map(sim, [(mode, 1000 + i) for i in range(R)])
    json.dump(res, open(f"/tmp/jse-review/overfit/placebo_{mode}.json", "w"))
    print(mode, len(res))
