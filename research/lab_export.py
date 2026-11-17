"""The dashboard's rule lab and timeline: derived results only, no prices.

  python research/lab_export.py [path to jse-risk-management]     # use that repo's venv (pandas)

The lab: 216 versions of the spread rule on Standard Bank and Nedbank (window, gate cutoff, entry, fill, dividends),
each with its development record to 31 March 2026, its record since 1 April 2026, a quarterly P&L curve, and the
same version on the 18 pairs of H20. Beside them, how good the best of N versions looks when none has an edge
(a joint block bootstrap of the versions' demeaned monthly P&L). The timeline: the close-based 126-session
statistic and z each session, and the realistic rule's trades (research/results/realistic.json).

Writes data/lab.json and data/timeline.json. Reporting only; nothing frozen is changed.
"""
import json, math, sys
import datetime as dt
from itertools import product
from pathlib import Path
import numpy as np

sys.path.insert(0, "research"); sys.path.insert(0, "research/models"); sys.path.insert(0, "service")
from pairdata import load_pair  # noqa: E402
from app import switch as sw  # noqa: E402
from h19_total_return import raw_closes, dividends, total_return, shifted, START, DEV_END  # noqa: E402
import h20_other_pairs as h20  # noqa: E402

sw.EXPIRIES = sw.third_thursdays(2004, 2031)
UNSEEN = dt.date(2026, 4, 1)
WINDOWS, GATES, ENTRIES = (63, 126, 252), (None, -2.0, -2.4, -2.8, -3.2, -3.6), (1.0, 1.5, 2.0)
FILLS, DIVS = ("same", "next"), ("price", "total")
ERAS = [("2006-01-01", "2013-01-01"), ("2013-01-01", "2020-01-01"), ("2020-01-01", "2026-04-01")]
rng = np.random.default_rng(20261117)


_ROLL = {}


def run(x, y, rx, ry, dates, L, g, e, fill):
    key = (id(x), L)
    if key not in _ROLL:
        _ROLL[key] = sw.rolling(x, y, L)
    b, z, eg = _ROLL[key]
    on = np.array([d >= START for d in dates])
    gate = (on if g is None else (eg < g) & on).astype(np.int8)
    sw.ENTRY = e
    try:
        trs = sw.trades(gate, np.full(len(x), 0.5), b, z, copula_on=False, hold_through=True)
    finally:
        sw.ENTRY = 1.5
    if fill == "next":
        trs = shifted(trs, 1, len(x))
    daily, rows = sw.daily_returns(trs, dates, rx, ry, "futures")
    return daily, [r for r in rows if r["complete"] and dates[r["open"]] >= START]


def stats(nets):
    v = np.asarray(nets) * 1e4
    if len(v) < 3:
        return {"n": int(len(v)), "mean": round(float(v.mean()), 1) if len(v) else None}
    return {"n": int(len(v)), "mean": round(float(v.mean()), 1), "t": round(float(v.mean() / (v.std(ddof=1) / math.sqrt(len(v)))), 2),
            "win": round(float((v > 0).mean()), 2)}


def main():
    d = load_pair()
    dates = d["date"]
    n = len(dates)
    raw = {k: raw_closes(k) for k in ("sbk", "ned")}
    div = dividends()
    have = [i for i, t in enumerate(dates) if t in raw["sbk"] and t in raw["ned"]]
    assert len(have) == n, "every pair session needs a raw close"
    first_prev = max(t for t in sorted(set(raw["sbk"]) & set(raw["ned"])) if t < dates[0])
    seq = [first_prev] + dates
    tr = {k: total_return(seq, raw[k], div[k])[0][1:] for k in ("sbk", "ned")}
    series = {"price": (np.cumsum(d["r_sbk"]), np.cumsum(d["r_ned"]), np.expm1(d["r_sbk"]), np.expm1(d["r_ned"])),
              "total": (np.cumsum(tr["sbk"]), np.cumsum(tr["ned"]), np.expm1(tr["sbk"]), np.expm1(tr["ned"]))}
    dev = np.array([START <= t <= DEV_END for t in dates])
    months = sorted({(t.year, t.month) for t, k in zip(dates, dev) if k})
    mi = {m: i for i, m in enumerate(months)}
    quarters = sorted({(t.year, (t.month - 1) // 3) for t, k in zip(dates, dev) if k})
    qi = {q: i for i, q in enumerate(quarters)}

    # The 18 pairs of H20 and the four Big Four cross-pairs of H21, total returns.
    BIG4 = [("Banks", "SBK", "FSR"), ("Banks", "SBK", "ABG"), ("Banks", "NED", "FSR"), ("Banks", "NED", "ABG")]
    pairs = {}
    for _, a, b in h20.PAIRS + BIG4:
        sa, sb = h20.series(a), h20.series(b)
        idx = sa.index.intersection(sb.index)
        pd_dates = [t.date() for t in idx]
        x, y = np.log(sa.loc[idx].to_numpy()), np.log(sb.loc[idx].to_numpy())
        pairs[f"{a}/{b}"] = (x, y, np.r_[0.0, np.expm1(np.diff(x))], np.r_[0.0, np.expm1(np.diff(y))], pd_dates)

    specs, monthly = [], []
    other_cache = {}
    for L, g, e, fill, dv in product(WINDOWS, GATES, ENTRIES, FILLS, DIVS):
        x, y, rx, ry = series[dv]
        daily, rows = run(x, y, rx, ry, dates, L, g, e, fill)
        devrows = [r for r in rows if dates[r["close"]] <= DEV_END]
        unseen = [r for r in rows if dates[r["open"]] >= UNSEEN]
        m = np.zeros(len(months)); q = np.zeros(len(quarters))
        for t, v, k in zip(dates, daily, dev):
            if k:
                m[mi[(t.year, t.month)]] += v
                q[qi[(t.year, (t.month - 1) // 3)]] += v
        monthly.append(m)
        sharpe = float(m.mean() / m.std(ddof=1) * math.sqrt(12)) if m.std() > 0 else 0.0
        key = (L, g, e, fill)
        if key not in other_cache:
            big = {f"{x}/{y}" for _, x, y in BIG4}
            groups = {"sector": [], "big4": []}
            per = {"sector": {}, "big4": {}}
            for name, (px, py, prx, pry, pdates) in pairs.items():
                _, prow = run(px, py, prx, pry, pdates, L, g, e, fill)
                gk = "big4" if name in big else "sector"
                per[gk][name] = [r["net"] for r in prow]
                groups[gk] += [{"open": pdates[r["open"]], "net": r["net"]} for r in prow]
            res = {}
            for gk, pooled in groups.items():
                mm, tt = h20.clustered_t(pooled) if len(pooled) > 2 else (None, None)
                res[gk] = {"n": len(pooled), "mean": None if mm is None else round(mm * 1e4, 1),
                           "t": None if tt is None else round(tt, 2),
                           "positive": sum(1 for v in per[gk].values() if v and np.mean(v) > 0),
                           "of": sum(1 for v in per[gk].values() if v)}
            other_cache[key] = {**res["sector"], "big4": res["big4"]}
        specs.append({"window": L, "gate": g, "entry": e, "fill": fill, "div": dv,
                      "dev": {**stats([r["net"] for r in devrows]), "sharpe": round(sharpe, 2),
                              "eras": [stats([r["net"] for r in devrows if a <= dates[r["open"]].isoformat() < c]).get("mean") for a, c in ERAS]},
                      "unseen": stats([r["net"] for r in unseen]),
                      "curve": [round(float(v) * 100, 2) for v in np.cumsum(q)],
                      "pairs": other_cache[key]})
        print(L, g, e, fill, dv, specs[-1]["dev"]["n"], specs[-1]["dev"].get("mean"), specs[-1]["dev"]["sharpe"], other_cache[key]["mean"], other_cache[key]["big4"]["mean"])

    # Luck: the best Sharpe among N versions when none has an edge.
    M = np.array(monthly)  # versions x months
    M0 = M - M.mean(axis=1, keepdims=True)
    T = M.shape[1]
    reps, block, NMAX = 2000, 6, 60
    best = np.zeros((reps, NMAX))
    for r in range(reps):
        starts = rng.integers(0, T, size=math.ceil(T / block))
        idx = (starts[:, None] + np.arange(block)[None, :]).ravel()[:T] % T
        S = M0[:, idx]
        sh = S.mean(axis=1) / S.std(axis=1, ddof=1) * math.sqrt(12)
        perm = rng.permutation(len(sh))[:NMAX]
        best[r] = np.maximum.accumulate(sh[perm])
    luck = {"n": list(range(1, NMAX + 1)), "p50": [round(float(v), 2) for v in np.percentile(best, 50, axis=0)],
            "p95": [round(float(v), 2) for v in np.percentile(best, 95, axis=0)]}

    out = {"note": "Reporting only. Development to 31 March 2026; unseen from 1 April 2026. Net of institutional futures costs.",
           "dev": {"from": START.isoformat(), "to": DEV_END.isoformat()}, "unseen_from": UNSEEN.isoformat(),
           "last": dates[-1].isoformat(), "quarters": [f"{y}-Q{k + 1}" for y, k in quarters],
           "dims": {"window": WINDOWS, "gate": GATES, "entry": ENTRIES, "fill": FILLS, "div": DIVS},
           "found": {"window": 126, "gate": -2.8, "entry": 1.5, "fill": "same", "div": "price"},
           "specs": specs, "luck": luck}
    Path("data/lab.json").write_text(json.dumps(out, separators=(",", ":")))

    # The timeline: close-based statistic and z (price-only levels, as the frozen rule), and the realistic trades.
    b, z, eg = sw.rolling(np.cumsum(d["r_sbk"]), np.cumsum(d["r_ned"]))
    real = json.load(open("research/results/realistic.json"))
    tl = {"dates": [t.isoformat() for t in dates], "eg": [None if np.isnan(v) else round(float(v), 3) for v in eg],
          "z": [None if np.isnan(v) else round(float(v), 3) for v in z], "gate": sw.GATE_CRIT, "entry": 1.5,
          "trades": real["trades"], "trades_note": "decided at 16:00, filled in the closing auction, dividends counted; development to 31 March 2026"}
    Path("data/timeline.json").write_text(json.dumps(tl, separators=(",", ":")))
    print("lab", Path("data/lab.json").stat().st_size // 1000, "kB; timeline", Path("data/timeline.json").stat().st_size // 1000, "kB")
    print("luck p95 at N=1,10,30,60:", luck["p95"][0], luck["p95"][9], luck["p95"][29], luck["p95"][59])


if __name__ == "__main__":
    main()
