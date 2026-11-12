from common import *
import csv as _csv
dates, ls, ln = load(); n = len(dates)
x, y = np.cumsum(ls), np.cumsum(ln); rs, rn = np.expm1(ls), np.expm1(ln)
trs, b, z, eg = h16_trades(dates, x, y)
done = [t for t in trs if t["close"] is not None and dates[t["open"]] >= dt.date(2006, 1, 1)]
S = sw.SCHEDULES
print("per-execution bps: futures %.2f cash %.2f" % (S["futures"]["exec"], S["cash"]["exec"]))
# cost decomposition futures
ex, fund, roll, nroll = [], [], [], []
for t in done:
    o, c = t["open"], t["close"]
    gross = abs(t["w_sbk"]) + abs(t["w_ned"])
    ex.append(2 * gross * S["futures"]["exec"])
    fund.append((c - o) * (S["futures"]["long_year"] + S["futures"]["short_year"]) * gross / 252 * 1.0 * (1 if True else 0))
    tot = sw.trade_costs(t, dates, "futures").sum() * 1e4
    roll.append(tot - ex[-1] - fund[-1]); nroll.append(round(roll[-1] / (2 * S["futures"]["exec"])))
print("futures per trade: exec %.1f funding %.1f rolls %.1f (mean rolls %.2f, trades with >=1 roll %d of %d)" % (np.mean(ex), np.mean(fund), np.mean(roll), np.mean(nroll), sum(r > 0 for r in nroll), len(done)))
cc = []
for t in done:
    cc.append(sw.trade_costs(t, dates, "cash").sum() * 1e4)
stt = [25 * (abs(t["w_sbk"]) + abs(t["w_ned"])) for t in done]
borrow = [(t["close"] - t["open"]) * 100 * (max(-t["w_sbk"], 0) + max(-t["w_ned"], 0)) / 252 for t in done]
print("cash per trade: total %.1f, of which STT %.1f, exec %.1f, borrow %.1f" % (np.mean(cc), np.mean(stt), 2 * S["cash"]["exec"], np.mean(borrow)))

# cash rate
rate = {}
for r in _csv.DictReader(open(REPO + "/data/raw/h15_rate.csv")):
    try: rate[r["observation_date"][:7]] = float(r["IRSTCI01ZAM156N"]) / 100
    except ValueError: pass
rr = np.array([rate.get(t.isoformat()[:7], np.nan) for t in dates])
for i in range(n):
    if np.isnan(rr[i]): rr[i] = rr[i - 1]
span = np.array([t >= dt.date(2006, 1, 3) for t in dates])
print("mean cash rate 2006-Mar 2026: %.2f%%" % (rr[span].mean() * 100))
# Excess-return correction: futures embed financing at r on net notional
corr = np.array([-(t["w_sbk"] + t["w_ned"]) * rr[t["open"] + 1:t["close"] + 1].sum() / 252 for t in done]) * 1e4
_, rows = sw.daily_returns(done, dates, rs, rn, "futures")
netf = np.array([r["net"] for r in rows]) * 1e4
print("net-exposure financing correction per trade: mean %.1f bps, sd %.1f, min %.1f max %.1f -> corrected futures %s" % (corr.mean(), corr.std(), corr.min(), corr.max(), summ((netf + corr) / 1e4)))
print("share of trades net long (sum w > 0): %.2f" % np.mean([t["w_sbk"] + t["w_ned"] > 0 for t in done]))

# Dividends inside trades
raw = {k: daily_raw(k) for k in ("sbk", "ned")}
divs = []
for r in _csv.DictReader(open(REPO + "/data/raw/h15_div.csv")):
    divs.append((dt.date.fromisoformat(r["ex_date"]), r["bank"], float(r["amount"])))
# check: adjusted/close factor steps only on ex-dates
for k in ("sbk", "ned"):
    ds_ = sorted(raw[k]); f = np.array([raw[k][d][1] / raw[k][d][0] for d in ds_])
    steps = [ds_[i] for i in range(1, len(ds_)) if abs(f[i] / f[i - 1] - 1) > 1e-6]
    exd = {d for d, bk, _ in divs if bk == k}
    print(k, "factor steps", len(steps), "on known ex-dates", sum(s in exd for s in steps), "ex-dates", len(exd), "first steps not ex-dates:", [s for s in steps if s not in exd][:5])
didx = {t: i for i, t in enumerate(dates)}
dwt, divshare, ntr_div = [], [], 0
for t in done:
    o, c = t["open"], t["close"]
    yl = {"sbk": 0.0, "ned": 0.0}
    for d, bk, amt in divs:
        if dates[o] < d <= dates[c] and d in didx:
            i = didx[d]; prev = dates[i - 1]
            yl[bk] += amt / raw[bk][prev][0]
    w = {"sbk": t["w_sbk"], "ned": t["w_ned"]}
    if yl["sbk"] or yl["ned"]: ntr_div += 1
    dwt.append(sum(0.2 * max(w[k], 0) * yl[k] for k in yl))  # long-leg withholding for a taxable individual on cash
    divshare.append(sum(w[k] * yl[k] for k in yl))
print("trades spanning an ex-date: %d of %d; mean net dividend carried %.1f bps; 20%% DWT on a cash long leg %.1f bps/trade (max %.1f)" % (ntr_div, len(done), np.mean(divshare) * 1e4, np.mean(dwt) * 1e4, np.max(dwt) * 1e4))

# Margin and capital
mae, pnl_path_min = [], []
for t in done:
    o, c = t["open"], t["close"]
    cum = np.cumsum(t["w_sbk"] * rs[o + 1:c + 1] + t["w_ned"] * rn[o + 1:c + 1])
    mae.append(min(0, cum.min()))
mae = np.array(mae) * 1e4
print("max adverse excursion per trade bps: median %.0f p90 %.0f p99 %.0f worst %.0f" % (np.median(mae), np.percentile(mae, 10), np.percentile(mae, 1), mae.min()))
im = np.mean([0.12 * abs(t["w_sbk"]) + 0.15 * abs(t["w_ned"]) for t in done])
print("initial margin as share of gross notional (SBK 12%%, NED 15%%): %.3f" % im)
# annual P&L
yrs = span.sum() / 252
tot = netf.sum()
print("futures net bps of gross notional per year: %.0f over %.1f years (%.1f trades/yr)" % (tot / yrs, yrs, len(done) / yrs))
# daily series for Sharpe, on gross-notional capital
daily, _ = sw.daily_returns(done, dates, rs, rn, "futures")
dd = daily[span]
print("futures daily-series: ann mean %.2f%%, ann sd %.2f%%, Sharpe %.2f" % (dd.mean() * 252 * 100, dd.std() * math.sqrt(252) * 100, dd.mean() / dd.std() * math.sqrt(252)))
eq = np.cumsum(dd); print("max drawdown (bps of notional, additive): %.0f" % ((eq - np.maximum.accumulate(eq)).min() * 1e4))
# with financing correction spread per day
for lev_cap in (1.0, 0.5, 0.3):
    exc = dd.mean() * 252 / lev_cap
    print("capital = %.0f%% of gross notional: excess return %.1f%%/yr on capital, plus cash on the capital (%.1f%%) -> total %.1f%%, vol %.1f%%" % (lev_cap * 100, exc * 100, rr[span].mean() * 100, (exc + rr[span].mean()) * 100, dd.std() * math.sqrt(252) / lev_cap * 100))
# bad prints dropped
from h5_weights import _drop_bad_prints
for k in ("sbk", "ned"):
    rows_ = []
    for r in _csv.DictReader(open(f"{REPO}/data/raw/{k}.csv")):
        try:
            a = float(r["adjusted"]); d = dt.date.fromisoformat(r["date"])
        except ValueError: continue
        if a > 0 and d <= CUT: rows_.append((d, a))
    print(k, "prints dropped by the two-sided filter:", len(rows_) - len(_drop_bad_prints(rows_)))
