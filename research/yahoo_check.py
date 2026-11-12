"""Has Yahoo changed the data the frozen rules read? Run after research/00_data.R (the refit job runs it).

  python research/yahoo_check.py [T]

The frozen rules read Yahoo's "adjusted" closes, which for these banks carry about a hundredth of each dividend
(research/PROTOCOL.md, amendment of 12 November 2026). Two checks: (1) on each ex-dividend session, Yahoo's
adjustment step as a share of the dividend yield (about 0.01 today; near 1 means Yahoo has fixed it, and the frozen
rules' inputs have changed under them); (2) if a local snapshot exists (research/snapshot.py), the largest
difference between today's and the snapshot's adjusted log returns on common sessions. Writes
research/results/yahoo_check[_T].json. Reports only; it never stops anything.
"""
import csv, glob, json, math, sys
import datetime as dt
import numpy as np


def series(path):
    out = {}
    for r in csv.DictReader(open(path)):
        try:
            c, a = float(r["close"]), float(r["adjusted"])
        except (ValueError, KeyError):
            continue
        if c > 0 and a > 0:
            out[dt.date.fromisoformat(r["date"].strip('"'))] = (c, a)
    return out


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else None
    divs = {"sbk": {}, "ned": {}}
    for r in csv.DictReader(open("data/raw/h15_div.csv")):
        divs[r["bank"]][dt.date.fromisoformat(r["ex_date"])] = float(r["amount"])
    out = {"checked": dt.date.today().isoformat(), "banks": {}}
    snaps = sorted(glob.glob("data/snapshots/*/sbk.csv"))
    for k in ("sbk", "ned"):
        s = series(f"data/raw/{k}.csv"); days = sorted(s)
        ratio = []
        for i in range(1, len(days)):
            d = days[i]
            if d in divs[k]:
                (cp, ap), (c, a) = s[days[i - 1]], s[d]
                ratio.append((d.isoformat(), ((ap / cp) / (a / c) - 1) / -(divs[k][d] / cp)))
        recent = [x for _, x in ratio[-4:]]
        b = {"ex_dates": len(ratio), "recent_step_over_yield": [round(x, 4) for x in recent],
             "fixed_by_yahoo": bool(recent and np.median(recent) > 0.5)}
        if snaps:
            old = series(snaps[-1].replace("sbk.csv", f"{k}.csv"))
            common = sorted(set(old) & set(s))
            r0 = np.diff(np.log([old[d][1] for d in common])); r1 = np.diff(np.log([s[d][1] for d in common]))
            b["snapshot"] = snaps[-1].split("/")[-2]
            b["max_abs_return_change"] = float(np.abs(r1 - r0).max()) if len(common) > 1 else None
        out["banks"][k] = b
    out["changed"] = any(v["fixed_by_yahoo"] or (v.get("max_abs_return_change") or 0) > 1e-6 for v in out["banks"].values())
    path = f"research/results/yahoo_check{'_' + tag if tag else ''}.json"
    json.dump(out, open(path, "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
