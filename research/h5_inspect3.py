"""H5 inspection, part 3: a copula correlation that tracks recent dependence. Design only.

At each month end the fitted Student t copula keeps its degrees of freedom, but its
correlation is replaced by the value implied (tau = 2/pi arcsin rho) by Kendall's tau of the
last W training-day PITs under that month's fit. Window chosen by calibration of h on design,
not by returns. Then one design-period evaluation of the chosen window.
"""
import json, math, sys
import numpy as np
from scipy import stats as st
sys.path.insert(0, "research")
from h5_weights import load, signals, evaluate, show, paired_t, positions, net_returns  # noqa: E402

d = load()
fits = json.load(open("data/basket.json"))["fits"]
DES = ("2010-01-01", "2020-01-01")


def tracking(W):
    def edit(c, u_tr, v_tr):
        tau = st.kendalltau(u_tr[-W:], v_tr[-W:]).statistic
        return {**c, "par": float(np.clip(math.sin(math.pi * tau / 2), -0.99, 0.99)), "tau_track": float(tau)}
    return edit

base = signals(d, fits)
m = np.array([DES[0] <= x.isoformat() < DES[1] for x in base["date"]])
yrs = np.array([x.year for x in base["date"]])
out = {"windows": []}
print("window  KS stat  KS p   fires%   (design, calibration only)")
sigs = {}
for W in (126, 252, 504):
    s = signals(d, fits, edit_cop=tracking(W))
    sigs[W] = s
    hh = s["h"][m]
    ks = st.kstest(hh, "uniform")
    fires = float(np.mean(np.abs(hh - 0.5) > 0.45))
    out["windows"].append({"W": W, "ks": float(ks.statistic), "p": float(ks.pvalue), "fires": fires})
    print(f"{W:5d}   {ks.statistic:.4f}  {ks.pvalue:.3f}  {100*fires:5.2f}")
best = min(out["windows"], key=lambda r: r["ks"])
W = best["W"]
print("chosen by calibration: W =", W)
out["chosen_W"] = W
s = sigs[W]
print("\nyear  fires% as fitted -> tracking   par as fitted -> tracking (mean over the year)")
rows = []
for y in range(2010, 2020):
    sel = m & (yrs == y)
    rows.append({"year": y, "fires_base": float(np.mean(np.abs(base["h"][sel] - 0.5) > 0.45)), "fires_edit": float(np.mean(np.abs(s["h"][sel] - 0.5) > 0.45)),
                 "par_base": float(base["par"][sel].mean()), "par_edit": float(s["par"][sel].mean())})
    r = rows[-1]
    print(f"{y}  {100*r['fires_base']:5.2f} -> {100*r['fires_edit']:5.2f}        {r['par_base']:.3f} -> {r['par_edit']:.3f}")
out["by_year"] = rows
print("\nh decile densities, design, tracking:", " ".join(f"{x:.2f}" for x in np.histogram(s["h"][m], bins=10, range=(0, 1))[0] / m.sum() * 10))

# One design-period performance evaluation of the chosen edit (logged).
res = evaluate(s, f"copula par tracks {W}-day tau", ["design"], note="chosen by calibration of h on design; first and only design-period look at this edit's returns")
show(res, f"par tracks {W}d tau")
pb, pe = positions(base["h"]), positions(s["h"])
pt = paired_t(net_returns(pe, s["rs"], s["rb"])[m], net_returns(pb, base["rs"], base["rb"])[m])
print("  edit vs H1 on paired design days:", pt)
agree = float(np.mean((np.abs(s["h"][m] - 0.5) > 0.45) == (np.abs(base["h"][m] - 0.5) > 0.45)))
print(f"  the two rules agree on whether to fire on {100*agree:.1f}% of design days")
out["design_eval"] = res["design"]; out["vs_h1_design"] = pt; out["fire_agreement"] = agree
json.dump(out, open("research/results/h5_inspection3.json", "w"), indent=1)
