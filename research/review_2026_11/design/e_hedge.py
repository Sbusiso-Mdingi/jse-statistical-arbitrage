"""Hedge ratio and spread definitions. Gate is always the 126-session EG < -2.8 on the frozen OLS unless stated."""
import sys; sys.path.insert(0, "/tmp/jse-review/design")
from core import *
import pickle
w = pickle.load(open("/tmp/jse-review/design/w126.pkl", "rb"))
gate = w["eg"] < -2.8
L = 126
specs = 0
def Lf(name, trs):
    global specs; specs += 1
    return line(name, trs)

def adf_stat(u):
    du = np.diff(u); a1, a2, yy = u[1:-1], du[:-1], du[1:]
    X = np.column_stack([a1, a2]); beta, *_ = np.linalg.lstsq(X, yy, rcond=None)
    e = yy - X @ beta; s2 = e @ e / (len(yy) - 2); cov = s2 * np.linalg.inv(X.T @ X)
    return beta[0] / math.sqrt(cov[0, 0])

Lf("BASE OLS NED on SBK", sim(w["z"], w["b"], gate))
# 1:1 weights but OLS signal
Lf("OLS signal, 1:1 legs (b=1 weights)", sim(w["z"], np.ones(n), gate))

# TLS and reverse regression and fixed ratio
bT = np.full(n, np.nan); zT = np.full(n, np.nan); egT = np.full(n, np.nan)
bR = np.full(n, np.nan); zR = np.full(n, np.nan); egR = np.full(n, np.nan)
z1 = np.full(n, np.nan); eg1 = np.full(n, np.nan)
for t in range(L - 1, n):
    xi, yi = x[t - L + 1:t + 1], y[t - L + 1:t + 1]
    dx, dy = xi - xi.mean(), yi - yi.mean()
    sxx, syy, sxy = dx @ dx, dy @ dy, dx @ dy
    bt = (syy - sxx + math.sqrt((syy - sxx) ** 2 + 4 * sxy ** 2)) / (2 * sxy)
    u = dy - bt * dx; bT[t] = bt; zT[t] = u[-1] / math.sqrt(u @ u / (L - 2)); egT[t] = adf_stat(u)
    c = sxy / syy; v = dx - c * dy  # SBK on NED
    bR[t] = 1 / c; zR[t] = -(v[-1] / math.sqrt(v @ v / (L - 2))); egR[t] = adf_stat(v)  # sign so z>0 means NED rich
    r1 = dy - dx; z1[t] = r1[-1] / r1.std(ddof=1); eg1[t] = adf_stat(r1)
Lf("TLS spread, OLS gate", sim(zT, bT, gate))
Lf("TLS spread, TLS gate", sim(zT, bT, egT < -2.8))
Lf("reverse (SBK on NED), OLS gate", sim(zR, bR, gate))
Lf("reverse (SBK on NED), own gate", sim(zR, bR, egR < -2.8))
Lf("fixed 1:1 log ratio, OLS gate", sim(z1, np.ones(n), gate))
Lf("fixed 1:1 log ratio, own ADF gate", sim(z1, np.ones(n), eg1 < -2.8))
print("corr b OLS vs TLS", np.corrcoef(w["b"][L:], bT[L:])[0, 1].round(3), "median b OLS/TLS/rev", np.nanmedian(w["b"]).round(2), np.nanmedian(bT).round(2), np.nanmedian(bR).round(2))

# Kalman filter on y = a + b x, random walk states
def kalman(delta, ve=None):
    th = np.zeros(2); P = np.eye(2); Vw = delta / (1 - delta) * np.eye(2)
    zz = np.full(n, np.nan); bb = np.full(n, np.nan)
    Ve = ve if ve is not None else 1e-4
    for t in range(n):
        F = np.array([1.0, x[t]])
        R = P + Vw
        yhat = F @ th; e = y[t] - yhat; Q = F @ R @ F + Ve
        K = R @ F / Q
        th = th + K * e; P = R - np.outer(K, F) @ R
        if t > 250:
            zz[t] = e / math.sqrt(Q); bb[t] = th[1]
    return zz, bb
for delta in (1e-5, 1e-4):
    zk, bk = kalman(delta)
    # Kalman innovation z is one-step; use the post-update residual / rolling sd instead for a level signal
    res = y - (np.nan_to_num(bk) * x)
    print(f"kalman delta {delta}: b median {np.nanmedian(bk):.2f}, sd of daily db {np.nanstd(np.diff(bk)):.4f} (OLS126 {np.nanstd(np.diff(w['b'])):.4f})")
    # level z: residual of current Kalman line over trailing 126 sessions
    zl = np.full(n, np.nan)
    for t in range(400, n):
        a_ = y[t - L + 1:t + 1] - bk[t] * x[t - L + 1:t + 1]
        zl[t] = (a_[-1] - a_.mean()) / a_.std(ddof=1)
    Lf(f"Kalman b (delta {delta}), level z on 126, OLS gate", sim(zl, bk, gate))

# windows near 126 (neighbourhood check, not a search)
for LL in (100, 160):
    ww = wstats(x, y, LL)
    Lf(f"window {LL} (own gate -2.8)", sim(ww["z"], ww["b"], ww["eg"] < -2.8))
    Lf(f"window {LL} spread, 126 gate", sim(ww["z"], ww["b"], gate))

# daily re-hedge to the current rolling b inside the trade (extra exec cost on the leg changes)
base = sim(w["z"], w["b"], gate)
_, rows, _ = score(base)
ex = sw.SCHEDULES["futures"]["exec"] / 1e4
v = []
for tr, r in zip([t for t in base if t["close"] is not None], rows):
    o, c, side = tr["open"], tr["close"], tr["side"]
    g = 0.0; cost = 0.0; ws, wn = tr["w_sbk"], tr["w_ned"]
    for j in range(o + 1, c + 1):
        g += ws * rs[j] + wn * rn[j]
        if j < c:
            k = abs(w["b"][j]); ws2, wn2 = -side * k / (1 + k), side / (1 + k)
            cost += (abs(ws2 - ws) + abs(wn2 - wn)) * ex; ws, wn = ws2, wn2
    base_cost = r["gross"] - r["net"]
    v.append((g - base_cost - cost) * 1e4)
v = np.array(v); specs += 1
print(f"daily re-hedge to rolling b: n={len(v)} fut={v.mean():.1f} t={v.mean()/v.std(ddof=1)*math.sqrt(len(v)):.2f}")
print("SPECS", specs)
