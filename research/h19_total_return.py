"""H19 (research/PROTOCOL.md): H16's spread trade on dividend-correct prices. Development data only.

  python research/h19_total_return.py

Yahoo's "adjusted" closes for these two banks carry about a hundredth of each dividend (the dividend in cents
applied as if in rand), so the frozen rules read what is in effect a price-only series. This builds a separate
total-return series from Yahoo's raw closes and its dividend events, both in cents: on each session
r = log((close_t + dividend_t) / close_{t-1}), on the frozen rules' own sessions (bad prints dropped as everywhere).
Nothing the frozen rules read is changed.

Writes data/pair_dividends.json (the per-session correction from the frozen series to the total-return series,
nonzero only on ex-dividend sessions; the service adds it to the frozen returns) and research/results/h19.json
(H19's development record, and the reporting figures for the frozen H16 on the same record).
"""
import csv, json, math, sys
import datetime as dt
import numpy as np

sys.path.insert(0, "research"); sys.path.insert(0, "research/models"); sys.path.insert(0, "service")
from pairdata import load_pair  # noqa: E402
from app import switch as sw  # noqa: E402

sw.EXPIRIES = sw.third_thursdays(2004, 2031)  # trades from 2006 need earlier expiries than the service does
DEV_END = dt.date(2026, 3, 31)
START = dt.date(2006, 1, 3)
ERAS = [("2006-01-01", "2013-01-01"), ("2013-01-01", "2020-01-01"), ("2020-01-01", "2026-04-01")]


def raw_closes(name):
    out = {}
    for r in csv.DictReader(open(f"data/raw/{name}.csv")):
        try:
            c, a = float(r["close"]), float(r["adjusted"])
        except ValueError:
            continue
        if c > 0 and a > 0:
            out[dt.date.fromisoformat(r["date"])] = (c, a)
    return out


def dividends():
    out = {"sbk": {}, "ned": {}}
    for r in csv.DictReader(open("data/raw/h15_div.csv")):
        out[r["bank"]][dt.date.fromisoformat(r["ex_date"])] = float(r["amount"])
    return out


def total_return(dates, raw, div):
    """Total-return log returns on the given sessions, and the correction from the frozen (adjusted) returns."""
    n = len(dates)
    tr, corr, ex = np.zeros(n), np.zeros(n), []
    prev = None
    for i, d in enumerate(dates):
        c, a = raw[d]
        if i == 0:
            prev = (c, a); continue
        D = div.get(d, 0.0)
        tr[i] = math.log((c + D) / prev[0])
        corr[i] = tr[i] - math.log(a / prev[1])
        if D:
            ex.append({"date": d.isoformat(), "amount": D, "yield": D / prev[0],
                       "yahoo_step": (prev[1] / prev[0]) / (a / c)})
        prev = (c, a)
    return tr, corr, ex


def gate_trades(x, y, dev):
    b, z, eg = sw.rolling(x, y)
    gate = ((eg < sw.GATE_CRIT) & dev).astype(np.int8)
    return sw.trades(gate, np.full(len(x), 0.5), b, z, copula_on=False, hold_through=True), b, z, eg


def completed(rows, dates):
    return [r for r in rows if r["complete"] and dates[r["open"]] >= START and dates[r["close"]] <= DEV_END]


def summary(v):
    v = np.asarray(v) * 1e4
    if not len(v):
        return {"trades": 0}
    return {"trades": int(len(v)), "mean_bps": round(float(v.mean()), 1), "median_bps": round(float(np.median(v)), 1),
            "t": round(float(v.mean() / (v.std(ddof=1) / math.sqrt(len(v)))), 2) if len(v) > 2 else None,
            "win": round(float((v > 0).mean()), 2)}


def score(trs, dates, rs, rn, sched="futures"):
    _, rows = sw.daily_returns(trs, dates, rs, rn, sched)
    return completed(rows, dates)


def shifted(trs, k, n):
    """The same trades filled k sessions late at both ends."""
    out = []
    for t in trs:
        if t["close"] is None or t["close"] + k >= n:
            continue
        out.append(dict(t, open=t["open"] + k, close=t["close"] + k))
    return out


def fixed_contracts(trs, dates, rs, rn, sched):
    """Each trade held as fixed contracts from its entry (legs drift with prices) instead of the engine's
    constant weights. Costs as the engine charges them."""
    out = []
    for t in trs:
        if t["close"] is None:
            continue
        o, c = t["open"], t["close"]
        g = t["w_sbk"] * (np.prod(1 + rs[o + 1:c + 1]) - 1) + t["w_ned"] * (np.prod(1 + rn[o + 1:c + 1]) - 1)
        cost = sw.trade_costs(t, dates, sched).sum()
        out.append({**t, "net": float(g - cost), "complete": True})
    return out


def main():
    d = load_pair()
    keep = [i for i, t in enumerate(d["date"]) if t <= DEV_END]
    dates = [d["date"][i] for i in keep]
    n = len(dates)
    r_adj = {"sbk": d["r_sbk"][keep], "ned": d["r_ned"][keep]}
    # load_pair drops its first session's return; the raw closes need the session before it.
    all_days = sorted(set(raw_closes("sbk")) & set(raw_closes("ned")))
    first_prev = max(t for t in all_days if t < dates[0])
    raw = {k: raw_closes(k) for k in ("sbk", "ned")}
    div = dividends()
    seq = [first_prev] + dates
    tr, corr, ex = {}, {}, {}
    for k in ("sbk", "ned"):
        a, c, e = total_return(seq, raw[k], div[k])
        tr[k], corr[k], ex[k] = a[1:], c[1:], e
        # The correction must be zero away from ex-dividend sessions: Yahoo's close and adjusted differ only there.
        exd = {x["date"] for x in e}
        off = [abs(corr[k][i]) for i, t in enumerate(dates) if t.isoformat() not in exd]
        assert max(off) < 1e-5, f"{k}: adjusted and close differ off ex-dates by {max(off)}"  # rounding in the stored adjusted
        assert np.allclose(tr[k] - corr[k], r_adj[k], atol=1e-12)
    dev = np.array([t >= START for t in dates])
    rs, rn = np.expm1(r_adj["sbk"]), np.expm1(r_adj["ned"])
    ts, tn = np.expm1(tr["sbk"]), np.expm1(tr["ned"])
    exdays = {i for i, t in enumerate(dates) for k in ("sbk", "ned") if t.isoformat() in {x["date"] for x in ex[k]}}

    # H16 as frozen (adjusted levels, price-only P&L) and its reporting figures.
    h16, _, _, _ = gate_trades(np.cumsum(r_adj["sbk"]), np.cumsum(r_adj["ned"]), dev)
    rec = {"h16": {"as_scored": {s: summary([r["net"] for r in score(h16, dates, rs, rn, s)]) for s in ("futures", "cash")}}}
    rec["h16"]["next_close_fill"] = summary([r["net"] for r in score(shifted(h16, 1, n), dates, rs, rn)])
    rec["h16"]["with_dividends"] = summary([r["net"] for r in score(h16, dates, ts, tn)])
    rec["h16"]["fixed_contracts"] = summary([r["net"] for r in fixed_contracts(h16, dates, rs, rn, "futures") if dates[r["open"]] >= START and dates[r["close"]] <= DEV_END])
    assert rec["h16"]["as_scored"]["futures"]["trades"] == 79 and abs(rec["h16"]["as_scored"]["futures"]["mean_bps"] - 91.1) < 0.05

    # H19: the same rule on total-return levels, P&L on total returns.
    h19, b, z, eg = gate_trades(np.cumsum(tr["sbk"]), np.cumsum(tr["ned"]), dev)
    rows = score(h19, dates, ts, tn)
    v = np.array([r["net"] for r in rows])
    rec["h19"] = {s: summary([r["net"] for r in score(h19, dates, ts, tn, s)]) for s in ("futures", "cash")}
    rec["h19"]["eras"] = [{"from": a, "to": c, **summary([r["net"] for r in rows if a <= dates[r["open"]].isoformat() < c])} for a, c in ERAS]
    rec["h19"]["next_close_fill"] = summary([r["net"] for r in score(shifted(h19, 1, n), dates, ts, tn)])
    rec["h19"]["price_only_pnl"] = summary([r["net"] for r in score(h19, dates, rs, rn)])
    rec["h19"]["same_entries_as_h16"] = len({r["open"] for r in rows} & {r["open"] for r in score(h16, dates, rs, rn)})
    rec["h19"]["gate_share"] = round(float(((eg < sw.GATE_CRIT) & dev)[dev].mean()), 3)
    rec["h19"]["trades_per_year"] = round(len(rows) / ((DEV_END - START).days / 365.25), 1)
    rec["h19"]["trade_nets_bps"] = [round(x * 1e4, 1) for x in v]
    rec["h19"]["trade_opens"] = [dates[r["open"]].isoformat() for r in rows]
    rec["h19"]["trade_closes"] = [dates[r["close"]].isoformat() for r in rows]
    rec["h19"]["latest"] = {"date": dates[-1].isoformat(), "eg126": round(float(eg[-1]), 3), "z126": round(float(z[-1]), 3)}

    # Copula-rule signals on ex-dividend sessions (reporting).
    hh = {r["date"]: float(r["h"]) for r in csv.DictReader(open("research/results/copulas_py.csv")) if r["model"] == "gas_t"}
    sig = [i for i, t in enumerate(dates) if t.isoformat() in hh and abs(hh[t.isoformat()] - 0.5) > sw.LEVEL]
    on_h = [i for i in exdays if dates[i].isoformat() in hh]
    rec["copula_ex_dividend"] = {"ex_sessions": len(on_h), "fired": sum(1 for i in on_h if abs(hh[dates[i].isoformat()] - 0.5) > sw.LEVEL),
                                 "signals": len(sig), "signals_on_ex_sessions": sum(1 for i in sig if i in exdays), "expected_rate": 0.10}
    rec["yahoo_adjustment"] = {k: {"ex_dates": len(ex[k]), "median_yield": round(float(np.median([x["yield"] for x in ex[k]])), 4),
                                   "median_step_over_yield": round(float(np.median([(x["yahoo_step"] - 1) / x["yield"] for x in ex[k]])), 4)}
                               for k in ("sbk", "ned")}
    rec["development"] = {"from": START.isoformat(), "to": DEV_END.isoformat(), "sessions": n}
    json.dump({"protocol": "research/PROTOCOL.md, H19", **rec}, open("research/results/h19.json", "w"), indent=1)

    # The service's correction: from the frozen returns to total returns, by ex-dividend session, to 31 March 2026.
    # Later sessions are corrected live from Yahoo's dividend events (service/app/data.py).
    json.dump({"generated_from": "research/h19_total_return.py", "to": DEV_END.isoformat(),
               "units": "dividend and closes in cents; correction is added to the frozen log return",
               "corrections": {k: {x["date"]: round(float(corr[k][dates.index(dt.date.fromisoformat(x["date"]))]), 10) for x in ex[k]} for k in ("sbk", "ned")},
               "events": ex}, open("data/pair_dividends.json", "w"), indent=1)
    for k, val in rec.items():
        if k in ("development",):
            continue
        print(k, json.dumps({a: b for a, b in val.items() if a not in ("trade_nets_bps", "trade_opens", "trade_closes")} if isinstance(val, dict) else val))


if __name__ == "__main__":
    main()
