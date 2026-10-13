"""Pre-declared v2 candidates. Usage: candidates.py START END  (dates are trading days)."""
import json, math, sys, csv
import numpy as np

START, END = sys.argv[1], sys.argv[2]
w = json.load(open("data/walkforward.json")); h = w["history"]
d = np.array(h["date"])
rs_all = np.expm1(np.array(h["r_sbk"])); rn_all = np.expm1(np.array(h["r_ned"]))
hn_all = np.array(h["h_ns"])

def trailing_vol(r, n=60):
    out = np.full(len(r), np.nan)
    for t in range(n, len(r)): out[t] = r[t - n + 1 : t + 1].std(ddof=1)  # known at close t
    return out

vs, vn = trailing_vol(rs_all), trailing_vol(rn_all)
m = (d >= START) & (d < END)
rs, rn, hn, vs, vn = rs_all[m], rn_all[m], hn_all[m], vs[m], vn[m]
COST = 10 / 1e4

def signal(q, days):
    pos = np.zeros(len(hn)); cur = 0.0; left = 0
    for t in range(len(hn)):
        if abs(hn[t] - 0.5) > q / 2: cur, left = (1.0 if hn[t] > 0.5 else -1.0), days
        elif left > 0: left -= 1
        if left == 0: cur = 0.0
        pos[t] = cur
    return pos

def evaluate(pos, weighting="equal", target=None):
    ws = np.full(len(pos), 0.5); wn = np.full(len(pos), 0.5)
    if weighting == "vol":
        ws = vn / (vs + vn); wn = vs / (vs + vn)
    scale = np.ones(len(pos))
    spread_sd = np.sqrt((ws * vs) ** 2 + (wn * vn) ** 2) * math.sqrt(252)  # ignores correlation: conservative
    if target:
        # realised spread vol, trailing 60 days, known at close t
        sp = ws * rs - wn * rn
        rv = np.array([sp[max(0, t - 59): t + 1].std(ddof=1) * math.sqrt(252) if t >= 20 else np.nan for t in range(len(sp))])
        scale = np.clip(target / rv, 0, 2.0)
    expo_s = np.nan_to_num(pos * ws * scale); expo_n = np.nan_to_num(pos * wn * scale)
    held_s = np.concatenate([[0.0], expo_s[:-1]]); held_n = np.concatenate([[0.0], expo_n[:-1]])
    turn = np.abs(np.diff(np.concatenate([[0.0], expo_s]))) + np.abs(np.diff(np.concatenate([[0.0], expo_n])))
    net = held_s * rs - held_n * rn - turn * COST
    eq = np.cumprod(1 + net); yrs = len(net) / 252; sd = net.std(ddof=1)
    return dict(sharpe=net.mean() / sd * math.sqrt(252), cagr=eq[-1] ** (1 / yrs) - 1,
                vol=sd * math.sqrt(252), mdd=float((eq / np.maximum.accumulate(eq) - 1).min()),
                inmkt=float((pos != 0).mean()), turnover=float(turn.sum() / yrs))

base = signal(0.90, 5)
C = {
    "v1 report rule (for reference, equal legs, 1-day logic)": None,
    "A hold 5d, q90, equal legs": evaluate(base),
    "B hold 5d, q90, vol-weighted legs": evaluate(base, "vol"),
    "C hold 5d, q90, vol-weighted, 10% vol target": evaluate(base, "vol", 0.10),
}
for k, r in C.items():
    if r: print(f"{k:50s} SR {r['sharpe']:5.2f} CAGR {r['cagr']*100:5.1f}% vol {r['vol']*100:4.1f}% MDD {r['mdd']*100:6.1f}% in {r['inmkt']*100:3.0f}% turn {r['turnover']:4.1f}x/yr")
# Neighbourhood check for robustness (not selection): nearby thresholds and holds for B.
for q in (0.85, 0.90, 0.95):
    print(" ", "q", q, " ".join(f"{days}d:{evaluate(signal(q, days), 'vol')['sharpe']:5.2f}" for days in (3, 4, 5, 7, 10)))
