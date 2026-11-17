"""H20 (research/PROTOCOL.md): H16's rule, unchanged, on 18 JSE pairs it has never seen.

  python research/h20_other_pairs.py [path to jse-risk-management]

Prices come from the jse-risk-management download (Yahoo closes and dividend events, total returns built there,
no-trade days and bad prints dropped). Writes research/results/h20.json. Run once, as registered.
"""
import json, math, sys
import datetime as dt
from pathlib import Path
import numpy as np

RISK = Path(sys.argv[1] if len(sys.argv) > 1 else Path.home() / "Developer/jse-risk-management")
sys.path.insert(0, str(RISK)); sys.path.insert(0, "research"); sys.path.insert(0, "service")
from jserisk import data as jd  # noqa: E402
from app import switch as sw  # noqa: E402
from h19_total_return import shifted, summary  # noqa: E402

sw.EXPIRIES = sw.third_thursdays(2004, 2031)
START = dt.date(2006, 1, 3)
UNSEEN = dt.date(2026, 4, 1)
ERAS = [("2006-01-01", "2013-01-01"), ("2013-01-01", "2020-01-01"), ("2020-01-01", "2100-01-01")]
PAIRS = [  # (sector, first, second): the second's log level is regressed on the first's
    ("Banks", "FSR", "ABG"), ("Banks", "FSR", "CPI"), ("Banks", "ABG", "CPI"),
    ("Insurers", "SLM", "MTM"), ("Insurers", "SLM", "DSY"),
    ("Gold", "GFI", "ANG"), ("Gold", "GFI", "HAR"), ("Gold", "ANG", "HAR"), ("Gold", "HAR", "DRD"),
    ("Platinum", "IMP", "VAL"),
    ("Telecoms", "MTN", "VOD"), ("Telecoms", "VOD", "TKG"),
    ("Food retail", "SHP", "PIK"), ("Food retail", "SHP", "SPP"),
    ("Clothing retail", "MRP", "TFG"), ("Clothing retail", "MRP", "TRU"), ("Clothing retail", "TFG", "TRU"),
    ("Hospitals", "NTC", "LHC"),
]
assert len(PAIRS) == 18


def series(t):
    df = jd.clean(jd.read(RISK / "data" / "raw" / f"{t}.JO.csv"))
    return df["adjusted"]


def pair_trades(a, b):
    sa, sb = series(a), series(b)
    idx = sa.index.intersection(sb.index)
    dates = [d.date() for d in idx]
    x, y = np.log(sa.loc[idx].to_numpy()), np.log(sb.loc[idx].to_numpy())
    rx, ry = np.r_[0.0, np.expm1(np.diff(x))], np.r_[0.0, np.expm1(np.diff(y))]
    bb, z, eg = sw.rolling(x, y)
    live = np.array([d >= START for d in dates])
    gate = ((eg < sw.GATE_CRIT) & live).astype(np.int8)
    trs = sw.trades(gate, np.full(len(x), 0.5), bb, z, copula_on=False, hold_through=True)
    return trs, dates, rx, ry, eg


def scored(trs, dates, rx, ry, sched):
    _, rows = sw.daily_returns(trs, dates, rx, ry, sched)
    return [{"open": dates[r["open"]], "close": dates[r["close"]], "net": float(r["net"])}
            for r in rows if r["complete"] and dates[r["open"]] >= START]


def clustered_t(rows):
    """Mean net per trade and its t, standard error clustered by the calendar month of entry."""
    v = np.array([r["net"] for r in rows])
    n = len(v)
    if n < 3:
        return None, None
    m = v.mean()
    groups = {}
    for r, x in zip(rows, v):
        groups.setdefault((r["open"].year, r["open"].month), []).append(x - m)
    var = sum(sum(g) ** 2 for g in groups.values()) / n ** 2
    return m, m / math.sqrt(var)


def main(pairs=PAIRS, path="research/results/h20.json", protocol="H20"):
    out = {"protocol": f"research/PROTOCOL.md, {protocol}", "pairs": []}
    pooled = {"primary": [], "same_close": [], "cash": []}
    for sector, a, b in pairs:
        trs, dates, rx, ry, eg = pair_trades(a, b)
        n = len(dates)
        prim = scored(shifted(trs, 1, n), dates, rx, ry, "futures")
        same = scored(trs, dates, rx, ry, "futures")
        cash = scored(shifted(trs, 1, n), dates, rx, ry, "cash")
        for k, rows in (("primary", prim), ("same_close", same), ("cash", cash)):
            pooled[k] += [dict(r, pair=f"{a}/{b}") for r in rows]
        gate_share = float((eg[np.array([d >= START for d in dates])] < sw.GATE_CRIT).mean())
        out["pairs"].append({"sector": sector, "pair": f"{a}/{b}", "sessions": n, "first": dates[0].isoformat(),
                             "last": dates[-1].isoformat(), "gate_share": round(gate_share, 3),
                             "primary": summary([r["net"] for r in prim]), "same_close": summary([r["net"] for r in same]),
                             "cash": summary([r["net"] for r in cash]),
                             "eras": [{"from": f, "to": t, **summary([r["net"] for r in prim if f <= r["open"].isoformat() < t])}
                                      for f, t in ERAS],
                             "since_1_april": summary([r["net"] for r in prim if r["open"] >= UNSEEN])})
    res = {}
    for k, rows in pooled.items():
        m, t = clustered_t(rows)
        res[k] = {**summary([r["net"] for r in rows]), "mean_bps": round(m * 1e4, 1), "t_clustered": round(t, 2)}
    m, t = clustered_t(pooled["primary"])
    means = [p["primary"].get("mean_bps") for p in out["pairs"] if p["primary"]["trades"]]
    pos = sum(1 for x in means if x > 0)
    from scipy.stats import binomtest
    res["pairs_positive"] = {"positive": pos, "of": len(means), "sign_test_p": round(binomtest(pos, len(means), 0.5, alternative="greater").pvalue, 3)}
    res["eras"] = [{"from": f, "to": t_, **summary([r["net"] for r in pooled["primary"] if f <= r["open"].isoformat() < t_])} for f, t_ in ERAS]
    res["since_1_april"] = summary([r["net"] for r in pooled["primary"] if r["open"] >= UNSEEN])
    res["verdict"] = {"passed": bool(m > 0 and t > 1.65), "mean_bps": round(m * 1e4, 1), "t_clustered": round(t, 2), "bar": "mean > 0 and one-sided t > 1.65"}
    out["pooled"] = res
    out["trades"] = [{"pair": r["pair"], "open": r["open"].isoformat(), "close": r["close"].isoformat(), "net_bps": round(r["net"] * 1e4, 1)}
                     for r in pooled["primary"]]
    Path(path).write_text(json.dumps(out, indent=1))
    for p in out["pairs"]:
        print(f"{p['pair']:9s} {p['sector']:15s} trades {p['primary']['trades']:3d}  primary {p['primary'].get('mean_bps')!s:>7}  "
              f"same-close {p['same_close'].get('mean_bps')!s:>7}  gate {p['gate_share']:.0%}")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
