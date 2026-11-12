from common import *
dates, ls, ln = load(); n = len(dates)
x, y = np.cumsum(ls), np.cumsum(ln); rs, rn = np.expm1(ls), np.expm1(ln)
trs, b, z, eg = h16_trades(dates, x, y)
done = [t for t in trs if t["close"] is not None and dates[t["open"]] >= dt.date(2006, 1, 1)]
V = 1.15
extra = {
 "fut_inst_hs5_c2": dict(exec=(2 + 0.548) * V + 5, stt=0, long_year=50, short_year=50, rolls=True),
 "fut_inst_hs20_c5": dict(exec=(5 + 0.548) * V + 20, stt=0, long_year=50, short_year=50, rolls=True),
 "fut_inst_hs20_c10_fund150": dict(exec=(10 + 0.548) * V + 20, stt=0, long_year=150, short_year=150, rolls=True),
 "fut_inst_norolls": dict(exec=(5 + 0.548) * V + 10, stt=0, long_year=50, short_year=50, rolls=False),
 "fut_sb_online": dict(exec=(50 / 125000 * 1e4 + 0.548) * V + 40, stt=0, long_year=200, short_year=200, rolls=True),
 "fut_psg": dict(exec=(50 + 0.548) * V, stt=0, long_year=150, short_year=-150, rolls=True),
 "cash_retail": dict(exec=25 * V + 5 + 1, stt=25, long_year=0, short_year=100, rolls=False),
 "cash_inst_hs10_borrow300": dict(exec=10 * V + 10 + 0.3, stt=25, long_year=0, short_year=300, rolls=False),
}
sw.SCHEDULES.update(extra)
for k in ["futures", "cash"] + list(extra):
    _, rows = sw.daily_returns(done, dates, rs, rn, k)
    v = np.array([r["net"] for r in rows]); print(f"{k:28s} exec {sw.SCHEDULES[k]['exec']:6.2f}  net/trade {summ(v)}")
# roll as calendar spread at one half-spread per leg instead of a full close+reopen
