"""H9: GAS (and, reported, Markov-switching) Student t copulas on the basket instrument's monthly fits.
Writes research/results/copulas_basket.csv with the static, GAS and MS log copula scores and h per day."""
import csv, json, math, sys, time
import numpy as np
from joblib import Parallel, delayed
sys.path.insert(0, "research"); sys.path.insert(0, "research/models"); sys.path.insert(0, "service")
from h5_weights import load, month_ends, _filter_full  # noqa: E402
from copulas_py import t_logc, gas_fit, gas_score, ms_fit, ms_score  # noqa: E402
from app.model import h_func  # noqa: E402

d = load(); dates = d["date"]; n = len(dates)
B = json.load(open("data/basket.json")); fits = {f["train_end"]: f for f in B["fits"]}
ends = [e for e in month_ends(dates) if e.isoformat() in fits]
CL = 1e-6


def one(k):
    te = ends[k]; f = fits[te.isoformat()]
    n_train = sum(1 for x in dates if x <= te)
    n_all = sum(1 for x in dates if x <= ends[k + 1]) if k + 1 < len(ends) else n
    if n_all <= n_train:
        return []
    fs = _filter_full(f["sbk"], d["r_sbk"][:n_all], d["vix"][:n_all], n_train)
    fb = _filter_full(f["bsk"], d["r_bsk"][:n_all], d["vix"][:n_all], n_train)
    u, v = np.clip(fs["u"], CL, 1 - CL), np.clip(fb["u"], CL, 1 - CL)
    sl = slice(n_train, n_all); td = [dates[t].isoformat() for t in range(n_train, n_all)]
    rho, nu = f["copula"]["par"], f["copula"]["par2"]
    rows = [(dd, k + 1, "static_t", a, b, rho) for dd, a, b in zip(td, t_logc(u[sl], v[sl], rho, nu), h_func(2, u[sl], v[sl], rho, nu))]
    pg = gas_fit(u[:n_train], v[:n_train], rho)
    lc, h, rho_t, _ = gas_score(pg, u[:n_all], v[:n_all], n_train)
    rows += [(dd, k + 1, "gas_t", a, b, c) for dd, a, b, c in zip(td, lc, h, rho_t)]
    pm = ms_fit(u[:n_train], v[:n_train], rho)
    lc, h, p2, _ = ms_score(pm, u[:n_all], v[:n_all], n_train)
    rows += [(dd, k + 1, "ms_t", a, b, c) for dd, a, b, c in zip(td, lc, h, p2)]
    return rows


t0 = time.time()
res = Parallel(n_jobs=-1, verbose=5)(delayed(one)(k) for k in range(len(ends)))
rows = [r for rr in res for r in rr]
with open("research/results/copulas_basket.csv", "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["date", "fold", "model", "logc", "h", "state"])
    for r in rows:
        w.writerow([r[0], r[1], r[2], f"{r[3]:.6f}", f"{r[4]:.8f}", f"{r[5]:.5f}"])
print(f"wrote {len(rows)} rows in {time.time()-t0:.0f}s")
