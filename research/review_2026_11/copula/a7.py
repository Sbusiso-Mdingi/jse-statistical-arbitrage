import sys, math, datetime as dt, numpy as np
sys.path.insert(0, "service")
from app import switch as SW
B = np.load("/tmp/jse-review/copula/base.npz"); dates = list(B["dates"]); N = len(dates); D = [dt.date.fromisoformat(x) for x in dates]
h = np.load("/tmp/jse-review/copula/h.npy"); ok = ~np.isnan(h); yr = np.array([d.year for d in D])
dy = np.load("/tmp/jse-review/copula/dy.npy")
rs, rn, b, z, eg = B["rs"], B["rn"], B["b"], B["z"], B["eg"]
gate = (eg < SW.GATE_CRIT).astype(np.int8)
hz = np.where(ok, h, 0.5)
trs = SW.trades(gate, hz, b, z, copula_on=False, hold_through=True)
_, rows = SW.daily_returns(trs, D, rs, rn, "futures")
done = [r for r in rows if r["complete"]]
print("H16 trades opened 2006+ completed by 2026-03-31:", len(done), " mean fut net %.1f bps" % (np.mean([r["net"] for r in done]) * 1e4))
T = [r for r in done if ok[r["open"]]]
net = np.array([r["net"] for r in T]) * 1e4
# total-return correction: add dividend yields on held days times weights
corr = np.array([sum(r["w_sbk"] * dy[0][t] + r["w_ned"] * dy[1][t] for t in range(r["open"] + 1, r["close"] + 1)) for r in T]) * 1e4
print(f"with h available (2010+): {len(T)} trades, mean fut net {net.mean():.1f} (se {net.std(ddof=1)/math.sqrt(len(T)):.1f}); total-return correction adds {corr.mean():+.1f} bps a trade (min {corr.min():.0f}, max {corr.max():.0f})")
side = np.array([r["side"] for r in T])  # +1: long NED short SBK (NED cheap)
he = np.array([h[r["open"]] for r in T])
# copula agreement: spread long SBK/short NED (side -1) agrees with h>0.5 (NED rich relative today)
agree = np.sign(he - .5) == -side
cop_side_tail = np.abs(he - .5) > .45
# h over the 5 sessions before entry, summed
m5 = np.array([np.nansum(h[max(0, r["open"] - 4):r["open"] + 1] - .5) * (-r["side"]) for r in T])
def show(lbl, m):
    x = net[m]; 
    print(f"  {lbl:52s} n {m.sum():3d}  fut net {x.mean():7.1f}  se {x.std(ddof=1)/math.sqrt(max(m.sum(),2)) if m.sum()>1 else float('nan'):5.1f}  win {np.mean(x>0)*100:3.0f}%")
show("all", np.ones(len(T), bool))
show("h at entry agrees with spread side", agree)
show("h at entry disagrees", ~agree)
show("h at entry in copula tail, agreeing", agree & cop_side_tail)
show("h at entry |h-.5|>.25, agreeing", agree & (np.abs(he - .5) > .25))
show("h at entry |h-.5|>.25, disagreeing", ~agree & (np.abs(he - .5) > .25))
show("5-session h sum agrees (>0)", m5 > 0)
show("5-session h sum disagrees (<=0)", m5 <= 0)
show("design-era trades (2010-19)", np.array([yr[r['open']] < 2020 for r in T]))
show("2020+ trades", np.array([yr[r['open']] >= 2020 for r in T]))
# veto: an opposing copula tail signal during the trade; P&L from that day to the close vs the rest
print("  veto test: first opposing copula tail signal (h says the spread trade's side is wrong) during an open spread trade")
rem, n_op = [], 0
for r in T:
    for t in range(r["open"] + 1, r["close"]):
        if ok[t] and abs(h[t] - .5) > .45 and np.sign(h[t] - .5) == r["side"]:
            g = sum(r["w_sbk"] * rs[k] + r["w_ned"] * rn[k] for k in range(t + 1, r["close"] + 1)) * 1e4
            rem.append(g); n_op += 1; break
print(f"    trades with an opposing tail signal: {n_op}; gross P&L from that close to the trade's exit: mean {np.mean(rem):.1f} bps, median {np.median(rem):.1f}, win {np.mean(np.array(rem)>0)*100:.0f}% (a veto that exits there would save the negative of this less one exit's cost ~16 bps)")
rem, n_ag = [], 0
for r in T:
    for t in range(r["open"] + 1, r["close"]):
        if ok[t] and abs(h[t] - .5) > .45 and np.sign(h[t] - .5) == -r["side"]:
            g = sum(r["w_sbk"] * rs[k] + r["w_ned"] * rn[k] for k in range(t + 1, r["close"] + 1)) * 1e4
            rem.append(g); n_ag += 1; break
print(f"    trades with an agreeing tail signal later: {n_ag}; gross P&L from that close to exit: mean {np.mean(rem):.1f}, median {np.median(rem):.1f}")
print("  correlation of h at entry (signed to the trade) with trade net: %.3f" % np.corrcoef((he - .5) * (-side), net)[0, 1])
