"""H5 inspection, design period only (2010 to 2019) plus the parameter files themselves.

Reads the 202 monthly fits as text and looks for mechanisms, not for rules. Writes
research/results/h5_inspection.json. Any performance number computed here is a design-period
evaluation and is logged by h5_weights.evaluate.
"""
import json, math, sys
import numpy as np
from scipy import stats as st
sys.path.insert(0, "research")
from h5_weights import load, signals, evaluate, positions, net_returns, show, PERIODS  # noqa: E402

d = load()
B = json.load(open("data/basket.json"))
fits = B["fits"]
DES = ("2010-01-01", "2020-01-01")
out = {}

# 1. The parameters as text -------------------------------------------------------------
ar = np.array([f["sbk"]["coef"].get("ar1", 0.0) for f in fits])
ma = np.array([f["sbk"]["coef"].get("ma1", 0.0) for f in fits])
print("SBK ARMA(1,1) across 202 fits: ar1 in [%.3f, %.3f], ma1 in [%.3f, %.3f], ar1+ma1 in [%.3f, %.3f]" % (ar.min(), ar.max(), ma.min(), ma.max(), (ar + ma).min(), (ar + ma).max()))
# Implied mean recursion: mu_t - mu = ar (mu_{t-1} - mu) + (ar + ma) eps_{t-1}: an EWMA of past shocks.
print("  i.e. mu_t - mu = %.2f (mu_{t-1} - mu) %+.3f eps_{t-1}: a slow reversal forecast, half-life %.1f days" % (ar.mean(), (ar + ma).mean(), math.log(0.5) / math.log(ar.mean())))
out["arma"] = {"ar1": [ar.min(), ar.max()], "ma1": [ma.min(), ma.max()], "sum": [(ar + ma).min(), (ar + ma).max()], "half_life_days": math.log(0.5) / math.log(ar.mean())}

# 2. How big is the ARMA mean forecast relative to sigma, out of sample in design? ---------
base = signals(d, fits)
m = np.array([DES[0] <= x.isoformat() < DES[1] for x in base["date"]])
mu_c = np.array([next(f for f in fits if f["train_end"] <= x.isoformat())["sbk"]["coef"]["mu"] if False else 0 for x in base["date"][:1]])  # placeholder, not used
dev = base["mu_sbk"][m] - np.mean(base["mu_sbk"][m])
ratio = dev / base["sig_sbk"][m]
print("ARMA mean deviation / sigma, design: sd %.3f, |ratio| > 0.1 on %.1f%% of days, > 0.2 on %.1f%%" % (ratio.std(), 100 * np.mean(abs(ratio) > 0.1), 100 * np.mean(abs(ratio) > 0.2)))
# Does the forecast deviation predict the next return? (design only)
r_next = np.log1p(base["rs"][m])
slope = np.polyfit(dev, r_next, 1)[0]
corr = np.corrcoef(dev, r_next)[0, 1]
print("  regression of SBK log return on its own ARMA deviation, design: slope %.2f (1 = perfect forecast), corr %.3f" % (slope, corr))
out["arma_forecast"] = {"ratio_sd": float(ratio.std()), "slope": float(slope), "corr": float(corr)}

# 3. Calibration of u, v and h out of sample, design ----------------------------------------
for k in ("u", "v", "h"):
    x = base[k][m]
    ks = st.kstest(x, "uniform")
    dec = np.histogram(x, bins=10, range=(0, 1))[0] / len(x) * 10
    print(f"{k}: KS p = {ks.pvalue:.3f}; decile densities " + " ".join(f"{v:.2f}" for v in dec))
    out[f"calibration_{k}"] = {"ks_p": float(ks.pvalue), "deciles": dec.tolist()}
hi = base["h"][m] > 0.95
lo = base["h"][m] < 0.05
print("signal fires: h > 0.95 on %.2f%% of design days, h < 0.05 on %.2f%% (model says 5%% each)" % (100 * hi.mean(), 100 * lo.mean()))
out["fires"] = {"high": float(hi.mean()), "low": float(lo.mean())}

# 4. Where does the design-period P&L come from? -----------------------------------------
pos = positions(base["h"])
gross = net_returns(pos, base["rs"], base["rb"], 0.0)
held = np.concatenate([[0.0], pos[:-1]])
# day in hold: 1 on the first held day after a signal
day_in = np.zeros(len(pos), int); cnt = 0
for t in range(len(pos)):
    if t > 0 and pos[t - 1] != 0 and (t == 1 or abs(base["h"][t - 1] - 0.5) > 0.45):
        cnt = 1
    elif held[t] != 0:
        cnt += 1
    else:
        cnt = 0
    day_in[t] = cnt
rows = []
for k in range(1, 6):
    sel = m & (day_in == k) & (held != 0)
    rows.append({"day": k, "n": int(sel.sum()), "mean_bps": float(gross[sel].mean() * 1e4), "t": float(gross[sel].mean() / gross[sel].std(ddof=1) * math.sqrt(sel.sum()))})
    print(f"  held day {k}: n {sel.sum():4d}  mean gross {gross[sel].mean()*1e4:6.1f} bps  t {rows[-1]['t']:5.2f}")
out["by_day_in_hold"] = rows
for side, name in ((1.0, "long SBK"), (-1.0, "short SBK")):
    sel = m & (held == side)
    print(f"  {name:10s}: n {sel.sum():4d}  mean gross {gross[sel].mean()*1e4:6.1f} bps/day")
    out[f"side_{name}"] = {"n": int(sel.sum()), "mean_bps": float(gross[sel].mean() * 1e4)}
# signal strength at entry
sig_strength = np.abs(base["h"] - 0.5)
entry_days = (sig_strength > 0.45) & m
for lo_, hi_ in ((0.45, 0.47), (0.47, 0.49), (0.49, 0.5001)):
    sel = entry_days & (sig_strength >= lo_) & (sig_strength < hi_)
    nxt = np.roll(sel, 1)
    print(f"  entry |h-0.5| in [{lo_:.2f},{hi_:.2f}): n {sel.sum():3d}  next-day gross {gross[nxt].mean()*1e4:6.1f} bps")
flips = m & (held != 0) & (np.concatenate([[0.0], held[:-1]]) == -held)
print("  flips (new signal reverses an open position): %d of %d entries in design" % (flips.sum(), int(((held != 0) & (np.concatenate([[0.0], held[:-1]]) != held) & m).sum())))
# gap between exit and the next entry
ent = np.flatnonzero((pos != 0) & (np.concatenate([[0.0], pos[:-1]]) != pos) & m)
exits = np.flatnonzero((pos == 0) & (np.concatenate([[0.0], pos[:-1]]) != 0))
gaps = []
for e in ent:
    prev_exit = exits[exits < e]
    if len(prev_exit): gaps.append(e - prev_exit[-1])
gaps = np.array(gaps)
print("  days flat between an exit and the next entry, design: median %d, within 2 days on %.0f%%" % (np.median(gaps), 100 * np.mean(gaps <= 2)))
out["gaps"] = {"median": float(np.median(gaps)), "share_le_2": float(np.mean(gaps <= 2))}

# 5. Design-period evaluations of edits (each logged as a look at design data) -------------
zero_arma = lambda c: {**c, "ar1": 0.0, "ma1": 0.0}
res_base = evaluate(base, "H1 as fitted", ["design"], note="baseline, reproduces h1.json")
show(res_base, "H1 as fitted")
edit1 = signals(d, fits, edit_sbk=zero_arma)
res1 = evaluate(edit1, "SBK ar1 = ma1 = 0", ["design"], note="remove the near-cancelling ARMA(1,1) direction from the SBK margin")
show(res1, "SBK ar1 = ma1 = 0")
changed = np.mean(np.abs(edit1["u"][m] - base["u"][m]) > 0.01)
agree = np.mean((np.abs(edit1["h"][m] - 0.5) > 0.45) == (np.abs(base["h"][m] - 0.5) > 0.45))
print("  u moved by more than 0.01 on %.0f%% of design days; the two rules agree on whether to fire on %.1f%% of days" % (100 * changed, 100 * agree))
out["edit_zero_arma"] = {"design": res1["design"], "u_changed_share": float(changed), "fire_agreement": float(agree)}
pt = {}
p1 = positions(edit1["h"]); pb = positions(base["h"])
from h5_weights import paired_t
pt = paired_t(net_returns(p1, edit1["rs"], edit1["rb"])[m], net_returns(pb, base["rs"], base["rb"])[m])
print("  edit vs H1 on paired design days:", pt)
out["edit_zero_arma"]["vs_h1_design"] = pt

json.dump(out, open("research/results/h5_inspection.json", "w"), indent=1)
