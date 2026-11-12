import json, sys, numpy as np, os
P = "/tmp/jse-review/overfit/"
OBS_M, OBS_T = 91.1, 3.58
sh = json.load(open(P + "placebo_shift.json"))
# exclude shifts within +-252 of zero (near-real gate)
n = len(sh); ks = np.linspace(126, 5414 - 126, n).astype(int)
far = (ks > 252) & (ks < 5414 - 252)
m28 = np.array([r["-2.8"][1] for r in sh])[far]; t28 = np.array([r["-2.8"][2] for r in sh])[far]
best_t = np.array([max(v[2] for v in r.values() if v[2] == v[2]) for r in sh])[far]
best_m = np.array([max(r.values(), key=lambda v: v[2] if v[2] == v[2] else -9)[1] for r in sh])[far]
print(f"SHIFT ({far.sum()} shifts): -2.8 mean {np.nanmean(m28):.1f} sd {np.nanstd(m28):.1f}, 95th {np.nanpercentile(m28, 95):.1f}, 99th {np.nanpercentile(m28, 99):.1f}; P(mean>=91) {np.nanmean(m28 >= OBS_M):.3f}; P(t>=3.58) {np.nanmean(t28 >= OBS_T):.3f}")
print(f"   best-of-7 cutoffs: P(best t>=3.58) {np.mean(best_t >= OBS_T):.3f}; 95th best t {np.percentile(best_t, 95):.2f}; mean of picked {np.mean(best_m):.1f}, 95th {np.percentile(best_m, 95):.1f}")
for mode in ("iid", "block_20", "block_60"):
    f = P + f"placebo_{mode}.json"
    if not os.path.exists(f): continue
    R = json.load(open(f))
    fr = np.array([r["L126|-2.8"] for r in R]); al = np.array([r["always"] for r in R])
    bt = []; bm = []
    for r in R:
        k = max((k for k in r if k != "always"), key=lambda k: r[k][2] if r[k][2] == r[k][2] else -9)
        bt.append(r[k][2]); bm.append(r[k][1])
    bt, bm = np.array(bt), np.array(bm)
    print(f"{mode} ({len(R)} paths): always mean {np.nanmean(al[:,1]):.1f} (n {al[:,0].mean():.0f}); frozen-spec mean {np.nanmean(fr[:,1]):.1f} sd {np.nanstd(fr[:,1]):.1f}, trades {fr[:,0].mean():.0f}, P(mean>=91) {np.nanmean(fr[:,1] >= OBS_M):.4f}, P(t>=3.58) {np.nanmean(fr[:,2] >= OBS_T):.4f}, t sd {np.nanstd(fr[:,2]):.2f} share t>1.65 {np.nanmean(fr[:,2] > 1.65):.3f}")
    print(f"   best of {len(R[0]) - 1} family specs: P(best t>=3.58) {np.mean(bt >= OBS_T):.4f}, P(best t>=2.2) {np.mean(bt >= 2.2):.3f}; 95th best t {np.percentile(bt, 95):.2f}, max {bt.max():.2f}; mean of picked {np.mean(bm):.1f}, 95th {np.percentile(bm, 95):.1f}; P(picked mean >= 91 & t>=3.58) {np.mean((bm >= OBS_M) & (bt >= OBS_T)):.4f}")
