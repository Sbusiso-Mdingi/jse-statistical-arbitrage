import sys, csv, math, datetime as dt
import numpy as np
from scipy import stats as st
sys.path.insert(0, "service")
from app import switch as SW
B = np.load("/tmp/jse-review/copula/base.npz"); dates = list(B["dates"]); N = len(dates)
D = [dt.date.fromisoformat(x) for x in dates]
h = np.load("/tmp/jse-review/copula/h.npy"); h2 = B["h2"]; ok = ~np.isnan(h)
rs, rn = B["rs"], B["rn"]; sp = 0.5 * (rs - rn); cs = np.concatenate([[0.0], np.cumsum(sp)])
yr = np.array([d.year for d in D]); z, eg, b = B["z"], B["eg"], B["b"]
def trade_net(o, c, side, sched):
    tr = {"open": o, "close": c, "w_sbk": 0.5 * side, "w_ned": -0.5 * side}
    return float(SW.trade_costs(tr, D, sched).sum())
RT_F = 2 * SW.SCHEDULES["futures"]["exec"] + 5 * 50 / 252; RT_C = 2 * SW.SCHEDULES["cash"]["exec"] + 25 + 0.5 * 100 * 5 / 252
print(f"round trip, five-day hold, no roll: futures {RT_F:.1f} bps, cash {RT_C:.1f} bps")
ERAS = [("2010-19", 2010, 2020), ("2020", 2020, 2021), ("2021-26Q1", 2021, 2027)]
def report(name, trs):
    """trs: list of (open, close, side). gross and futures net per trade by era."""
    out = []
    for nm, lo, hi in ERAS:
        T = [t for t in trs if lo <= yr[t[0]] < hi and t[1] < N]
        if len(T) < 2: out.append(f"{nm}: n {len(T)}"); continue
        g = np.array([s * (cs[c + 1] - cs[o + 1]) for o, c, s in T]) * 1e4
        nf = g - np.array([trade_net(o, c, s, "futures") for o, c, s in T]) * 1e4
        hold = np.mean([c - o for o, c, _ in T])
        out.append(f"{nm}: n {len(T):3d} hold {hold:4.1f} gross {g.mean():6.1f} ({g.std(ddof=1)/math.sqrt(len(T)):4.1f}) fut net {nf.mean():6.1f}")
    print(f"{name:42s} | " + " | ".join(out))
def hold_rule(sigs):
    """H8-style: open on a signal day (side), hold 5 sessions, same-side signal restarts, opposite flips."""
    trs, cur, left = [], None, 0
    for t in range(N):
        sd = sigs[t]
        if sd != 0:
            if cur and cur[2] != sd: trs.append((cur[0], t, cur[2])); cur = None
            if cur is None: cur = [t, None, sd]
            left = 5
        elif cur: left -= 1
        if cur and left == 0: trs.append((cur[0], t, cur[2])); cur = None
    return trs
def fixed5(sigs):
    """Open on a signal when flat, hold exactly 5 sessions, ignore signals while open."""
    trs, t = [], 0
    while t < N - 6:
        if sigs[t] != 0: trs.append((t, t + 5, sigs[t])); t += 5
        else: t += 1
    return trs
base = np.where(ok & (np.abs(h - .5) > .45), np.sign(h - .5), 0.0)
print("\n== 3. alternatives to the one-day h (all reversal direction; signal-close fill) ==")
report("H8 rule (baseline)", hold_rule(base))
report("H8 signal, fixed 5, no extension", fixed5(base))
both = np.where(ok & (np.abs(h - .5) > .45) & (np.abs(h2 - .5) > .45) & (np.sign(h - .5) == -np.sign(h2 - .5)), np.sign(h - .5), 0.0)
print("  two-sided agreement share of H8 signal days: %.3f; corr(h, h2) %.3f" % (np.abs(both).sum() / np.abs(base).sum(), np.corrcoef(h[ok], h2[ok])[0, 1]))
report("two-sided daily (h and h2 both in tails)", hold_rule(both))
hh = np.where(ok, h - .5, 0.0); hh2 = np.where(ok, h2 - .5, 0.0)
for W in (3, 5, 10, 20):
    M = np.convolve(hh, np.ones(W))[:N]
    thr = 1.645 * math.sqrt(W / 12)
    sg = np.where(ok & (np.abs(M) > thr), np.sign(M), 0.0)
    report(f"windowed MI W={W} |M|>{thr:.2f} hold5", hold_rule(sg))
def reset_index(D_, two_sided, max_hold=60):
    """Xie et al. / Rad et al.: M accumulates from the last reset; open at |M1|>D (and M2 opposite beyond D);
    close when indices return to zero (both if two-sided), reset on close."""
    trs, M1, M2, cur = [], 0.0, 0.0, None
    for t in range(N):
        if not ok[t]: continue
        M1 += hh[t]; M2 += hh2[t]
        if cur is None:
            cond = abs(M1) > D_ and (not two_sided or (abs(M2) > D_ and np.sign(M2) == -np.sign(M1)))
            if cond: cur = (t, np.sign(M1))
        else:
            o, s = cur
            back = (s * M1 <= 0) and (not two_sided or s * M2 >= 0)
            if back or t - o >= max_hold:
                trs.append((o, t, s)); cur = None; M1 = M2 = 0.0
    return trs
for D_ in (0.3, 0.6, 1.0, 1.5):
    report(f"reset MI one-sided D={D_}", reset_index(D_, False))
    report(f"reset MI two-sided D={D_} (Rad/Xie)", reset_index(D_, True))
# pure gap: margin ARMA-implied relative mean forecast (5-day sum not available: use one-day)
mu_rel = 0.5 * (B["mu_s"] - B["mu_n"])
idx = np.flatnonzero(ok & (np.arange(N) + 2 < N))
for nm, lo, hi in ERAS:
    m = idx[(yr[idx] >= lo) & (yr[idx] < hi)]
    print(f"  margins' own relative mean forecast for t+1 vs realised, {nm}: slope {np.polyfit(mu_rel[m+1], sp[m+1],1)[0]:+.2f}  corr {np.corrcoef(mu_rel[m+1], sp[m+1])[0,1]:+.3f}")
np.save("/tmp/jse-review/copula/hh.npy", hh)
