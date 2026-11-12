from common import *
dates, ls, ln = load()
print(len(dates), dates[0], dates[-1])
x, y = np.cumsum(ls), np.cumsum(ln)
rs, rn = np.expm1(ls), np.expm1(ln)
trs, b, z, eg = h16_trades(dates, x, y)
for s in ("futures", "cash", None):
    rows = per_trade(trs, dates, rs, rn, s)
    print(s, summ([r["net"] for r in rows]))
rows = per_trade(trs, dates, rs, rn, "futures")
hold = np.array([r["close"] - r["open"] for r in rows])
print("hold mean/median/max", hold.mean(), np.median(hold), hold.max(), "share hitting 60:", (hold >= 60).mean())
k = np.array([abs(b[r["open"]]) for r in rows]); bs = np.array([b[r["open"]] for r in rows])
print("b at entry: min %.2f p10 %.2f median %.2f p90 %.2f max %.2f, negative %d" % (bs.min(), *np.percentile(bs, [10, 50, 90]), bs.max(), (bs < 0).sum()))
net = np.array([r["w_sbk"] + r["w_ned"] for r in rows])
print("net exposure |sum w| mean %.3f max %.3f" % (np.abs(net).mean(), np.abs(net).max()))
# exit reasons
reasons = []
for r in rows:
    c = r["close"]; side = r["side"]
    if abs(z[c]) > sw.STOP: reasons.append("stop")
    elif c - r["open"] >= sw.MAX_HOLD: reasons.append("time")
    else: reasons.append("revert")
import collections; print(collections.Counter(reasons))
# time in market
inm = np.zeros(len(dates), bool)
for r in rows: inm[r["open"] + 1: r["close"] + 1] = True
span = np.array([dt.date(2006,1,3) <= t for t in dates])
print("time in market %.3f" % inm[span].mean(), "years", span.sum() / 252)
# rolls per trade
roll_n = []
for r in rows:
    c = sw.trade_costs(r, dates, "futures"); exec_ = sw.SCHEDULES["futures"]["exec"] / 1e4
    roll_n.append(int(round(c[r["open"] + 1: r["close"]].max() / (2 * exec_))) if r["close"] > r["open"] + 1 else 0)
    # crude
