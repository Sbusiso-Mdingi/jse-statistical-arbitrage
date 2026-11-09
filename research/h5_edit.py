"""H5: the copula correlation tracks the last 252 training days' Kendall tau (research/PROTOCOL.md).

The one validation run. Writes research/results/h5.json and research/results/h5_daily.csv.
"""
import csv, json, math, sys
import numpy as np
from scipy import stats as st
sys.path.insert(0, "research")
from h5_weights import load, signals, evaluate, show, paired_t, positions, net_returns, PERIODS  # noqa: E402

W = 252
d = load()
fits = json.load(open("data/basket.json"))["fits"]


def tracking(c, u_tr, v_tr):
    tau = st.kendalltau(u_tr[-W:], v_tr[-W:]).statistic
    return {**c, "par": float(np.clip(math.sin(math.pi * tau / 2), -0.99, 0.99))}


base = signals(d, fits)
edit = signals(d, fits, edit_cop=tracking)
periods = ["design", "validation", "post-freeze"]
res_edit = evaluate(edit, "H5: par tracks 252-day tau", periods, note="the one validation run")
res_base = evaluate(base, "H1 as fitted (comparison)", periods, note="baseline for the paired comparison; figures already in h1.json")
show(res_base, "H1 as fitted"); show(res_edit, "H5 edit")

pb, pe = positions(base["h"]), positions(edit["h"])
nb, ne = net_returns(pb, base["rs"], base["rb"]), net_returns(pe, edit["rs"], edit["rb"])
dates = base["date"]
out = {"test": "H5", "window": W, "pass_mark": "validation Sharpe after costs above zero and above H1's 0.06"}
for p in periods:
    s, e = PERIODS[p]
    m = np.array([s <= x.isoformat() < e for x in dates])
    out[p] = res_edit[p]
    out[p]["vs_h1"] = paired_t(ne[m], nb[m])
    out[p]["calibration"] = {k: {"ks_p": float(st.kstest(sig["h"][m], "uniform").pvalue), "fires": float(np.mean(np.abs(sig["h"][m] - 0.5) > 0.45)),
                                 "deciles": (np.histogram(sig["h"][m], bins=10, range=(0, 1))[0] / m.sum() * 10).round(2).tolist()} for k, sig in (("fitted", base), ("edited", edit))}
    print(f"{p:12s} vs H1 {out[p]['vs_h1']}  calibration fitted KS p {out[p]['calibration']['fitted']['ks_p']:.3f} fires {100*out[p]['calibration']['fitted']['fires']:.1f}%  edited KS p {out[p]['calibration']['edited']['ks_p']:.3f} fires {100*out[p]['calibration']['edited']['fires']:.1f}%")
out["vs_h1_validation"] = out["validation"]["vs_h1"]
out["passed"] = out["validation"]["after_costs"]["sharpe"] > max(0.0, 0.06)
yrs = np.array([x.year for x in dates])
out["by_year"] = [{"year": int(y), "par_fitted": round(float(base["par"][yrs == y].mean()), 3), "par_edited": round(float(edit["par"][yrs == y].mean()), 3),
                   "fires_fitted": round(float(np.mean(np.abs(base["h"][yrs == y] - 0.5) > 0.45)), 4), "fires_edited": round(float(np.mean(np.abs(edit["h"][yrs == y] - 0.5) > 0.45)), 4)} for y in sorted(set(yrs))]
for r in out["by_year"]:
    print(f"  {r['year']}  par {r['par_fitted']:.3f} -> {r['par_edited']:.3f}   fires {100*r['fires_fitted']:5.2f}% -> {100*r['fires_edited']:5.2f}%")
print("PASSED" if out["passed"] else "FAILED", "validation Sharpe", out["validation"]["after_costs"]["sharpe"])
json.dump(out, open("research/results/h5.json", "w"), indent=1)
with open("research/results/h5_daily.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["date", "par_fitted", "par_edited", "h_fitted", "h_edited", "pos_h1", "pos_h5", "net_h1", "net_h5"])
    for i, x in enumerate(dates):
        w.writerow([x.isoformat(), f"{base['par'][i]:.4f}", f"{edit['par'][i]:.4f}", f"{base['h'][i]:.6f}", f"{edit['h'][i]:.6f}", int(pb[i]), int(pe[i]), f"{nb[i]:.8f}", f"{ne[i]:.8f}"])
