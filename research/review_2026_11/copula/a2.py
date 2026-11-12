import csv, math, datetime as dt
from collections import defaultdict
import numpy as np
B = np.load("/tmp/jse-review/copula/base.npz"); dates = list(B["dates"]); N = len(dates)
h = np.load("/tmp/jse-review/copula/h.npy"); ok = ~np.isnan(h)
yr = np.array([int(x[:4]) for x in dates])
def bars(name):
    out = defaultdict(dict)
    for r in csv.DictReader(open(f"data/raw/{name}_60m.csv")):
        t = dt.datetime.utcfromtimestamp(int(r["time"]))
        if t.date().isoformat() > "2026-03-31": continue
        out[t.date().isoformat()][t.hour] = (float(r["open"]), float(r["close"]))
    return out
S, Nd = bars("sbk"), bars("ned")
# raw daily closes for alignment check
raw = {nm: {r["date"]: float(r["close"]) for r in csv.DictReader(open(f"data/raw/{nm}.csv")) if r["close"] not in ("NA", "")} for nm in ("sbk", "ned")}
chk = [abs(math.log(S[x][14][1] / raw["sbk"][x])) for x in dates if x in S and 14 in S[x] and x in raw["sbk"]]
print("last-bar close vs daily close |log diff| median %.4f, share >0.5%%: %.3f" % (np.median(chk), np.mean(np.array(chk) > .005)))
HRS = list(range(7, 15))
def rel_path(t):
    """Relative log return of SBK minus NED (x0.5) from the close of day t: open of t+1, each bar close of t+1, then closes t+2..t+5."""
    d0, d1 = dates[t], dates[t + 1]
    if not all(k in S and k in Nd for k in (d0, d1)) or 14 not in S[d0] or 14 not in Nd[d0] or any(hh not in S[d1] or hh not in Nd[d1] for hh in HRS): return None
    c0 = math.log(S[d0][14][1]) - math.log(Nd[d0][14][1])
    pts = [math.log(S[d1][7][0]) - math.log(Nd[d1][7][0])] + [math.log(S[d1][hh][1]) - math.log(Nd[d1][hh][1]) for hh in HRS]
    # day t itself: from close t-1 to 16:00 and to close
    dm = dates[t - 1]
    if dm not in S or dm not in Nd or 14 not in S[dm] or 14 not in Nd[dm] or 13 not in S[d0] or 13 not in Nd[d0]: return None
    cm = math.log(S[dm][14][1]) - math.log(Nd[dm][14][1])
    day_peak = max((abs(math.log(S[d0][hh][1]) - math.log(Nd[d0][hh][1]) - cm) for hh in HRS if hh in S[d0] and hh in Nd[d0]))
    at16 = math.log(S[d0][13][1]) - math.log(Nd[d0][13][1]) - cm
    return 0.5 * (np.array(pts) - c0), 0.5 * (c0 - cm), 0.5 * at16, 0.5 * day_peak
sig = np.flatnonzero(ok & (np.abs(h - .5) > .45) & (np.arange(N) + 6 < N))
BLK = [("2010-14", 2010, 2015), ("2015-19", 2015, 2020), ("2020", 2020, 2021), ("2021-23", 2021, 2024), ("2024-26Q1", 2024, 2027)]
print("signal-direction relative return from signal close (bps): open t+1 | 10:00 | 12:00 | 14:00 | close t+1   ; day-t move: at 16:00 / at close / intraday peak |move|")
for nm, lo, hi in BLK + [("2010-19", 2010, 2020), ("2021-26Q1", 2021, 2027)]:
    P, D = [], []
    for t in sig[(yr[sig] >= lo) & (yr[sig] < hi)]:
        r = rel_path(t)
        if r is None: continue
        s = 1.0 if h[t] > .5 else -1.0
        P.append(s * r[0] * 1e4); D.append((s * r[2] * 1e4, s * r[1] * 1e4, r[3] * 1e4))
    P = np.array(P); D = np.array(D)
    if not len(P): continue
    se = P.std(0, ddof=1) / math.sqrt(len(P))
    print(f"{nm:10s} n {len(P):3d}  open {P[:,0].mean():6.1f} ({se[0]:.1f}) 10h {P[:,1].mean():6.1f} 12h {P[:,3].mean():6.1f} 14h {P[:,5].mean():6.1f} close {P[:,-1].mean():6.1f} ({se[-1]:.1f}) | overnight share of next-day {P[:,0].mean()/P[:,-1].mean() if P[:,-1].mean() else float('nan'):+.2f} | day t: 16:00 {D[:,0].mean():6.1f}  close {D[:,1].mean():6.1f}  peak|.| {D[:,2].mean():5.1f}")
# unconditional: share of the next-day reversal of large close-to-close relative moves that is overnight, all days with |day move| > 2 sd (no copula)
print("\n5-day path measured on last-bar closes (excludes both closing auctions) vs official closes, bps")
def lb(x, nm): 
    D = S if nm == "s" else Nd
    return math.log(D[x][14][1]) if x in D and 14 in D[x] else None
rs, rn = B["rs"], B["rn"]; sp = 0.5 * (rs - rn); cs = np.concatenate([[0.0], np.cumsum(sp)])
for nm, lo, hi in BLK + [("2010-19", 2010, 2020), ("2021-26Q1", 2021, 2027)]:
    a, b, auc = [], [], []
    for t in sig[(yr[sig] >= lo) & (yr[sig] < hi)]:
        if t + 5 >= N: continue
        vals = [lb(dates[t], "s"), lb(dates[t], "n"), lb(dates[t + 5], "s"), lb(dates[t + 5], "n")]
        if None in vals: continue
        s = 1.0 if h[t] > .5 else -1.0
        a.append(s * 0.5 * ((vals[2] - vals[0]) - (vals[3] - vals[1])) * 1e4)
        b.append(s * (cs[t + 6] - cs[t + 1]) * 1e4)
        # auction deviation on day t: official close rel vs last bar rel
        rc = math.log(raw["sbk"][dates[t]]) - math.log(raw["ned"][dates[t]]) if dates[t] in raw["sbk"] and dates[t] in raw["ned"] else None
        if rc is not None: auc.append(s * 0.5 * (rc - (vals[0] - vals[1])) * 1e4)
    a, b = np.array(a), np.array(b)
    print(f"{nm:10s} n {len(a):3d}  official close-to-close 5d {b.mean():6.1f} ({b.std(ddof=1)/math.sqrt(len(b)):.1f})  last-bar 5d {a.mean():6.1f} ({a.std(ddof=1)/math.sqrt(len(a)):.1f})  auction deviation on signal day {np.mean(auc):6.1f} bps (median {np.median(auc):.1f})")
