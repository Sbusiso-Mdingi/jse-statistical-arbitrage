"""The gate as a state variable; alternative 'holding now' measures; window fragility map."""
import sys; sys.path.insert(0, "/tmp/jse-review/design")
from core import *
import pickle
w = pickle.load(open("/tmp/jse-review/design/w126.pkl", "rb"))
eg, z, b, phi = w["eg"], w["z"], w["b"], w["phi"]
gate = eg < -2.8
L = 126
specs = 0
def Lf(name, trs):
    global specs; specs += 1
    return line(name, trs)

base = sim(z, b, gate)
_, rows, _ = score(base)
tr_done = [t for t in base if t["close"] is not None]
# ---- descriptive: state at entry vs net
hl = np.where((phi > 0) & (phi < 1), -math.log(2) / np.log(np.clip(phi, 1e-9, 0.999999)), np.inf)
# variance ratio of residual increments over 10 sessions in the window
vr = np.full(n, np.nan)
for t in range(L - 1, n):
    xi, yi = x[t - L + 1:t + 1], y[t - L + 1:t + 1]
    u = yi - w["a"][t] - b[t] * xi
    d1 = np.diff(u); d10 = u[10:] - u[:-10]
    vr[t] = d10.var() / (10 * d1.var())
since = np.full(n, 0)
for t in range(1, n):
    since[t] = since[t - 1] + 1 if gate[t] else 0
deg = np.full(n, np.nan); deg[10:] = eg[10:] - eg[:-10]
# EG on the window ending k sessions earlier (not contaminated by the divergence being traded)
egk = {}
for k in (5, 10, 20):
    egk[k] = np.concatenate([np.full(k, np.nan), eg[:-k]])
feat = {"half-life (sessions)": hl, "VR(10)": vr, "sessions since gate opened": since.astype(float), "EG change over 10": deg,
        "EG at entry": eg, "|z| at entry": np.abs(z), "EG 10 sessions before": egk[10]}
net = np.array([r["net"] * 1e4 for r in rows])
for name, f in feat.items():
    v = np.array([f[t["open"]] for t in tr_done])
    q = np.nanpercentile(v[np.isfinite(v)], [33.3, 66.7])
    grp = [net[(v <= q[0])], net[(v > q[0]) & (v <= q[1])], net[v > q[1]]]
    rho = np.corrcoef(np.argsort(np.argsort(v)), np.argsort(np.argsort(net)))[0, 1]
    print(f"{name:28s} terciles cut {np.round(q, 2)}: mean net {[round(float(g.mean()), 1) for g in grp]} n {[len(g) for g in grp]} spearman {rho:.2f}")
print("half-life at entry: median", np.median([hl[t['open']] for t in tr_done]).round(1))

# ---- rules: added to the gate, or replacing it
Lf("BASE gate EG<-2.8", base)
for H in (10, 15):
    Lf(f"gate AND half-life < {H}", sim(z, b, gate & (hl < H)))
Lf("gate AND VR(10) < 0.8", sim(z, b, gate & (vr < 0.8)))
Lf("half-life < 10 alone (no EG)", sim(z, b, hl < 10))
for k in (5, 10, 20):
    Lf(f"gate on EG of window ending {k} sessions back", sim(z, b, egk[k] < -2.8))
    Lf(f"EG now OR EG {k} back below -2.8", sim(z, b, gate | (egk[k] < -2.8)))
Lf("gate AND open >= 5 sessions", sim(z, b, gate & (since >= 5)))
# hysteresis: open below -2.8, stays open until above -2.0 (entries allowed while open)
hy = np.zeros(n, bool); st = False
for t in range(n):
    if not np.isnan(eg[t]):
        if eg[t] < -2.8: st = True
        elif eg[t] > -2.0: st = False
    hy[t] = st
Lf("hysteresis gate: open < -2.8, shut > -2.0", sim(z, b, hy))
# sequential break monitor inside the spread: CUSUM from engine on the entry window -- reuse engine 'C' modes as gate
for c in (7.66,):
    mode = sw.modes(x, y, eg, "C", c)
    Lf("H14 CUSUM spell (C05) as gate", sim(z, b, mode.astype(bool)))
print("SPECS gate", specs)

# ---- window fragility map (each window with its own EG<-2.8 gate)
print("window map, own gate -2.8:")
for LL in (90, 110, 120, 132, 140, 150, 180):
    ww = wstats(x, y, LL)
    r = line(f"  window {LL}", sim(ww["z"], ww["b"], ww["eg"] < -2.8))
    specs += 1
print("SPECS total", specs)
