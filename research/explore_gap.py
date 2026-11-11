"""Exploration on development data (all sessions to 31 March 2026; research/PROTOCOL.md, H15's rule change).

  python research/explore_gap.py

Not a test. Forecasts of whether the frozen 126-session gap closes (H15's label), out of fold on purged folds and
walk-forward, spread trades gated on them and on plain Engle-Granger cutoffs, other windows and entries, and a
sector-hedged spread (each bank less its FirstRand and Absa beta), at the institutional schedules in
service/app/switch.py. Every specification tried is listed in research/results/explore_gap.json.
"""
import json, math, sys
import datetime as dt
import numpy as np
from sklearn.linear_model import LogisticRegression

sys.path.insert(0, "research"); sys.path.insert(0, "research/models"); sys.path.insert(0, "service")
from pairdata import load_pair  # noqa: E402
from h5_weights import _read_px  # noqa: E402
from app import switch as sw  # noqa: E402
import h15_forecast as h15  # noqa: E402

sw.EXPIRIES = sw.third_thursdays(2004, 2031)  # trades from 2006 need earlier expiries than the service does
N, ENTRY, STOP = 60, 1.5, 4.0
ERAS = [("2006-01-01", "2013-01-01"), ("2013-01-01", "2020-01-01"), ("2020-01-01", "2026-04-01")]


def wstats(x, y, L):
    n = len(x)
    out = {k: np.full(n, np.nan) for k in ("a", "b", "s", "z", "eg", "phi")}
    for t in range(L - 1, n):
        xi, yi = x[t - L + 1:t + 1], y[t - L + 1:t + 1]
        b, z, eg = sw.window_stats(xi, yi)
        a = yi.mean() - b * xi.mean()
        u = yi - a - b * xi
        out["a"][t], out["b"][t], out["z"][t], out["eg"][t] = a, b, z, eg
        out["s"][t] = math.sqrt(u @ u / (L - 2))
        out["phi"][t] = float(u[1:] @ u[:-1] / (u[:-1] @ u[:-1]))
    return out


def oof_probs(feats, lab, dev, dates, folds=5):
    n = len(lab)
    p = np.full(n, np.nan)
    idx = np.flatnonzero(dev)
    X = np.column_stack(feats)
    for test in np.array_split(idx, folds):
        lo, hi = test[0], test[-1]
        tr = dev.copy(); tr[max(lo - N, 0):min(hi + N + 1, n)] = False
        tr &= ~np.isnan(lab) & ~np.isnan(X).any(1)
        te = np.zeros(n, bool); te[test] = True; te &= ~np.isnan(lab) & ~np.isnan(X).any(1)
        mu, sd = X[tr].mean(0), X[tr].std(0); sd[sd == 0] = 1
        m = LogisticRegression(C=1.0, max_iter=1000).fit((X[tr] - mu) / sd, lab[tr])
        p[te] = m.predict_proba((X[te] - mu) / sd)[:, 1]
    return p


def fixed_line_trades(x, y, w, gate, hold=N, stop=STOP, entry=ENTRY, last=None):
    """One spread trade at a time. Open on a close where gate holds and |z| > entry; the line (a, b, s) is fixed at
    entry, and the trade closes when the gap reaches zero, passes the stop, or after `hold` sessions."""
    n = len(x) if last is None else last + 1
    out = []; t = 0
    while t < n:
        if gate[t] and not np.isnan(w["z"][t]) and abs(w["z"][t]) > entry:
            a, b, s, z0 = w["a"][t], w["b"][t], w["s"][t], w["z"][t]
            side = -1 if z0 > 0 else 1
            k = abs(b)
            close = None
            for j in range(t + 1, min(t + hold, n - 1) + 1):
                g = (y[j] - a - b * x[j]) / s
                if g * z0 <= 0 or abs(g) > stop or j == t + hold:
                    close = j; break
            out.append({"open": t, "close": close, "method": "spread", "side": side, "w_sbk": -side * k / (1 + k), "w_ned": side / (1 + k)})
            if close is None:
                break
            t = close + 1
        else:
            t += 1
    return out


def evaluate(trs, dates, rs, rn, lo="2006-01-01", hi="2026-04-01"):
    res = {}
    for sched in ("futures", "cash"):
        _, rows = sw.daily_returns(trs, dates, rs, rn, sched)
        v = np.array([r["net"] for r in rows if r["complete"] and lo <= dates[r["open"]].isoformat() < hi and dates[r["close"]] <= dt.date(2026, 3, 31)]) * 1e4
        res[sched] = {"trades": int(len(v)), "per_trade_bps": round(float(v.mean()), 1) if len(v) else None,
                      "t": round(float(v.mean() / (v.std(ddof=1) / math.sqrt(len(v)))), 2) if len(v) > 2 else None}
        if sched == "futures":
            res["eras"] = []
            for a, b in ERAS:
                vv = np.array([r["net"] for r in rows if r["complete"] and a <= dates[r["open"]].isoformat() < b and dates[r["close"]] <= dt.date(2026, 3, 31)]) * 1e4
                res["eras"].append([int(len(vv)), round(float(vv.mean()), 1) if len(vv) else None])
    return res


def _rolling_trades(gate, dev, w, entry=ENTRY):
    """H4b's trade (rolling z exits, held through the gate's end) on closes where the gate holds."""
    sw.ENTRY = entry
    try:
        return sw.trades((gate & dev).astype(np.int8), np.full(len(dev), 0.5), w["b"], w["z"], copula_on=False, hold_through=True)
    finally:
        sw.ENTRY = ENTRY


def detail(trs, dates, rs, rn):
    _, rows = sw.daily_returns(trs, dates, rs, rn, "futures")
    rows = [r for r in rows if r["complete"] and dates[r["close"]] <= dt.date(2026, 3, 31)]
    v = np.sort(np.array([r["net"] for r in rows]) * 1e4)
    return {"median_bps": round(float(np.median(v)), 1), "win": round(float((v > 0).mean()), 2), "drop_top3_bps": round(float(v[:-3].mean()), 1),
            "mean_days": round(float(np.mean([r["close"] - r["open"] for r in rows])), 1)}


def _logret(name, dates):
    px = dict(_read_px(name)); out = np.zeros(len(dates)); prev = None
    for i, t in enumerate(dates):
        if t in px:
            if prev is not None:
                out[i] = math.log(px[t] / prev)
            prev = px[t]
    return out


def _own(r, sec, L=126):
    o = np.zeros(len(r))
    for t in range(L, len(r)):
        rr, ss = r[t - L:t], sec[t - L:t]
        o[t] = r[t] - (rr @ ss) / (ss @ ss) * sec[t]
    return np.cumsum(o)


def main():
    d = load_pair()
    dates = d["date"]; n = len(dates)
    x, y = np.cumsum(d["r_sbk"]), np.cumsum(d["r_ned"])
    rs, rn = np.expm1(d["r_sbk"]), np.expm1(d["r_ned"])
    W = {L: wstats(x, y, L) for L in (63, 126, 252)}
    w = W[126]
    lab, _ = h15.labels(x, y, w["a"], w["b"], w["s"], w["z"])
    last_dev = max(i for i in range(n) if dates[i] <= dt.date(2026, 3, 31))
    dev = np.array([dates[i] >= dt.date(2006, 1, 3) and i + N <= last_dev for i in range(n)])
    ev = dev & ~np.isnan(lab)
    log = {"label_base_rate": round(float(lab[ev].mean()), 3), "events": int(ev.sum()), "forecasts": {}, "trades": {}}

    specs = {
        "absz": [np.abs(w["z"])],
        "absz_eg126": [np.abs(w["z"]), w["eg"]],
        "absz_eg126_phi": [np.abs(w["z"]), w["eg"], w["phi"]],
        "absz_eg_multi": [np.abs(w["z"]), W[63]["eg"], w["eg"], W[252]["eg"]],
    }
    P = {}
    for k, f in specs.items():
        p = oof_probs(f, lab, dev, dates)
        P[k] = p
        ok = ev & ~np.isnan(p)
        log["forecasts"][k] = {"log_score": round(float(h15.logscore(p[ok], lab[ok]).mean()), 4), "brier": round(float(((p[ok] - lab[ok]) ** 2).mean()), 4)}
        if k != "absz":
            log["forecasts"][k]["vs_absz"] = h15.compare(p[ok], P["absz"][ok], lab[ok])
    print(json.dumps(log["forecasts"], indent=1))

    # Trades: fixed-line exits, gated on each forecast at thresholds; and simple gates for reference.
    always = np.ones(n, bool)
    gates = {"always": always, "eg126_below_crit": w["eg"] < sw.EG_CRIT}
    for k in ("absz_eg126", "absz_eg_multi"):
        for th in (0.5, 0.55, 0.6, 0.65, 0.7):
            gates[f"p_{k}>{th}"] = np.nan_to_num(P[k], nan=0) > th
    for g, m in gates.items():
        trs = fixed_line_trades(x, y, w, m & dev)
        log["trades"][f"fixed|{g}"] = evaluate(trs, dates, rs, rn)
        # H4b's exits (rolling z) for the same gate
        mode = (m & dev).astype(np.int8)
        trs2 = sw.trades(mode, np.full(n, 0.5), w["b"], w["z"], copula_on=False, hold_through=True)
        log["trades"][f"rolling|{g}"] = evaluate(trs2, dates, rs, rn)
    # Walk-forward: refit each 1 January on labels resolved before it, |z| and eg126.
    X = np.column_stack([np.abs(w["z"]), w["eg"]])
    p = np.full(n, np.nan)
    first = int(np.argmax(dev))
    for yr in range(2009, 2027):
        s0 = next(i for i in range(n) if dates[i].year == yr)
        s1 = next((i for i in range(n) if dates[i].year == yr + 1), n)
        tr = ev.copy(); tr[s0 - N:] = False; tr[:first] = False
        m = LogisticRegression(C=1.0, max_iter=1000).fit(X[tr], lab[tr])
        te = np.arange(s0, s1); g = ~np.isnan(X[te]).any(1)
        p[te[g]] = m.predict_proba(X[te[g]])[:, 1]
    full = ev & ~np.isnan(X).any(1)
    m = LogisticRegression(C=1.0, max_iter=1000).fit(X[full], lab[full])
    log["logistic_full_sample"] = {"absz": round(float(m.coef_[0][0]), 3), "eg": round(float(m.coef_[0][1]), 3), "intercept": round(float(m.intercept_[0]), 3)}
    dev_all = np.array([dates[i] >= dt.date(2006, 1, 3) and i <= last_dev for i in range(n)])
    for th in (0.5, 0.55, 0.6, 0.65, 0.7):
        log["trades"][f"rolling|walk_forward_p>{th}|from_2009"] = evaluate(_rolling_trades(np.nan_to_num(p, nan=0) > th, dev_all, w), dates, rs, rn, lo="2009-01-01")
    # Plain cutoffs on the Engle-Granger statistic, windows and entries.
    for L in (63, 126, 252):
        for c in (-2.0, -2.4, -2.6, -2.8, -3.0, -3.34, -3.6):
            if L != 126 and c not in (-2.4, -2.8, -3.34):
                continue
            log["trades"][f"rolling|L{L}|eg<{c}"] = evaluate(_rolling_trades(W[L]["eg"] < c, dev_all, W[L]), dates, rs, rn) | {"detail": detail(_rolling_trades(W[L]["eg"] < c, dev_all, W[L]), dates, rs, rn)}
    for e in (1.0, 1.25, 1.75, 2.0):
        trs = _rolling_trades(w["eg"] < -2.8, dev_all, w, entry=e)
        log["trades"][f"rolling|L126|eg<-2.8|entry{e}"] = evaluate(trs, dates, rs, rn) | {"detail": detail(trs, dates, rs, rn)}
    # Sector-hedged: each bank's own part (less its trailing 126-session beta on the FirstRand-Absa average).
    sec = 0.5 * (_logret("fsr", dates) + _logret("abg", dates))
    xo, yo = _own(d["r_sbk"], sec), _own(d["r_ned"], sec)
    dev_sec = np.array([dates[i] >= dt.date(2006, 7, 1) and i <= last_dev for i in range(n)])
    with np.errstate(invalid="ignore", divide="ignore"):
        bo, zo, ego = sw.rolling(xo, yo)
    for c in (None, -2.4, -2.8, -3.34):
        gate = np.ones(n, bool) if c is None else ego < c
        log["trades"][f"sector_hedged|eg<{c}"] = evaluate(_rolling_trades(gate, dev_sec, {"b": bo, "z": zo}), dates, rs, rn)
    log["specifications_tried"] = len(log["forecasts"]) + len(log["trades"])
    for k, v in log["trades"].items():
        print(f"{k:44s}", v["futures"], v["cash"]["per_trade_bps"], v["eras"], v.get("detail", ""))
    json.dump(log, open("research/results/explore_gap.json", "w"), indent=1)
    # The frozen record the service serves (PROTOCOL.md, H16): the rule has no fitted parameter, so this is its
    # identity, dates and development figures.
    ch = log["trades"]["rolling|L126|eg<-2.8"]
    json.dump({"protocol": "research/PROTOCOL.md, H16", "frozen_on": "2026-11-11", "score_from": "2026-11-12", "window": 126, "crit": sw.GATE_CRIT,
               "verdict": "40 completed trades or 31 December 2036; mean net per trade at the institutional futures schedule above zero, one-sided t > 1.65",
               "development": {"from": "2006-01-03", "to": "2026-03-31", "specifications_searched": log["specifications_tried"],
                               "trades": ch["futures"]["trades"], "futures_bps": ch["futures"]["per_trade_bps"], "cash_bps": ch["cash"]["per_trade_bps"],
                               "t_futures": ch["futures"]["t"], **ch["detail"],
                               "eras": [{"from": a, "to": b, "trades": e[0], "futures_bps": e[1]} for (a, b), e in zip(ERAS, ch["eras"])],
                               "trades_per_year": round(ch["futures"]["trades"] / 20.25, 1),
                               "by_cutoff": {str(c): log["trades"][f"rolling|L126|eg<{c}"]["futures"]["per_trade_bps"] for c in (-2.4, -2.6, -2.8, -3.0, -3.34)}},
               "expected_live_bps": [40, 60]}, open("data/pair_spread_gate.json", "w"), indent=1)


if __name__ == "__main__":
    main()
