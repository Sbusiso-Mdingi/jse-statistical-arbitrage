from common import *
import csv as _csv
raw = {k: daily_raw(k) for k in ("sbk", "ned")}
B = {k: bars(k) for k in ("sbk", "ned")}
for k in ("sbk", "ned"):
    vol = {}
    for r in _csv.DictReader(open(f"{REPO}/data/raw/{k}_volume.csv")):
        d = dt.date.fromisoformat(r["date"])
        if d <= CUT and r["volume"]: vol[d] = float(r["volume"])
    for lo, hi in (("2010-01-01", "2013-01-01"), ("2018-01-01", "2020-01-01"), ("2024-04-01", "2026-04-01")):
        ds_ = [d for d in vol if lo <= d.isoformat() < hi and d in raw[k] and vol[d] > 0]
        adv = np.array([vol[d] * raw[k][d][0] / 100 for d in ds_])  # close in cents
        print(k, lo, hi, "median daily value traded R%.0fm, p10 R%.0fm" % (np.median(adv) / 1e6, np.percentile(adv, 10) / 1e6))
    # hourly volume shares
    ds_ = [d for d in B[k] if len(B[k][d]) == 8 and d in vol and vol[d] > 0 and d >= dt.date(2024, 4, 1)]
    hv = np.array([[B[k][d][h][2] for h in range(7, 15)] for d in ds_])
    tot = hv.sum(1)
    print(k, "bar-volume sum / Yahoo daily volume median %.2f; share by bar opening 09..16 SAST:" % np.median(tot / np.array([vol[d] for d in ds_])), np.round(np.median(hv / tot[:, None], 0), 3))
    # last continuous print vs official close
    diffs = np.array([math.log(raw[k][d][0] / B[k][d][14][1]) for d in B[k] if 14 in B[k][d] and d in raw[k] and d >= dt.date(2015, 1, 1)])
    print(k, "log(official close / 17:00-bar close) since 2015: mean %.1f bps, sd %.1f bps, mean abs %.1f bps" % (diffs.mean() * 1e4, diffs.std() * 1e4, np.abs(diffs).mean() * 1e4))
    # Corwin-Schultz spread from daily high/low built from bars (since 2015)
    ds2 = sorted(d for d in B[k] if len(B[k][d]) == 8 and d >= dt.date(2015, 1, 1))
    H = np.array([max(B[k][d][h][0] for h in B[k][d]) for d in ds2])
    hi_ = np.array([0.0]*len(ds2)); lo_ = np.array([0.0]*len(ds2))
    # need true bar highs/lows: reread
    print(k, "days for CS", len(ds2))
