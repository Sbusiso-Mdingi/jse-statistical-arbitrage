import json, numpy as np, math
D = json.load(open("/tmp/jse-review/overfit/trades_h16.json"))
v = np.array(D["v"]); yr = np.array(D["year"]); rng = np.random.default_rng(1)
B = 20000
def cluster_boot(ids):
    u = np.unique(ids); groups = [v[ids == k] for k in u]; G = len(u)
    sums = np.array([g.sum() for g in groups]); cnts = np.array([len(g) for g in groups])
    idx = rng.integers(0, G, (B, G))
    m = sums[idx].sum(1) / cnts[idx].sum(1)
    # cluster-robust t
    res = np.array([(g - v.mean()).sum() for g in groups])
    se = math.sqrt(G / (G - 1) * (res ** 2).sum()) / len(v)
    return G, np.percentile(m, [2.5, 5, 50]).round(1), (m <= 0).mean(), round(v.mean() / se, 2)
print("iid t", round(v.mean() / (v.std(ddof=1) / math.sqrt(len(v))), 2))
m = v[rng.integers(0, len(v), (B, len(v)))].mean(1); print("iid boot 2.5/5/50", np.percentile(m, [2.5, 5, 50]).round(1), "P<=0", (m <= 0).mean())
for name, ids in (("year", yr), ("episode gap21", np.array(D["ep21"])), ("episode gap63", np.array(D["ep63"]))):
    print(name, cluster_boot(ids))
# moving block over trade sequence
for bl in (3, 5, 8):
    nb = math.ceil(len(v) / bl); starts = rng.integers(0, len(v) - bl + 1, (B, nb))
    mm = np.array([np.concatenate([v[s:s + bl] for s in row])[:len(v)].mean() for row in starts[:5000]])
    print("block", bl, np.percentile(mm, [2.5, 5, 50]).round(1), (mm <= 0).mean())
