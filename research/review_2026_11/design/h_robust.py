"""Robustness of the leading candidates across implementation (lag, 16:00) and neighbouring windows."""
import sys; sys.path.insert(0, "/tmp/jse-review/design")
from core import *
import pickle
w = pickle.load(open("/tmp/jse-review/design/w126.pkl", "rb"))
I = pickle.load(open("/tmp/jse-review/design/intraday.pkl", "rb"))
eg, z, b = w["eg"], w["z"], w["b"]
gate = eg < -2.8
specs = 0
def Lf(name, trs):
    global specs; specs += 1
    return line(name, trs)

def block_t(d1, d2, blk=20, B=2000, seed=0):
    dd = (d1 - d2)[dev]; m = len(dd); rng = np.random.default_rng(seed)
    nb = m // blk; means = []
    for _ in range(B):
        st = rng.integers(0, m - blk, nb)
        means.append(np.concatenate([dd[s:s + blk] for s in st]).mean())
    return dd.mean() * 252 * 1e4, dd.mean() / np.std(means)

_, _, t0 = score(sim(z, b, gate))
for ex in (-0.25, -0.5):
    _, _, t1 = score(sim(z, b, gate, exit_=ex))
    a, tt = block_t(t1, t0)
    print(f"overshoot exit {ex} minus BASE: {a:.0f} bps a year, block-bootstrap t {tt:.2f}")
for lag in (1,):
    for ex in (0.0, -0.25, -0.5):
        Lf(f"lag {lag}, exit {ex}", sim(z, b, gate, lag=lag, exit_=ex))
start = dt.date(2009, 6, 1)
zz = I["z16"]; g16 = I["eg16"] < -2.8
for ex in (0.0, -0.25, -0.5):
    Lf(f"16:00 decision, close fill, exit {ex}", [t for t in sim(zz, I["b16"], g16, exit_=ex) if dates[t["open"]] >= start])
for LL in (110, 140):
    ww = wstats(x, y, LL)
    for ex in (0.0, -0.5):
        Lf(f"window {LL}, exit {ex}", sim(ww["z"], ww["b"], ww["eg"] < -2.8, exit_=ex))
# overshoot exit plus a shorter time cap (to see if the extra time costs time-outs)
Lf("exit -0.5, hold 40", sim(z, b, gate, exit_=-0.5, hold=40))
# 16:00 decision with 16:00 entry but closing exit on daily z (exit known after close -> fill next close: lag on exit)
# gate shut mechanics: |z| on the first in-trade session the gate shuts
tr = sim(z, b, gate)
zs = []
for t in tr:
    if t["close"] is None: continue
    for j in range(t["open"] + 1, t["close"] + 1):
        if not gate[j]:
            zs.append((abs(z[j]), abs(t["z0"]), np.sign(z[j]) == np.sign(t["z0"]))); break
zs = np.array(zs)
print(f"gate first shuts inside {len(zs)} trades: median |z| then {np.median(zs[:,0]):.2f} vs entry {np.median(zs[:,1]):.2f}; same side as entry {zs[:,2].mean():.2f}")
# unconditional: P(gate shuts next session) by |z| today, while open
op = gate[:-1] & dev[:-1]
nxt = ~gate[1:]
az = np.abs(np.nan_to_num(z[:-1]))
for lo, hi in ((0, 0.5), (0.5, 1), (1, 1.5), (1.5, 2), (2, 9)):
    m = op & (az >= lo) & (az < hi)
    print(f"  gate open, |z| in [{lo},{hi}): P(shut next close) {nxt[m].mean():.3f}  n={m.sum()}")
print("SPECS", specs)
