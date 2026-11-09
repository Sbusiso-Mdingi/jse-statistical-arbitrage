"""Descriptive study of the 60-minute SBK and NED bars (TradingView export, not redistributed).

Design period only (2010 to 2019), nothing selected. Two questions: does realised correlation
from intraday returns move in regimes the daily copula cannot see, and did the daily reversal
the strategies rely on move inside the day? Writes research/results/hourly_study.json.
"""
import csv, json, math, datetime as dt
from collections import defaultdict
import numpy as np
from scipy import stats as st

def load(f):
    out = defaultdict(dict)
    for r in csv.DictReader(open(f)):
        t = dt.datetime.utcfromtimestamp(int(r["time"]))
        out[t.date()][t.hour] = float(r["close"])
    return out
S, N = load("data/raw/sbk_60m.csv"), load("data/raw/ned_60m.csv")
days = sorted(d for d in S if d in N and len(S[d]) == 8 and len(N[d]) == 8 and dt.date(2010, 1, 1) <= d < dt.date(2020, 1, 1))
print(len(days), "full design days with 8 bars in both")
H = [7, 8, 9, 10, 11, 12, 13, 14]  # UTC bar close hours: 09:00 to 16:00 SAST

def intraday(x):  # 7 within-day hourly log returns plus the overnight return from the previous close
    return np.array([[math.log(x[d][H[i + 1]] / x[d][H[i]]) for i in range(7)] for d in days])
def overnight(x):
    return np.array([math.log(x[days[i]][H[0]] / x[days[i - 1]][H[-1]]) if i else 0.0 for i in range(len(days))])
rs, rn = intraday(S), intraday(N)
os_, on_ = overnight(S), overnight(N)
daily_s = rs.sum(1) + os_; daily_n = rn.sum(1) + on_

out = {}
# 1. realised correlation from intraday returns, by month, against the yearly copula correlation and the daily-return correlation
months = sorted({d.strftime("%Y-%m") for d in days})
mi = np.array([months.index(d.strftime("%Y-%m")) for d in days])
rc = []
for k, m in enumerate(months):
    sel = mi == k
    a, b = rs[sel].ravel(), rn[sel].ravel()
    rc.append(float(np.corrcoef(a, b)[0, 1]))
rc = np.array(rc)
yrs = sorted({m[:4] for m in months})
print("\nyear  realised intraday corr (mean of months, min, max)   daily-return corr")
rows = []
for y in yrs:
    sel = np.array([m[:4] == y for m in months]); dsel = np.array([d.year == int(y) for d in days])
    dc = float(np.corrcoef(daily_s[dsel], daily_n[dsel])[0, 1])
    rows.append({"year": int(y), "rc_mean": float(rc[sel].mean()), "rc_min": float(rc[sel].min()), "rc_max": float(rc[sel].max()), "daily_corr": dc})
    print(f"{y}   {rc[sel].mean():.3f}  ({rc[sel].min():.3f} to {rc[sel].max():.3f})                        {dc:.3f}")
out["realised_corr_by_year"] = rows
# persistence: does this month's realised correlation predict next month's? (what a tracking parameter relies on)
print("month-to-month autocorrelation of realised intraday correlation:", round(float(np.corrcoef(rc[:-1], rc[1:])[0, 1]), 3))
out["rc_autocorr"] = float(np.corrcoef(rc[:-1], rc[1:])[0, 1])
# a crude regime view: is the distribution of monthly realised correlation bimodal? (dip test proxy: histogram)
hist, edges = np.histogram(rc, bins=np.arange(0.3, 1.0001, 0.05))
print("histogram of monthly realised correlation:", {f"{edges[i]:.2f}": int(hist[i]) for i in range(len(hist))})
out["rc_hist"] = {f"{edges[i]:.2f}": int(hist[i]) for i in range(len(hist))}

# 2. does the realised correlation forecast the realised variance of the spread next month (what the copula gets wrong)?
spread_d = daily_s - daily_n
sv = np.array([float(np.std(spread_d[mi == k])) for k in range(len(months))])
print("corr(realised corr this month, spread vol next month):", round(float(np.corrcoef(rc[:-1], sv[1:])[0, 1]), 3),
      " vs corr(spread vol this month, next):", round(float(np.corrcoef(sv[:-1], sv[1:])[0, 1]), 3))

# 3. intraday reversal: after a large divergence over the first k hours, what does the spread do over the rest of the day and the next day?
print("\nintraday reversal of the SBK minus NED spread, design. Divergence = spread move in the window; 'rest' = remaining hours to close; 'next' = next full day")
spread_h = rs - rn  # 7 hourly spread returns
rows = []
for k in (1, 2, 3, 4):
    first = spread_h[:, :k].sum(1)
    rest = spread_h[:, k:].sum(1)
    nxt = np.concatenate([spread_d[1:], [np.nan]])
    thr = np.quantile(np.abs(first), 0.9)
    big = np.abs(first) > thr
    sign = np.sign(first[big])
    r_rest = (sign * rest[big]) * 1e4; r_next = (sign * nxt[big])[~np.isnan(nxt[big])] * 1e4
    rows.append({"hours": k, "n": int(big.sum()), "rest_of_day_bps": float(r_rest.mean()), "rest_t": float(r_rest.mean() / r_rest.std(ddof=1) * math.sqrt(len(r_rest))),
                 "next_day_bps": float(r_next.mean()), "next_t": float(r_next.mean() / r_next.std(ddof=1) * math.sqrt(len(r_next)))})
    r = rows[-1]
    print(f"  first {k}h beyond q90: n {r['n']:4d}  continuation rest of day {r['rest_of_day_bps']:6.1f} bps (t {r['rest_t']:5.2f})  next day {r['next_day_bps']:6.1f} bps (t {r['next_t']:5.2f})")
out["intraday_reversal"] = rows
# the same split by half: 2010-14 vs 2015-19
for lo, hi in ((2010, 2015), (2015, 2020)):
    sel = np.array([lo <= d.year < hi for d in days])
    first = spread_h[sel, :2].sum(1); rest = spread_h[sel, 2:].sum(1)
    thr = np.quantile(np.abs(first), 0.9); big = np.abs(first) > thr; sign = np.sign(first[big])
    x = sign * rest[big] * 1e4
    print(f"  {lo}-{hi-1}: first 2h beyond q90, rest of day {x.mean():6.1f} bps (t {x.mean()/x.std(ddof=1)*math.sqrt(len(x)):5.2f}, n {len(x)})")
# 4. overnight vs intraday share of daily spread variance
print("\nshare of daily spread variance that is overnight:", round(float(np.var(os_ - on_) / np.var(spread_d)), 3))
out["overnight_share"] = float(np.var(os_ - on_) / np.var(spread_d))
json.dump(out, open("research/results/hourly_study.json", "w"), indent=1)
