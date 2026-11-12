"""Build the development frame (to 2026-03-31): returns, PITs, GAS h both ways, rho, sigma, z, EG."""
import sys, json, csv, math
import numpy as np
sys.path.insert(0, "research"); sys.path.insert(0, "research/models"); sys.path.insert(0, "service")
import copulas_py as C
from app.model import h_func
from app import switch as SW
END = "2026-03-31"
d = C.d; dates = [x.isoformat() for x in d["date"]]
N = sum(1 for x in dates if x <= END)
folds = C.folds; ends = C.ends
G = json.load(open("research/results/h17.json"))["gas_by_refit"]
rows = {k: np.full(N, np.nan) for k in ("u", "v", "h", "h2", "rho", "fold", "sig_s", "sig_n", "mu_s", "mu_n", "nu")}
for k, f in enumerate(folds):
    te = f["train_end"]
    n_train = sum(1 for x in dates if x <= te)
    n_all = sum(1 for x in dates if x <= ends[k + 1]) if k + 1 < len(folds) else len(dates)
    n_all = min(n_all, N)
    if n_all <= n_train: continue
    fs = C._filter_full(f["sbk"], d["r_sbk"][:n_all], d["vix"][:n_all], n_train)
    fn = C._filter_full(f["ned"], d["r_ned"][:n_all], d["vix"][:n_all], n_train)
    u = np.clip(fs["u"], C.CL, 1 - C.CL); v = np.clip(fn["u"], C.CL, 1 - C.CL)
    p = G[te]
    fr, _, _ = C.gas_filter(u, v, p["omega"], p["beta"], p["alpha"], p["nu"], p["omega"] / max(1 - p["beta"], 1e-3))
    rho = np.tanh(fr); sl = slice(n_train, n_all)
    rows["u"][sl] = u[sl]; rows["v"][sl] = v[sl]; rows["rho"][sl] = rho[sl]; rows["fold"][sl] = k + 1; rows["nu"][sl] = p["nu"]
    rows["h"][sl] = [h_func(2, np.array([u[t]]), np.array([v[t]]), rho[t], p["nu"])[0] for t in range(n_train, n_all)]
    rows["h2"][sl] = [h_func(2, np.array([v[t]]), np.array([u[t]]), rho[t], p["nu"])[0] for t in range(n_train, n_all)]
    rows["sig_s"][sl] = fs["sigma"][sl]; rows["sig_n"][sl] = fn["sigma"][sl]; rows["mu_s"][sl] = fs["mu"][sl]; rows["mu_n"][sl] = fn["mu"][sl]
# parity with stored csv
ref = {r["date"]: float(r["h"]) for r in csv.DictReader(open("research/results/copulas_py.csv")) if r["model"] == "gas_t"}
diff = [abs(rows["h"][i] - ref[dates[i]]) for i in range(N) if dates[i] in ref and not np.isnan(rows["h"][i])]
print("parity max |dh|", max(diff), len(diff))
rs, rn = np.expm1(d["r_sbk"][:N]), np.expm1(d["r_ned"][:N])
x, y = np.cumsum(d["r_sbk"][:N]), np.cumsum(d["r_ned"][:N])
b, z, eg = SW.rolling(x, y)
np.savez("/tmp/jse-review/copula/base.npz", dates=np.array(dates[:N]), rs=rs, rn=rn, b=b, z=z, eg=eg, **rows)
print("saved", N, dates[0], dates[N - 1])
