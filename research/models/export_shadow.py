"""Freeze H13's variants (research/PROTOCOL.md) into data/pair_shadow.json.

A: H12's own-volatility copula fitted once on the final fold's training PITs (to the freeze) with the H12 code; the
state at the end of training is stored for the service to filter forward. B: the VIX level for the gate.
A reference h for the post-freeze sessions on disk is stored for the parity test.
"""
import json, math, sys
import numpy as np
from scipy import optimize
sys.path.insert(0, "research"); sys.path.insert(0, "research/models"); sys.path.insert(0, "service")
import h12_gauge as H  # noqa: E402
from app.shadow import x_filter, own_gauge  # noqa: E402

FROZEN_ON = "2026-11-09"
VIX_LEVEL = 0.170967  # upper third of the VIX before design signal days (PROTOCOL.md, H12 disclosure), in the margins' units

f = H.folds[-1]; te = f["train_end"]
n_train = sum(1 for x in H.dates if x.isoformat() <= te)
u, v = H.pits(f, H.n, n_train)
pg = H.gas_fit(u[:n_train], v[:n_train], f["copula"]["par"])
_, _, _, par_g = H.gas_score(pg, u[:n_train + 1] if H.n > n_train else u, v[:n_train + 1] if H.n > n_train else v, n_train)
raw = H.GAUGES["own"][:n_train]; mu, sd = float(np.nanmean(raw)), float(np.nanstd(raw))
x_all = np.nan_to_num((H.GAUGES["own"] - mu) / sd, nan=0.0)
p0 = [pg[0], pg[1], pg[2], math.log(par_g["nu"] - 2), 0.0, 0.0]
nll = lambda p: -float(np.sum(H.x_filter(p, u[:n_train], v[:n_train], x_all[:n_train])[0]))
res = optimize.minimize(nll, p0, method="Nelder-Mead", options={"maxiter": 4000, "xatol": 1e-4, "fatol": 1e-4})
p = res.x if res.fun <= nll(p0) else np.array(p0)
params = {"omega": float(p[0]), "beta": float(1 / (1 + math.exp(-p[1]))), "alpha": float(math.exp(p[2])),
          "eta0": float(p[3]), "gamma": float(p[4]), "eta1": float(p[5])}
f0 = params["omega"] / max(1 - params["beta"], 1e-3)
tr = x_filter(params, u[:n_train], v[:n_train], x_all[:n_train], f0, 0.0)
ref = H.x_filter(p, u[:n_train], v[:n_train], x_all[:n_train])
gap = float(np.abs(tr["logc"] - ref[0]).max())
assert gap < 1e-8, gap
# the service's own gauge must match H12's on the training window
xs = own_gauge(H.d["r_sbk"], H.d["r_ned"], mu, sd)
assert float(np.abs(xs[20:n_train] - x_all[20:n_train]).max()) < 1e-10
post = x_filter(params, u[n_train:], v[n_train:], x_all[n_train:], tr["f_last"], tr["s_last"])
out = {"frozen_on": FROZEN_ON, "train_end": te, "protocol": "research/PROTOCOL.md, H13",
       "own_vol": {"params": params, "gauge": {"mu": mu, "sd": sd, "window": 20},
                   "state": {"f_last": tr["f_last"], "s_last": tr["s_last"]}, "train_gain": float(nll(p0) - res.fun)},
       "vix_gate": {"level": VIX_LEVEL},
       "reference": {"date": [x.isoformat() for x in H.dates[n_train:]], "h": post["h"].tolist()}}
json.dump(out, open("data/pair_shadow.json", "w"), indent=1)
print(json.dumps({k: v for k, v in out["own_vol"].items()}), "| reference days", len(out["reference"]["date"]), "| training parity", gap)
