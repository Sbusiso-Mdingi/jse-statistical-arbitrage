"""H18 (research/PROTOCOL.md): H16's spread trade decided on the 16:00 price and filled in the closing auction.
Development data only.

  python research/h18_auction.py      # needs data/raw/{sbk,ned}_60m.csv (TradingView, local only)

H16 computes its slope, z and Engle-Granger statistic on the close and fills at that same close, which no one can
trade. H18 replaces only today's point in the 126-session window with each bank's 16:00 price (the close of the
15:00-16:00 SAST bar), so the decision is known 50 minutes before the closing auction, and fills at the official
close. Every cutoff is H16's. A session without a 16:00 price for both banks makes no decision: no entry, no
z-based exit (the 60-session limit still applies). The P&L is H16's (close to close from the fill).

Writes research/results/h18.json: H18's development record and H16's on the same sessions.
"""
import csv, json, math, sys
import datetime as dt
from collections import defaultdict
import numpy as np

sys.path.insert(0, "research"); sys.path.insert(0, "research/models"); sys.path.insert(0, "service")
from pairdata import load_pair  # noqa: E402
from app import switch as sw  # noqa: E402
from h19_total_return import raw_closes, summary, completed, shifted, START, DEV_END  # noqa: E402

sw.EXPIRIES = sw.third_thursdays(2004, 2031)
BAR = 13  # bar opening 13:00 UTC = 15:00 SAST, closing 16:00 SAST


def bar_close(name):
    out = defaultdict(dict)
    for r in csv.DictReader(open(f"data/raw/{name}_60m.csv")):
        t = dt.datetime.fromtimestamp(int(r["time"]), dt.timezone.utc)
        if t.date() <= DEV_END:
            out[t.date()][t.hour] = float(r["close"])
    return {d: h[BAR] for d, h in out.items() if BAR in h}


def stats_at_1600(x, y, x16, y16):
    """Rolling 126-session slope, z and Engle-Granger statistic with today's close replaced by its 16:00 level."""
    n = len(x)
    b, z, eg = np.full(n, np.nan), np.full(n, np.nan), np.full(n, np.nan)
    for t in range(sw.L - 1, n):
        if np.isnan(x16[t]) or np.isnan(y16[t]):
            continue
        xi = np.append(x[t - sw.L + 1:t], x16[t]); yi = np.append(y[t - sw.L + 1:t], y16[t])
        b[t], z[t], eg[t] = sw.window_stats(xi, yi)
    return b, z, eg


def main():
    d = load_pair()
    keep = [i for i, t in enumerate(d["date"]) if t <= DEV_END]
    dates = [d["date"][i] for i in keep]
    n = len(dates)
    r = {"sbk": d["r_sbk"][keep], "ned": d["r_ned"][keep]}
    lvl = {k: np.cumsum(r[k]) for k in r}
    raw = {k: raw_closes(k) for k in r}
    bars = {k: bar_close(k) for k in r}
    first_bar = max(min(bars[k]) for k in r)
    lvl16 = {}
    for k in r:
        a = np.full(n, np.nan)
        for t in range(1, n):
            day, prev = dates[t], dates[t - 1]
            if day in bars[k] and day in raw[k] and prev in raw[k]:
                c_p, a_p = raw[k][prev]; c, adj = raw[k][day]
                a[t] = lvl[k][t - 1] + math.log(bars[k][day] / c_p) + math.log((adj / c) / (a_p / c_p))  # units as the adjusted series
        lvl16[k] = a
    have = ~np.isnan(lvl16["sbk"]) & ~np.isnan(lvl16["ned"])
    span = np.array([t >= max(first_bar, START) for t in dates])
    b, z, eg = stats_at_1600(lvl["sbk"], lvl["ned"], lvl16["sbk"], lvl16["ned"])
    gate = ((eg < sw.GATE_CRIT) & span).astype(np.int8)
    h18 = sw.trades(gate, np.full(n, 0.5), b, z, copula_on=False, hold_through=True)
    rs, rn = np.expm1(r["sbk"]), np.expm1(r["ned"])
    first = dates[int(np.argmax(span))]

    def done(trs, sched="futures"):
        _, rows = sw.daily_returns(trs, dates, rs, rn, sched)
        return [x for x in completed(rows, dates) if dates[x["open"]] >= first]

    bc, zc, ec = sw.rolling(lvl["sbk"], lvl["ned"])
    h16 = sw.trades(((ec < sw.GATE_CRIT) & span).astype(np.int8), np.full(n, 0.5), bc, zc, copula_on=False, hold_through=True)
    rows = done(h18)
    dif = np.abs(np.array([bars["sbk"].get(t, np.nan) / raw["sbk"][t][0] - 1 for t in dates if t in raw["sbk"]]))
    out = {"protocol": "research/PROTOCOL.md, H18", "development": {"from": first.isoformat(), "to": DEV_END.isoformat(),
                                                                     "sessions": int(span.sum()), "sessions_without_1600": int((span & ~have).sum())},
           "h18": {s: summary([x["net"] for x in done(h18, s)]) for s in ("futures", "cash")},
           "h16_same_span": {s: summary([x["net"] for x in done(h16, s)]) for s in ("futures", "cash")},
           "h16_same_span_next_close": summary([x["net"] for x in done(shifted(h16, 1, n))]),
           "h18_next_close": summary([x["net"] for x in done(shifted(h18, 1, n))]),
           "agreement": {"z_corr": round(float(np.corrcoef(z[have & span & ~np.isnan(zc)], zc[have & span & ~np.isnan(zc)])[0, 1]), 3),
                         "gate_same": round(float(((eg < sw.GATE_CRIT) == (ec < sw.GATE_CRIT))[have & span].mean()), 3),
                         "same_entry_sessions": len({x["open"] for x in rows} & {x["open"] for x in done(h16)})},
           "sbk_1600_vs_close_median_abs": round(float(np.nanmedian(dif)), 4)}
    out["h18"]["trade_nets_bps"] = [round(x["net"] * 1e4, 1) for x in rows]
    out["h18"]["trade_opens"] = [dates[x["open"]].isoformat() for x in rows]
    out["h18"]["trade_closes"] = [dates[x["close"]].isoformat() for x in rows]
    json.dump(out, open("research/results/h18.json", "w"), indent=1)
    print(json.dumps({k: ({a: b_ for a, b_ in v.items() if not a.startswith("trade_")} if isinstance(v, dict) else v) for k, v in out.items()}, indent=1))


if __name__ == "__main__":
    main()
