"""SBK and NED daily log returns, aligned VIX, and realised variance from the 60-minute bars."""
import csv, math, datetime as dt
from collections import defaultdict
import numpy as np
import sys
sys.path.insert(0, "research")
from h5_weights import _read_px  # bad-print cleaning as in research/clean.R


def load_pair():
    s, n = dict(_read_px("sbk")), dict(_read_px("ned"))
    dates = sorted(set(s) & set(n))
    vix = {}
    for r in csv.DictReader(open("data/raw/vix.csv")):
        try:
            vix[dt.date.fromisoformat(r["date"].strip('"'))] = float(r["vix"])
        except ValueError:
            pass
    vd = sorted(vix); vnum = np.array([d.toordinal() for d in vd])
    keep, vx = [], []
    for d in dates:
        i = np.searchsorted(vnum, d.toordinal() - 1, side="right") - 1
        if i >= 0:
            keep.append(d); vx.append(vix[vd[i]] / 100)
    dates = keep
    ps = np.array([s[d] for d in dates]); pn = np.array([n[d] for d in dates])
    return {"date": dates[1:], "r_sbk": np.diff(np.log(ps)), "r_ned": np.diff(np.log(pn)), "vix": np.array(vx[1:])}


def realised_variance(name, dates):
    """Close-to-close realised variance from the hourly bar closes, including the overnight gap."""
    bars = defaultdict(dict)
    for r in csv.DictReader(open(f"data/raw/{name}_60m.csv")):
        t = dt.datetime.utcfromtimestamp(int(r["time"]))
        bars[t.date()][t.hour] = float(r["close"])
    days = sorted(bars)
    rv = {}
    prev_close = None
    for d in days:
        closes = [bars[d][h] for h in sorted(bars[d])]
        seq = ([prev_close] if prev_close else []) + closes
        if len(seq) > 1:
            lr = np.diff(np.log(seq))
            rv[d] = float((lr ** 2).sum())
        prev_close = closes[-1]
    return np.array([rv.get(d, np.nan) for d in dates])


if __name__ == "__main__":
    d = load_pair()
    print(len(d["date"]), d["date"][0], d["date"][-1])
    for k in ("sbk", "ned"):
        rv = realised_variance(k, d["date"])
        r2 = d[f"r_{k}"] ** 2
        m = ~np.isnan(rv)
        print(k, "RV days", m.sum(), "first", d["date"][int(np.argmax(m))], "corr(RV, r^2)", round(float(np.corrcoef(rv[m], r2[m])[0, 1]), 3), "mean ratio", round(float(rv[m].mean() / r2[m].mean()), 2))
    with open("data/rv_daily.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["date", "r_sbk", "r_ned", "vix", "rv_sbk", "rv_ned"])
        rs, rn = realised_variance("sbk", d["date"]), realised_variance("ned", d["date"])
        for i, x in enumerate(d["date"]):
            w.writerow([x.isoformat(), f"{d['r_sbk'][i]:.8f}", f"{d['r_ned'][i]:.8f}", f"{d['vix'][i]:.5f}", "" if np.isnan(rs[i]) else f"{rs[i]:.10f}", "" if np.isnan(rn[i]) else f"{rn[i]:.10f}"])
    print("wrote data/rv_daily.csv")
