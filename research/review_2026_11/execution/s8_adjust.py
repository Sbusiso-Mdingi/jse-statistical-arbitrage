from common import *
import csv as _csv
dates, ls, ln = load(); n = len(dates)
x, y = np.cumsum(ls), np.cumsum(ln); rs, rn = np.expm1(ls), np.expm1(ln)
raw = {k: daily_raw(k) for k in ("sbk", "ned")}
divs = collections = {}
dv = {"sbk": {}, "ned": {}}
for r in _csv.DictReader(open(REPO + "/data/raw/h15_div.csv")):
    dv[r["bank"]][dt.date.fromisoformat(r["ex_date"])] = float(r["amount"])
# raw closes on the same dates (session before first date needed: use dates list itself)
def lvl(k, with_div):
    c = np.array([raw[k][t][0] for t in dates])
    lr = np.zeros(n)
    for i in range(1, n):
        D = dv[k].get(dates[i], 0.0) if with_div else 0.0
        lr[i] = math.log((c[i] + D) / c[i - 1])
    return np.cumsum(lr)
base, *_ = h16_trades(dates, x, y)
def score(trs):
    _, rows = sw.daily_returns(trs, dates, rs, rn, "futures")
    v = [r["net"] for r in rows if r["complete"] and dates[r["open"]] >= dt.date(2006, 1, 1)]
    return summ(v), {r["open"] for r in rows if r["complete"] and dates[r["open"]] >= dt.date(2006,1,1)}
s0, o0 = score(base)
print("adjusted (as frozen):", s0)
for lab, wd in (("real-time total-return index from raw closes + dividends", True), ("raw closes, no dividends", False)):
    xx, yy = lvl("sbk", wd), lvl("ned", wd)
    trs, b, z, eg = h16_trades(dates, xx, yy)
    s, o = score(trs)
    bb, zz, ee = sw.rolling(x, y)
    m = ~np.isnan(z) & ~np.isnan(zz)
    print(lab, s, "same entry sessions:", len(o & o0), "| max |z diff| %.3f, max |eg diff| %.3f" % (np.nanmax(np.abs(z - zz)), np.nanmax(np.abs(eg - ee))))
print("--- factor step sizes vs D/P")
for k in ("sbk", "ned"):
    ds_ = sorted(raw[k]); f = {d: raw[k][d][1] / raw[k][d][0] for d in ds_}
    for d in sorted(dv[k])[-6:]:
        i = ds_.index(d) if d in ds_ else None
        if i:
            print(k, d, "D/P %.4f" % (dv[k][d] / raw[k][ds_[i - 1]][0]), "factor step %.6f" % (f[ds_[i - 1]] / f[d]))
# total-return P&L
def tr_ret(k):
    c = np.array([raw[k][t][0] for t in dates]); r = np.zeros(n)
    for i in range(1, n): r[i] = (c[i] + dv[k].get(dates[i], 0.0)) / c[i - 1] - 1
    return r
trs_s, trn = tr_ret("sbk"), tr_ret("ned")
print("price-only vs TR daily returns: mean diff sbk %.2f bps/day, ned %.2f" % ((trs_s - rs).mean() * 1e4, (trn - rn).mean() * 1e4))
def score2(trs, a, bb):
    _, rows = sw.daily_returns(trs, dates, a, bb, "futures")
    return summ([r["net"] for r in rows if r["complete"] and dates[r["open"]] >= dt.date(2006, 1, 1)])
print("frozen signals, total-return P&L:", score2(base, trs_s, trn))
xx, yy = lvl("sbk", True), lvl("ned", True)
trs_tr, *_ = h16_trades(dates, xx, yy)
print("TR signals, TR P&L:", score2(trs_tr, trs_s, trn))
# trades whose entry falls within 5 sessions after an ex-date
exi = set()
for k in dv:
    for d in dv[k]:
        if d in dates: exi.add(dates.index(d))
near = [t for t in base if t["close"] is not None and dates[t["open"]] >= dt.date(2006,1,1) and any(0 <= t["open"] - e <= 5 for e in exi)]
print("frozen trades opened within 5 sessions after an ex-date:", len(near), score2(near, rs, rn), "with TR P&L", score2(near, trs_s, trn))
