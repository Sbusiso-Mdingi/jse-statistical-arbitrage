from common import *
import json
dates, ls, ln = load(); n = len(dates)
x, y = np.cumsum(ls), np.cumsum(ln)
rs, rn = np.expm1(ls), np.expm1(ln)
raw = {k: daily_raw(k) for k in ("sbk", "ned")}
B = {k: bars(k) for k in ("sbk", "ned")}
# hour coverage and last-bar vs official close
hrs = collections = {}
import collections
for k in ("sbk", "ned"):
    c = collections.Counter(h for d in B[k] for h in B[k][d]); print(k, "bar hours", sorted(c.items()))
    m = [abs(B[k][d][14][1] / raw[k][d][0] - 1) for d in B[k] if 14 in B[k][d] and d in raw[k]]
    print(k, "last bar close vs daily close: share exact %.3f, median abs %.5f" % (np.mean(np.array(m) < 1e-9), np.median(m)))

def intraday_level(k, hour, field):
    lvl = np.full(n, np.nan)
    base = x if k == "sbk" else y
    for t, d in enumerate(dates):
        bb = B[k].get(d, {})
        if hour in bb and d in raw[k]:
            lvl[t] = base[t] + math.log(bb[hour][field] / raw[k][d][0])
    return lvl
x16, y16 = intraday_level("sbk", 13, 1), intraday_level("ned", 13, 1)
xo, yo = intraday_level("sbk", 7, 0), intraday_level("ned", 7, 0)
first_bar = next(t for t in range(n) if not np.isnan(x16[t]) and not np.isnan(y16[t]))
print("first session with 16:00 bars", dates[first_bar])
cov = (~np.isnan(x16) & ~np.isnan(y16))[first_bar:]
print("16:00 coverage after first bar", cov.mean(), "open coverage", (~np.isnan(xo) & ~np.isnan(yo))[first_bar:].mean())

trs, b, z, eg = h16_trades(dates, x, y)
done = [t for t in trs if t["close"] is not None and dates[t["open"]] >= dt.date(2006, 1, 1)]

def costs_of(tr, sched):
    return sw.trade_costs(tr, dates, sched).sum() if sched else 0.0

def gross_engine(tr, rr_s=rs, rr_n=rn):
    o, c = tr["open"], tr["close"]
    return float(tr["w_sbk"] * rr_s[o + 1:c + 1].sum() + tr["w_ned"] * rr_n[o + 1:c + 1].sum())

def gross_bh(tr, lx, ly, o_lvl=None, c_lvl=None):
    """buy and hold from fill level to exit level (log levels)."""
    o, c = tr["open"], tr["close"]
    ex0, ey0 = (x[o], y[o]) if o_lvl is None else o_lvl
    ex1, ey1 = (x[c], y[c]) if c_lvl is None else c_lvl
    return float(tr["w_sbk"] * (math.exp(ex1 - ex0) - 1) + tr["w_ned"] * (math.exp(ey1 - ey0) - 1))

def report(label, rows):
    out = {}
    for s in ("gross", "futures", "cash"):
        v = [g - (cf if s == "futures" else cc if s == "cash" else 0) for g, cf, cc in rows]
        out[s] = summ(v)
    print(f"{label:58s}", out); return out

R = {}
base = [(gross_engine(t), costs_of(t, "futures"), costs_of(t, "cash")) for t in done]
R["base_engine"] = report("base: signal close, fill same close (engine)", base)
R["base_bh"] = report("base, buy-and-hold legs instead of daily-rebalanced", [(gross_bh(t, x, y), f, c) for t, (_, f, c) in zip(done, base)])
# next close
shift = lambda t, k: {**t, "open": t["open"] + k, "close": t["close"] + k}
nc = [shift(t, 1) for t in done if t["close"] + 1 < n]
R["next_close"] = report("fill at the next close (signal t, fill t+1)", [(gross_engine(t), costs_of(t, "futures"), costs_of(t, "cash")) for t in nc])
R["next_close_2"] = report("fill two closes later", [(gross_engine(t), costs_of(t, "futures"), costs_of(t, "cash")) for t in [shift(t, 2) for t in done if t["close"] + 2 < n]])
# subsample with bars
sub = [t for t in done if t["open"] >= first_bar + 1 and t["close"] + 1 < n]
print("trades in the bar era:", len(sub), "from", dates[sub[0]["open"]])
R["bar_era_base"] = report("bar era, base (engine)", [(gross_engine(t), costs_of(t, "futures"), costs_of(t, "cash")) for t in sub])
R["bar_era_base_bh"] = report("bar era, base (buy-and-hold)", [(gross_bh(t, x, y), costs_of(t, "futures"), costs_of(t, "cash")) for t in sub])
def lvl(lx, ly, t, fx=x, fy=y):
    a, bb = lx[t], ly[t]
    return (fx[t] if np.isnan(a) else a, fy[t] if np.isnan(bb) else bb)
no = [(t, gross_bh(t, x, y, o_lvl=lvl(xo, yo, t["open"] + 1), c_lvl=lvl(xo, yo, t["close"] + 1))) for t in sub]
R["next_open"] = report("bar era, fill at the next open (buy-and-hold)", [(g, costs_of(shift(t, 1), "futures"), costs_of(shift(t, 1), "cash")) for t, g in no])
p16 = [(t, gross_bh(t, x, y, o_lvl=lvl(x16, y16, t["open"]), c_lvl=lvl(x16, y16, t["close"]))) for t in sub]
R["close_signal_fill_16"] = report("bar era, close signal but filled at 16:00 price (illustrative)", [(g, costs_of(t, "futures"), costs_of(t, "cash")) for t, g in p16])

# 16:00 signal: replace today's close by the 16:00 price in the window
b16, z16, eg16 = np.full(n, np.nan), np.full(n, np.nan), np.full(n, np.nan)
miss = 0
for t in range(max(sw.L - 1, first_bar), n):
    xi, yi = x[t - sw.L + 1:t + 1].copy(), y[t - sw.L + 1:t + 1].copy()
    if np.isnan(x16[t]) or np.isnan(y16[t]):
        miss += 1  # no bar: fall back to the close
    else:
        xi[-1], yi[-1] = x16[t], y16[t]
    b16[t], z16[t], eg16[t] = sw.window_stats(xi, yi)
print("sessions without 16:00 bars (fall back to close):", miss)
print("corr z16 vs z (bar era):", np.corrcoef(z16[first_bar:], z[first_bar:])[0, 1], " gate agreement:", np.mean((eg16[first_bar:] < -2.8) == (eg[first_bar:] < -2.8)))
mask_pre = np.array([i < first_bar for i in range(n)])
b16[mask_pre], z16[mask_pre], eg16[mask_pre] = np.nan, np.nan, np.inf
trs16, *_ = h16_trades(dates, x, y, b=b16, z=z16, eg=eg16)
d16 = [t for t in trs16 if t["close"] is not None and t["open"] >= first_bar + 1]
R["sig16_fill_close"] = report("bar era, 16:00 signal, fill in the closing auction", [(gross_engine(t), costs_of(t, "futures"), costs_of(t, "cash")) for t in d16])
R["sig16_fill_close_bh"] = report("bar era, 16:00 signal, closing auction (buy-and-hold)", [(gross_bh(t, x, y), costs_of(t, "futures"), costs_of(t, "cash")) for t in d16])
R["sig16_fill_16"] = report("bar era, 16:00 signal, fill at the 16:00 price (bh)", [(gross_bh(t, x, y, o_lvl=lvl(x16, y16, t["open"]), c_lvl=lvl(x16, y16, t["close"])), costs_of(t, "futures"), costs_of(t, "cash")) for t in d16])
R["sig16_fill_nextopen"] = report("bar era, 16:00 signal, fill next open (bh)", [(gross_bh(t, x, y, o_lvl=lvl(xo, yo, t["open"] + 1), c_lvl=lvl(xo, yo, t["close"] + 1)), costs_of(shift(t,1), "futures"), costs_of(shift(t,1), "cash")) for t in d16 if t["close"] + 1 < n])
# overlap of trade sets
so = {t["open"] for t in sub}; s16 = {t["open"] for t in d16}
print("entry dates shared exactly:", len(so & s16), "of", len(sub), "and", len(d16), "; within 1 session:", sum(any(abs(a - c) <= 1 for c in s16) for a in so))
# entry-day and exit-day components (where the gross comes from)
day1 = [t["w_sbk"] * rs[t["open"] + 1] + t["w_ned"] * rn[t["open"] + 1] for t in done]
dayx = [t["w_sbk"] * rs[t["close"]] + t["w_ned"] * rn[t["close"]] for t in done]
print("mean first-day gross bps %.1f, exit-day gross bps %.1f" % (np.mean(day1) * 1e4, np.mean(dayx) * 1e4))
ov = [t["w_sbk"] * (math.exp(lvl(xo, yo, t["open"] + 1)[0] - x[t["open"]]) - 1) + t["w_ned"] * (math.exp(lvl(xo, yo, t["open"] + 1)[1] - y[t["open"]]) - 1) for t in sub]
print("mean overnight (close->next open) gross on entry, bps %.1f" % (np.mean(ov) * 1e4))
json.dump(R, open("/tmp/jse-review/execution/timing.json", "w"), indent=1)
