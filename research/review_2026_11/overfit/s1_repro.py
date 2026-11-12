import sys; sys.path.insert(0, "/tmp/jse-review/overfit")
from common import *
import pickle
d, dates, x, y, rs, rn, dev = setup()
print("n", len(dates), dates[0], dates[-1])
W = {L: rolling(x, y, L) for L in (63, 126, 252)}
pickle.dump({"W": W}, open("/tmp/jse-review/overfit/W.pkl", "wb"))
b, z, eg = W[126]
for c in (-2.0, -2.4, -2.6, -2.8, -3.0, -3.34, -3.6):
    trs = run_rule(eg < c, b, z, dev)
    for s in ("futures", "cash"):
        _, rows = score(trs, dates, rs, rn, s)
        v = np.array([r["net"] for r in rows]) * 1e4
        if s == "futures":
            eras = [round(float(np.mean([r["net"] for r in rows if a <= r["d_open"].isoformat() < bb]) * 1e4), 1) for a, bb in ERAS]
            print(c, len(v), round(v.mean(), 1), round(tstat(v), 2), eras, "open at end:", trs[-1]["close"] is None, end=" ")
        else:
            print("cash", round(v.mean(), 1))
