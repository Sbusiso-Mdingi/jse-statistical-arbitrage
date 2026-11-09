"""Export the score-driven copula for the live service: the GAS h for every walk-forward day and the
latest fit's GAS parameters with its terminal state, so new sessions can be filtered forward.
Writes data/basket_gas.json. Also scores the H1 rule on the GAS h by period (reported, not a pass mark)."""
import csv, json, math, sys
import numpy as np
sys.path.insert(0, "research"); sys.path.insert(0, "research/models"); sys.path.insert(0, "service")
from h5_weights import load, month_ends, _filter_full, evaluate, show, positions, net_returns, paired_t, PERIODS  # noqa: E402
from copulas_py import gas_fit, gas_unpack, gas_filter  # noqa: E402

d = load(); dates = d["date"]; n = len(dates)
B = json.load(open("data/basket.json")); latest = B["latest"]
te = latest["train_end"]
n_train = sum(1 for x in dates if x.isoformat() <= te)
fs = _filter_full(latest["sbk"], d["r_sbk"][:n_train], d["vix"][:n_train], n_train)
fb = _filter_full(latest["bsk"], d["r_bsk"][:n_train], d["vix"][:n_train], n_train)
u, v = np.clip(fs["u"], 1e-6, 1 - 1e-6), np.clip(fb["u"], 1e-6, 1 - 1e-6)
p = gas_fit(u, v, latest["copula"]["par"])
omega, beta, alpha, nu = gas_unpack(p)
f, _, _ = gas_filter(u, v, omega, beta, alpha, nu, omega / max(1 - beta, 1e-3))
# terminal state: f for the first day after the training end (the recursion already advanced past the last training day)
from copulas_py import t_score_rho
from scipy import stats as st
x_T, y_T = st.t.ppf(u[-1], nu), st.t.ppf(v[-1], nu)
rho_T = math.tanh(f[-1])
f_next = omega + beta * f[-1] + alpha * t_score_rho(x_T, y_T, rho_T, nu) * (1 - rho_T ** 2)
f_next = max(min(f_next, 4.0), -4.0)
print(f"latest GAS fit to {te}: omega {omega:.4f} beta {beta:.4f} alpha {alpha:.4f} nu {nu:.2f}; rho at train end {rho_T:.3f}, next {math.tanh(f_next):.3f}")

rows = list(csv.DictReader(open("research/results/copulas_basket.csv")))
gas = {r["date"]: (float(r["h"]), float(r["state"])) for r in rows if r["model"] == "gas_t"}
hist_dates = [x.isoformat() for x in dates if x.isoformat() in gas]
out = {
    "generated_from": "research/models/h9_basket_gas.py and export_gas.py",
    "model": "GAS Student t copula, rho_t = tanh(f_t), f_{t+1} = omega + beta f_t + alpha s_t, identity scaling",
    "latest": {"train_end": te, "omega": omega, "beta": beta, "alpha": alpha, "nu": nu, "f_next": f_next, "rho_train_end": rho_T},
    "history": {"date": hist_dates, "h": [gas[x][0] for x in hist_dates], "rho": [gas[x][1] for x in hist_dates]},
}
json.dump(out, open("data/basket_gas.json", "w"))
print("wrote data/basket_gas.json with", len(hist_dates), "days")

# The H1 rule on the GAS h, by period: reported, not a pass mark.
idx = {x.isoformat(): i for i, x in enumerate(dates)}
pos_idx = [idx[x] for x in hist_dates]
sig = {"date": [dates[i] for i in pos_idx], "h": np.array([gas[x][0] for x in hist_dates]),
       "rs": d["simple"]["sbk"][pos_idx], "rb": np.mean([d["simple"][k] for k in ["fsr", "abg", "ned", "cpi"]], axis=0)[pos_idx]}
res = evaluate(sig, "H1 rule on the GAS copula h (reported)", ["design", "validation", "post-freeze"], note="H9 reported figure, not a pass mark", log=True)
show(res, "rule on GAS h")
static = {r["date"]: float(r["h"]) for r in rows if r["model"] == "static_t"}
sig_s = dict(sig, h=np.array([static[x] for x in hist_dates]))
res_s = evaluate(sig_s, "H1 rule on the static h (comparison)", ["design", "validation", "post-freeze"], note="baseline for H9 paired comparison", log=True)
show(res_s, "rule on static h")
pg, ps = positions(sig["h"]), positions(sig_s["h"])
ng, ns = net_returns(pg, sig["rs"], sig["rb"]), net_returns(ps, sig_s["rs"], sig_s["rb"])
cmp = {}
for pname, (a, b) in PERIODS.items():
    m = np.array([a <= x.isoformat() < b for x in sig["date"]])
    cmp[pname] = paired_t(ng[m], ns[m]); print(pname, "GAS rule vs static rule:", cmp[pname])
json.dump({"gas": res, "static": res_s, "vs_static": cmp}, open("research/results/h9_rule.json", "w"), indent=1)
