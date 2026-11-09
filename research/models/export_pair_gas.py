"""Export the pair's score-driven copula (H8) for the live service: the GAS h for every walk-forward day
up to the freeze, and the final fold's GAS parameters with the state for the first session after it.
Writes data/pair_gas.json. Post-freeze sessions are filtered forward by the service (app.model.gas_filter)."""
import csv, json, math, sys
import numpy as np
from scipy import stats as st
sys.path.insert(0, "research"); sys.path.insert(0, "research/models"); sys.path.insert(0, "service")
from copulas_py import d, dates, folds, pits, gas_fit, gas_unpack, gas_filter, t_score_rho  # noqa: E402

f = folds[-1]; te = f["train_end"]
n_train = sum(1 for x in dates if x.isoformat() <= te)
u, v = pits(f, n_train, n_train)
p = gas_fit(u, v, f["copula"]["par"])
omega, beta, alpha, nu = gas_unpack(p)
ff, _, _ = gas_filter(u, v, omega, beta, alpha, nu, omega / max(1 - beta, 1e-3))
x_T, y_T = st.t.ppf(u[-1], nu), st.t.ppf(v[-1], nu)
rho_T = math.tanh(ff[-1])
f_next = max(min(omega + beta * ff[-1] + alpha * t_score_rho(x_T, y_T, rho_T, nu) * (1 - rho_T ** 2), 4.0), -4.0)
print(f"final fold to {te}: omega {omega:.4f} beta {beta:.4f} alpha {alpha:.4f} nu {nu:.2f}; rho at freeze {rho_T:.3f}, next {math.tanh(f_next):.3f}")

rows = [r for r in csv.DictReader(open("research/results/copulas_py.csv")) if r["model"] == "gas_t" and r["date"] <= te]
out = {
    "generated_from": "research/models/copulas_py.py (H8) and export_pair_gas.py",
    "model": "GAS Student t copula, rho_t = tanh(f_t), f_{t+1} = omega + beta f_t + alpha s_t, identity scaling",
    "latest": {"train_end": te, "omega": omega, "beta": beta, "alpha": alpha, "nu": nu, "f_next": f_next, "rho_train_end": rho_T},
    "history": {"date": [r["date"] for r in rows], "h": [float(r["h"]) for r in rows], "rho": [float(r["state"]) for r in rows]},
}
json.dump(out, open("data/pair_gas.json", "w"))
print("wrote data/pair_gas.json with", len(rows), "days")
