"""H5 inspection, part 2: where is the copula miscalibrated, design period only."""
import json, math, sys
import numpy as np
from scipy import stats as st
sys.path.insert(0, "research")
from h5_weights import load, signals, evaluate, show, paired_t, positions, net_returns  # noqa: E402

d = load()
B = json.load(open("data/basket.json")); fits = B["fits"]
DES = ("2010-01-01", "2020-01-01")
base = signals(d, fits)
m = np.array([DES[0] <= x.isoformat() < DES[1] for x in base["date"]])
u, v, h = base["u"][m], base["v"][m], base["h"][m]
yrs = np.array([x.year for x in base["date"]])[m]
out = {}

# A. does the under-dispersion of h depend on how extreme u is?
print("h tail share (|h-0.5| > 0.45, model 10%) by |u-0.5| tercile:")
cuts = np.quantile(np.abs(u - 0.5), [1 / 3, 2 / 3])
for lo, hi, name in ((0, cuts[0], "centre"), (cuts[0], cuts[1], "middle"), (cuts[1], 1, "extreme u")):
    sel = (np.abs(u - 0.5) >= lo) & (np.abs(u - 0.5) < hi)
    print(f"  {name:10s} n {sel.sum():4d}  fires {100*np.mean(np.abs(h[sel]-0.5) > 0.45):5.2f}%  KS p {st.kstest(h[sel], 'uniform').pvalue:.3f}")
    out[f"tercile_{name}"] = float(np.mean(np.abs(h[sel] - 0.5) > 0.45))

# B. by year: firing share, and realised Kendall tau of (u, v) against the fitted tau used that year
print("year  fires%  realised tau(u,v)  fitted tau (Dec before)  implied rho from realised tau")
fit_tau = {f["train_end"][:4]: f["copula"]["tau"] for f in fits}
fit_par = {f["train_end"][:4]: f["copula"]["par"] for f in fits}
rows = []
for y in sorted(set(yrs)):
    s = yrs == y
    tau = st.kendalltau(u[s], v[s]).statistic
    ft = fit_tau[str(y - 1)]
    rows.append({"year": int(y), "fires": float(np.mean(np.abs(h[s] - 0.5) > 0.45)), "tau_realised": float(tau), "tau_fitted": ft, "rho_realised": math.sin(math.pi * tau / 2), "par_fitted": fit_par[str(y - 1)]})
    print(f"{y}  {100*rows[-1]['fires']:5.2f}   {tau:.3f}             {ft:.3f}                 {rows[-1]['rho_realised']:.3f} (fitted par {fit_par[str(y-1)]:.3f})")
out["by_year"] = rows
print("design mean: realised tau %.3f, fitted tau %.3f; realised rho %.3f, fitted par %.3f" % (
    np.mean([r["tau_realised"] for r in rows]), np.mean([r["tau_fitted"] for r in rows]), np.mean([r["rho_realised"] for r in rows]), np.mean([r["par_fitted"] for r in rows])))

# C. what single edit to the copula makes h uniform on design? Chosen by calibration, not by returns.
print("\ncalibration of h on design under edits to the copula (no returns computed):")
print("  edit                 KS stat  KS p   fires%")
cands = []
def calib(label, edit):
    s = signals(d, fits, edit_cop=edit)
    hh = s["h"][m]
    ks = st.kstest(hh, "uniform")
    fires = float(np.mean(np.abs(hh - 0.5) > 0.45))
    cands.append({"label": label, "ks": float(ks.statistic), "p": float(ks.pvalue), "fires": fires})
    print(f"  {label:20s} {ks.statistic:.4f}  {ks.pvalue:.3f}  {100*fires:5.2f}")
    return s
calib("as fitted", None)
for delta in (0.02, 0.04, 0.06, 0.08, 0.10):
    calib(f"par + {delta:.2f}", lambda c, u_, v_, dl=delta: {**c, "par": min(c["par"] + dl, 0.99)})
for mult in (2.0, 4.0):
    calib(f"df x {mult:.0f}", lambda c, u_, v_, mu=mult: {**c, "par2": c["par2"] * mu})
calib("df = 1e6 (Gaussian)", lambda c, u_, v_: {**c, "par2": 1e6})
calib("par+0.06, df x 2", lambda c, u_, v_: {**c, "par": min(c["par"] + 0.06, 0.99), "par2": c["par2"] * 2})
out["calibration_candidates"] = cands
json.dump(out, open("research/results/h5_inspection2.json", "w"), indent=1)
