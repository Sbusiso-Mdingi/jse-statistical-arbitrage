import sys, pickle, math, itertools; sys.path.insert(0, "/tmp/jse-review/overfit")
import numpy as np
from scipy import stats
S = pickle.load(open("/tmp/jse-review/overfit/universe.pkl", "rb"))
U, G, dates, dev = S["U"], S["G"], S["dates"], S["dev_all"]
idx = np.flatnonzero(dev); T = len(idx); rng = np.random.default_rng(7)
CH = "rolling|L126|eg<-2.8"
def tt(v): return v.mean() / (v.std(ddof=1) / math.sqrt(len(v))) if len(v) > 2 else np.nan
def mat(D): 
    keys = list(D); return keys, np.column_stack([D[k]["daily"][idx] for k in keys]) * 1e4
for label, D, chosen in (("explore_gap 50", U, CH), ("EG grid 400", G, (126, -2.8, 1.5))):
    keys, M = mat(D)
    mu, sd = M.mean(0), M.std(0, ddof=1)
    tobs = math.sqrt(T) * mu / sd
    ci = keys.index(chosen)
    pt = np.array([tt(D[k]["v"]) for k in keys])
    print(f"\n== {label}: K={len(keys)}; chosen daily t {tobs[ci]:.2f} (rank {int((tobs > tobs[ci]).sum()) + 1}), max daily t {np.nanmax(tobs):.2f}; chosen per-trade t {pt[ci]:.2f}, max per-trade t {np.nanmax(pt):.2f} at {keys[int(np.nanargmax(pt))]}")
    # effective number of trials
    C = np.corrcoef(M.T); C = np.nan_to_num(C); ev = np.clip(np.linalg.eigvalsh(C), 0, None)
    neff = ev.sum() ** 2 / (ev ** 2).sum()
    print(f"  effective independent trials (participation ratio) {neff:.1f}; mean pairwise corr {(C.sum() - len(C)) / (len(C) * (len(C) - 1)):.2f}")
    p1 = stats.norm.sf(pt[ci])
    print(f"  per-trade one-sided p {p1:.5f}; Bonferroni K: {min(1, p1 * len(keys)):.4f}; Bonferroni Neff: {min(1, p1 * neff):.4f}; Bonferroni bar t {stats.norm.isf(0.05 / len(keys)):.2f}")
    for blk in (20, 60, 120):
        B = 2000; mx = np.empty(B); mx_spa = np.empty(B)
        keep = tobs > -math.sqrt(2 * math.log(math.log(T)))
        for bb in range(B):
            # stationary bootstrap indices
            ii = np.empty(T, int); t = 0
            while t < T:
                s = rng.integers(0, T); l = rng.geometric(1 / blk)
                seg = (s + np.arange(l)) % T; take = min(l, T - t); ii[t:t + take] = seg[:take]; t += take
            m = M[ii].mean(0)
            mx[bb] = np.max(math.sqrt(T) * (m - mu) / sd)
            mx_spa[bb] = np.max(math.sqrt(T) * (m - mu * keep) / sd)  # SPA-consistent recentring
        print(f"  stationary bootstrap block {blk}: RC p(max t* >= chosen daily t {tobs[ci]:.2f}) = {(mx >= tobs[ci]).mean():.3f}; SPA_c p = {(mx_spa >= tobs[ci]).mean():.3f}; 95th pct of max t* {np.percentile(mx, 95):.2f}")
    # Deflated Sharpe on per-trade SR
    sr = np.array([D[k]["v"].mean() / D[k]["v"].std(ddof=1) for k in keys if len(D[k]["v"]) > 5])
    v = D[chosen]["v"]; SR = v.mean() / v.std(ddof=1); n_ = len(v)
    g3, g4 = stats.skew(v), stats.kurtosis(v, fisher=False)
    for Nt in (len(keys), neff):
        emc = 0.5772156649
        sr0 = math.sqrt(sr.var(ddof=1)) * ((1 - emc) * stats.norm.ppf(1 - 1 / Nt) + emc * stats.norm.ppf(1 - 1 / (Nt * math.e)))
        z = (SR - sr0) * math.sqrt(n_ - 1) / math.sqrt(1 - g3 * SR + (g4 - 1) / 4 * SR ** 2)
        print(f"  DSR N={Nt:.0f}: per-trade SR {SR:.3f}, SR0 (expected max under null) {sr0:.3f} = {sr0 * v.std(ddof=1):.1f} bps, DSR prob {stats.norm.cdf(z):.3f}")
    # CSCV / PBO with 10 time blocks, selection by per-trade t in IS
    Sb = 10; edges = np.array_split(np.arange(len(dates)), Sb); bnd = [e[0] for e in edges] + [len(dates)]
    # restrict to dev period
    blocks_of = lambda o: np.searchsorted(bnd, o, side="right") - 1
    tb = {k: blocks_of(D[k]["open"]) for k in keys}
    oos_sel, oos_rank, is_sel = [], [], []
    for comb in itertools.combinations(range(Sb), Sb // 2):
        ism = np.isin(np.arange(Sb), comb)
        ist = []; oo = []
        for k in keys:
            vv, bk = D[k]["v"], tb[k]
            a, b_ = vv[ism[bk]], vv[~ism[bk]]
            ist.append(tt(a) if len(a) >= 10 else -np.inf); oo.append(b_.mean() if len(b_) >= 3 else np.nan)
        ist, oo = np.array(ist), np.array(oo)
        j = int(np.argmax(ist)); is_sel.append(D[keys[j]]["v"][ism[tb[keys[j]]]].mean())
        oos_sel.append(oo[j]); ok = ~np.isnan(oo); oos_rank.append((oo[ok] < oo[j]).mean())
    oos_sel, oos_rank = np.array(oos_sel), np.array(oos_rank)
    print(f"  CSCV (10 blocks, 252 splits, pick max IS per-trade t): IS mean of pick {np.nanmean(is_sel):.1f} bps; OOS mean of pick {np.nanmean(oos_sel):.1f} bps (median {np.nanmedian(oos_sel):.1f}, 10th pct {np.nanpercentile(oos_sel, 10):.1f}); P(OOS<=0) {np.nanmean(oos_sel <= 0):.2f}; PBO {np.mean(oos_rank < 0.5):.2f}")
# halves on the grid
print()
for lo_, hi_ in (((2006, 2015), (2016, 2026)), ((2016, 2026), (2006, 2015))):
    best, bk = -9, None
    for k, u in G.items():
        yrs = np.array([dates[o].year for o in u["open"]])
        a = u["v"][(yrs >= lo_[0]) & (yrs <= lo_[1])]
        if len(a) >= 15 and tt(a) > best: best, bk = tt(a), k
    u = G[bk]; yrs = np.array([dates[o].year for o in u["open"]]); b_ = u["v"][(yrs >= hi_[0]) & (yrs <= hi_[1])]
    ch = G[(126, -2.8, 1.5)]; yc = np.array([dates[o].year for o in ch["open"]]); cb = ch["v"][(yc >= hi_[0]) & (yc <= hi_[1])]
    print(f"select on {lo_}: best {bk} IS t {best:.2f}; OOS {hi_}: {len(b_)} trades {b_.mean():.1f} bps t {tt(b_):.2f}  | frozen rule in same OOS: {len(cb)} trades {cb.mean():.1f} bps")
# distribution of the grid: share of specs with positive mean, by window
for L in (63, 84, 105, 126, 147, 168, 189, 252):
    m = [G[k]["v"].mean() for k in G if k[0] == L]; print("L", L, "median spec bps", round(float(np.median(m)), 1), "share>0", round(float(np.mean(np.array(m) > 0)), 2))
