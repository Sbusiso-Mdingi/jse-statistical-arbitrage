"""Design-period grid (trading 2010-2019 only). Rules are declared here before any run."""
import itertools, json, math, sys
import numpy as np

w = json.load(open("data/walkforward.json"))
h = w["history"]
folds = {f["id"]: f for f in w["folds"]}
d = np.array(h["date"])
END = sys.argv[1] if len(sys.argv) > 1 else "2020-01-01"
START = sys.argv[2] if len(sys.argv) > 2 else "0000"
m = (d < END) & (d >= START)
rs = np.expm1(np.array(h["r_sbk"]))[m]
rn = np.expm1(np.array(h["r_ned"]))[m]
hn = np.array(h["h_ns"])[m]
vol = np.array(h["spread_vol"])[m]
fold = np.array(h["fold"])[m]
COST = 10 / 1e4

rng = np.random.default_rng(0)
U = rng.uniform(size=400_000) - 0.5
def model_quantile(lam, q):
    """Quantile of |M| when h is uniform and independent, as the model implies."""
    M = np.zeros_like(U); acc = 0.0
    for i, x in enumerate(U):
        acc = lam * acc + x; M[i] = acc
    return float(np.quantile(np.abs(M[1000:]), q))

def run(pos):
    held = np.concatenate([[0.0], pos[:-1]])
    turn = np.abs(np.diff(np.concatenate([[0.0], pos])))
    net = held * 0.5 * (rs - rn) - turn * COST
    sd = net.std(ddof=1)
    eq = np.cumprod(1 + net)
    yrs = len(net) / 252
    trades = int((np.diff(np.concatenate([[0.0], pos])) != 0).sum() / 1)
    return dict(sharpe=net.mean() / sd * math.sqrt(252), cagr=eq[-1] ** (1 / yrs) - 1,
                mdd=float((eq / np.maximum.accumulate(eq) - 1).min()), changes=trades,
                inmkt=float((pos != 0).mean()))

def vol_ok(pct):
    if pct is None: return np.ones(len(vol), bool)
    return np.array([not math.isnan(v) and v < folds[int(f)]["q_vol"][pct - 50] for v, f in zip(vol, fold)])

def decay_rule(lam, qin, qout, vpct):
    enter, leave = model_quantile(lam, qin), model_quantile(lam, qout)
    ok = vol_ok(vpct); pos = np.zeros(len(hn)); cur = 0.0; M = 0.0
    for t in range(len(hn)):
        M = lam * M + (hn[t] - 0.5)
        side = 1.0 if M > 0 else -1.0
        if abs(M) > enter and side != cur and ok[t]: cur = side
        elif cur != 0 and (abs(M) < leave or side != cur): cur = 0.0
        pos[t] = cur
    return pos

def hold_rule(qin, days, vpct):
    enter = qin / 2  # |h - 0.5| quantile under uniform h
    ok = vol_ok(vpct); pos = np.zeros(len(hn)); cur = 0.0; left = 0
    for t in range(len(hn)):
        s = abs(hn[t] - 0.5); side = 1.0 if hn[t] > 0.5 else -1.0
        if s > enter and ok[t]: cur, left = side, days
        elif left > 0: left -= 1
        if left == 0: cur = 0.0
        pos[t] = cur
    return pos

rows = []
for lam, qin, qout, v in itertools.product([0.0, 0.5, 0.7, 0.8, 0.9], [0.90, 0.95, 0.975], [0.50, 0.75], [None, 80]):
    rows.append((f"decay lam={lam} in={qin} out={qout} vol={v}", run(decay_rule(lam, qin, qout, v))))
for qin, days, v in itertools.product([0.90, 0.95, 0.975], [3, 5, 10], [None, 80]):
    rows.append((f"hold in={qin} days={days} vol={v}", run(hold_rule(qin, days, v))))
for name, r in sorted(rows, key=lambda x: -x[1]["sharpe"]):
    print(f"{name:45s} SR {r['sharpe']:5.2f} CAGR {r['cagr']*100:5.1f}% MDD {r['mdd']*100:6.1f}% chg {r['changes']:4d} in {r['inmkt']*100:4.0f}%")
print(len(rows), "variants")
