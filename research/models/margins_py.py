"""Margin models for SBK and NED, yearly walk-forward as in the pair's folds: one-step-ahead log
predictive densities and PITs out of sample.

(a) baseline: the walk-forward's BIC-chosen ARMA-GARCH, re-filtered from the stored coefficients;
(b) Beta-t-EGARCH with leverage (Harvey, 2013), fitted by maximum likelihood on each fold's training data.
Writes research/results/margins_py.csv.
"""
import csv, json, math, sys, time
import numpy as np
from scipy import stats as st, optimize
sys.path.insert(0, "research"); sys.path.insert(0, "research/models"); sys.path.insert(0, "service")
from pairdata import load_pair  # noqa: E402
from h5_weights import _filter_full  # noqa: E402

d = load_pair()
dates = d["date"]; n = len(dates)
W = json.load(open("data/walkforward.json"))
folds = W["folds"]
hist = W["history"]
hist_u = {dd: (u, v) for dd, u, v in zip(hist["date"], hist["u"], hist["v"])}
ends = [f["train_end"] for f in folds]


def windows():
    for k, f in enumerate(folds):
        te = f["train_end"]
        n_train = sum(1 for x in dates if x.isoformat() <= te)
        n_all = sum(1 for x in dates if x.isoformat() <= ends[k + 1]) if k + 1 < len(folds) else n
        yield f, n_train, n_all


def logf_std(r, mu, sigma, dist, shape):
    z = (r - mu) / sigma
    if dist == "std":
        s = math.sqrt(shape / (shape - 2))
        return st.t.logpdf(z * s, shape) + math.log(s) - np.log(sigma), st.t.cdf(z * s, shape)
    return st.norm.logpdf(z) - np.log(sigma), st.norm.cdf(z)


# ---- Beta-t-EGARCH with leverage -----------------------------------------------------------
def bte_filter(y, mu, omega, phi, kappa, kstar, nu):
    lam = np.empty(len(y)); l = omega
    for t in range(len(y)):
        lam[t] = l
        e = (y[t] - mu) * math.exp(-l)
        u = (nu + 1) * e * e / (nu + e * e) - 1
        l = omega * (1 - phi) + phi * l + kappa * u + kstar * (-1 if e > 0 else 1) * (u + 1)
    return lam


def bte_unpack(p):
    mu, omega, a, kappa, kstar, b = p
    return mu, omega, 1 / (1 + math.exp(-a)), kappa, kstar, 2 + math.exp(b)


def bte_nll(p, y):
    mu, omega, phi, kappa, kstar, nu = bte_unpack(p)
    lam = bte_filter(y, mu, omega, phi, kappa, kstar, nu)
    e = (y - mu) * np.exp(-lam)
    return -float(np.sum(st.t.logpdf(e, nu) - lam))


def bte_fit(y):
    p0 = np.array([y.mean(), math.log(y.std()), 4.0, 0.05, 0.02, math.log(6.0)])
    res = optimize.minimize(bte_nll, p0, args=(y,), method="Nelder-Mead", options={"maxiter": 4000, "xatol": 1e-5, "fatol": 1e-6})
    return res.x, -res.fun


def bte_score(p, y, n_train):
    mu, omega, phi, kappa, kstar, nu = bte_unpack(p)
    lam = bte_filter(y, mu, omega, phi, kappa, kstar, nu)
    e = (y - mu) * np.exp(-lam)
    return (st.t.logpdf(e, nu) - lam)[n_train:], st.t.cdf(e, nu)[n_train:], dict(mu=mu, omega=omega, phi=phi, kappa=kappa, kstar=kstar, nu=nu)


rows = []
t0 = time.time()
parity = []
for f, n_train, n_all in windows():
    sl = slice(n_train, n_all)
    for series in ("sbk", "ned"):
        r = d[f"r_{series}"]
        # baseline
        fm = _filter_full(f[series], r[:n_all], d["vix"][:n_all], n_train)
        lf, u = logf_std(r[sl], fm["mu"][sl], fm["sigma"][sl], f[series]["dist"], f[series]["coef"].get("shape"))
        for i, t in enumerate(range(n_train, n_all)):
            rows.append((dates[t].isoformat(), f["id"], series, "arma_garch_bic", lf[i], u[i]))
            if dates[t].isoformat() in hist_u:
                parity.append(abs(u[i] - hist_u[dates[t].isoformat()][0 if series == "sbk" else 1]))
        # Beta-t-EGARCH
        p, ll = bte_fit(r[:n_train])
        lf2, u2, par = bte_score(p, r[:n_all], n_train)
        for i, t in enumerate(range(n_train, n_all)):
            rows.append((dates[t].isoformat(), f["id"], series, "beta_t_egarch", lf2[i], u2[i]))
    print(f"fold {f['id']:2d} to {f['train_end']}  bte {series} phi {par['phi']:.3f} kappa {par['kappa']:.3f} kstar {par['kstar']:.3f} nu {par['nu']:.1f}  ({time.time()-t0:.0f}s)")
print("baseline PIT parity vs walkforward.json: max |du| = %.2e over %d days" % (max(parity), len(parity)))
with open("research/results/margins_py.csv", "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["date", "fold", "series", "model", "logf", "u"])
    for row in rows:
        w.writerow([row[0], row[1], row[2], row[3], f"{row[4]:.6f}", f"{row[5]:.8f}"])
# design summary
for series in ("sbk", "ned"):
    for model in ("arma_garch_bic", "beta_t_egarch"):
        x = [(r[4], r[5]) for r in rows if r[2] == series and r[3] == model and "2010-01-01" <= r[0] < "2020-01-01"]
        lf = np.array([a for a, _ in x]); u = np.array([b for _, b in x])
        print(f"design {series} {model:16s} mean logf {lf.mean():.4f}  n {len(lf)}  PIT KS p {st.kstest(u, 'uniform').pvalue:.3f}")
