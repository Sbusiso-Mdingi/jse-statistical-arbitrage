import json, numpy as np, os
P = "/tmp/jse-review/overfit/"
for mode in ("iid", "block_20", "block_60"):
    f = P + f"placebo_{mode}.json"
    if not os.path.exists(f): continue
    R = json.load(open(f))
    for mn in (30, 45):
        bt, bm = [], []
        for r in R:
            ks = [k for k in r if k != "always" and r[k][0] >= mn and r[k][2] == r[k][2]]
            if not ks: bt.append(-9); bm.append(np.nan); continue
            k = max(ks, key=lambda k: r[k][2]); bt.append(r[k][2]); bm.append(r[k][1])
        bt, bm = np.array(bt), np.array(bm)
        print(f"{mode} min{mn}: P(best t>=3.58) {np.mean(bt >= 3.58):.4f}, P(best t>=2.9) {np.mean(bt >= 2.9):.3f}, 95th best t {np.percentile(bt, 95):.2f}; picked mean avg {np.nanmean(bm):.1f}, P(picked>=91 & t>=3.58) {np.mean((bm >= 91.1) & (bt >= 3.58)):.4f}")
