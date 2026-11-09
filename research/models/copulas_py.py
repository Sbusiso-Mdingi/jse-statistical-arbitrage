"""Dependence models on the baseline margins' PITs for the SBK/NED pair, yearly folds.

(a) static Student t copula per fold (the walk-forward's own parameters);
(b) Student t copula refitted on a rolling 252-day window at each month end;
(c) GAS Student t copula: correlation driven by the scaled score (Creal, Koopman and Lucas, 2013);
(d) two-state Markov-switching Student t copula (Hamilton filter).
Out-of-sample one-step log copula densities and the conditional probability h = P(V <= v | U = u)
to research/results/copulas_py.csv.
"""
import csv, json, math, sys, time
import numpy as np
from scipy import stats as st, optimize, special
sys.path.insert(0, "research"); sys.path.insert(0, "research/models"); sys.path.insert(0, "service")
from pairdata import load_pair  # noqa: E402
from h5_weights import _filter_full  # noqa: E402
from app.model import h_func  # noqa: E402

d = load_pair(); dates = d["date"]; n = len(dates)
W = json.load(open("data/walkforward.json")); folds = W["folds"]; ends = [f["train_end"] for f in folds]
CL = 1e-6


def pits(f, n_all, n_train):
    out = []
    for s in ("sbk", "ned"):
        fm = _filter_full(f[s], d[f"r_{s}"][:n_all], d["vix"][:n_all], n_train)
        out.append(np.clip(fm["u"], CL, 1 - CL))
    return out


# ---- Student t copula pieces ---------------------------------------------------------------
def t_logc(u, v, rho, nu):
    x, y = st.t.ppf(u, nu), st.t.ppf(v, nu)
    q = (x * x - 2 * rho * x * y + y * y) / (1 - rho * rho)
    lf2 = special.gammaln((nu + 2) / 2) - special.gammaln(nu / 2) - math.log(nu * math.pi) - 0.5 * math.log(1 - rho * rho) - (nu + 2) / 2 * np.log1p(q / nu)
    return lf2 - st.t.logpdf(x, nu) - st.t.logpdf(y, nu)


def t_score_rho(x, y, rho, nu):
    """d log c / d rho at given t-quantiles."""
    r2 = 1 - rho * rho
    q = (x * x - 2 * rho * x * y + y * y) / r2
    dq = (-2 * x * y * r2 + 2 * rho * (x * x - 2 * rho * x * y + y * y)) / (r2 * r2)
    return rho / r2 - (nu + 2) / 2 * dq / (nu + q)


def fit_static(u, v):
    def nll(p):
        rho, nu = math.tanh(p[0]), 2 + math.exp(p[1])
        return -float(np.sum(t_logc(u, v, rho, nu)))
    tau = st.kendalltau(u, v).statistic
    res = optimize.minimize(nll, [math.atanh(math.sin(math.pi * tau / 2)), math.log(6)], method="Nelder-Mead", options={"xatol": 1e-4, "fatol": 1e-4})
    return math.tanh(res.x[0]), 2 + math.exp(res.x[1])


# ---- GAS t copula -----------------------------------------------------------------------------
def gas_filter(u, v, omega, beta, alpha, nu, f0):
    x, y = st.t.ppf(u, nu), st.t.ppf(v, nu)
    f = np.empty(len(u)); ft = f0
    for t in range(len(u)):
        f[t] = ft
        rho = math.tanh(ft)
        s = t_score_rho(x[t], y[t], rho, nu) * (1 - rho * rho)  # chain rule through tanh, identity scaling
        ft = omega + beta * ft + alpha * s
        ft = max(min(ft, 4.0), -4.0)
    return f, x, y


def gas_unpack(p):
    return p[0], 1 / (1 + math.exp(-p[1])), math.exp(p[2]), 2 + math.exp(p[3])


def gas_nll(p, u, v):
    omega, beta, alpha, nu = gas_unpack(p)
    f, x, y = gas_filter(u, v, omega, beta, alpha, nu, omega / max(1 - beta, 1e-3))
    rho = np.tanh(f)
    q = (x * x - 2 * rho * x * y + y * y) / (1 - rho * rho)
    lf2 = special.gammaln((nu + 2) / 2) - special.gammaln(nu / 2) - math.log(nu * math.pi) - 0.5 * np.log(1 - rho * rho) - (nu + 2) / 2 * np.log1p(q / nu)
    return -float(np.sum(lf2 - st.t.logpdf(x, nu) - st.t.logpdf(y, nu)))


def gas_fit(u, v, rho0):
    f_bar = math.atanh(rho0)
    p0 = [f_bar * (1 - 0.97), 3.5, math.log(0.03), math.log(6)]
    res = optimize.minimize(gas_nll, p0, args=(u, v), method="Nelder-Mead", options={"maxiter": 3000, "xatol": 1e-4, "fatol": 1e-4})
    return res.x


def gas_score(p, u, v, n_train):
    omega, beta, alpha, nu = gas_unpack(p)
    f, x, y = gas_filter(u, v, omega, beta, alpha, nu, omega / max(1 - beta, 1e-3))
    rho = np.tanh(f)
    logc = np.array([t_logc(np.array([u[t]]), np.array([v[t]]), rho[t], nu)[0] for t in range(n_train, len(u))])
    h = np.array([h_func(2, np.array([u[t]]), np.array([v[t]]), rho[t], nu)[0] for t in range(n_train, len(u))])
    return logc, h, rho[n_train:], dict(omega=omega, beta=beta, alpha=alpha, nu=nu)


# ---- Markov-switching t copula ---------------------------------------------------------------
def ms_unpack(p):
    return math.tanh(p[0]), math.tanh(p[1]), 2 + math.exp(p[2]), 1 / (1 + math.exp(-p[3])), 1 / (1 + math.exp(-p[4]))


def ms_filter(u, v, rho1, rho2, nu, p11, p22):
    """Hamilton filter. Returns predictive state probabilities (before seeing t) and per-state log densities."""
    l1, l2 = t_logc(u, v, rho1, nu), t_logc(u, v, rho2, nu)
    pred = np.empty((len(u), 2))
    pi = np.array([(1 - p22) / (2 - p11 - p22), (1 - p11) / (2 - p11 - p22)])
    P = np.array([[p11, 1 - p11], [1 - p22, p22]])
    for t in range(len(u)):
        pred[t] = pi
        lik = pi * np.array([math.exp(l1[t]), math.exp(l2[t])])
        post = lik / max(lik.sum(), 1e-300)
        pi = post @ P
    return pred, l1, l2


def ms_nll(p, u, v):
    rho1, rho2, nu, p11, p22 = ms_unpack(p)
    pred, l1, l2 = ms_filter(u, v, rho1, rho2, nu, p11, p22)
    mix = pred[:, 0] * np.exp(l1) + pred[:, 1] * np.exp(l2)
    return -float(np.sum(np.log(np.maximum(mix, 1e-300))))


def ms_fit(u, v, rho0):
    p0 = [math.atanh(max(rho0 - 0.15, 0.05)), math.atanh(min(rho0 + 0.12, 0.95)), math.log(6), 3.0, 3.0]
    res = optimize.minimize(ms_nll, p0, args=(u, v), method="Nelder-Mead", options={"maxiter": 4000, "xatol": 1e-4, "fatol": 1e-4})
    return res.x


def ms_score(p, u, v, n_train):
    rho1, rho2, nu, p11, p22 = ms_unpack(p)
    pred, l1, l2 = ms_filter(u, v, rho1, rho2, nu, p11, p22)
    sl = slice(n_train, len(u))
    mix = pred[sl, 0] * np.exp(l1[sl]) + pred[sl, 1] * np.exp(l2[sl])
    h = pred[sl, 0] * h_func(2, u[sl], v[sl], rho1, nu) + pred[sl, 1] * h_func(2, u[sl], v[sl], rho2, nu)
    return np.log(mix), h, pred[sl, 1], dict(rho1=rho1, rho2=rho2, nu=nu, p11=p11, p22=p22)


if __name__ == "__main__":
    rows = []
    t0 = time.time()
    for k, f in enumerate(folds):
        te = f["train_end"]
        n_train = sum(1 for x in dates if x.isoformat() <= te)
        n_all = sum(1 for x in dates if x.isoformat() <= ends[k + 1]) if k + 1 < len(folds) else n
        if n_all <= n_train:
            continue
        u, v = pits(f, n_all, n_train)
        sl = slice(n_train, n_all)
        test_dates = [dates[t].isoformat() for t in range(n_train, n_all)]
        # (a) static, the walk-forward's own parameters
        rho, nu = f["copula"]["par"], f["copula"]["par2"]
        lc = t_logc(u[sl], v[sl], rho, nu); h = h_func(2, u[sl], v[sl], rho, nu)
        rows += [(dd, k + 1, "static_t", a, b, rho) for dd, a, b in zip(test_dates, lc, h)]
        # (b) rolling 252-day refit at each month end inside the test window
        months = sorted({dd[:7] for dd in test_dates})
        for m in months:
            idx = [t for t in range(n_train, n_all) if dates[t].isoformat()[:7] == m]
            start = idx[0]
            r_m, nu_m = fit_static(u[start - 252:start], v[start - 252:start])
            lc = t_logc(u[idx], v[idx], r_m, nu_m); h = h_func(2, u[idx], v[idx], r_m, nu_m)
            rows += [(dates[t].isoformat(), k + 1, "rolling_t_252", a, b, r_m) for t, a, b in zip(idx, lc, h)]
        # (c) GAS t copula fitted on training PITs, filtered through the test window
        pg = gas_fit(u[:n_train], v[:n_train], rho)
        lc, h, rho_t, par_g = gas_score(pg, u[:n_all], v[:n_all], n_train)
        rows += [(dd, k + 1, "gas_t", a, b, c) for dd, a, b, c in zip(test_dates, lc, h, rho_t)]
        # (d) Markov-switching t copula
        pm = ms_fit(u[:n_train], v[:n_train], rho)
        lc, h, p2, par_m = ms_score(pm, u[:n_all], v[:n_all], n_train)
        rows += [(dd, k + 1, "ms_t", a, b, c) for dd, a, b, c in zip(test_dates, lc, h, p2)]
        print(f"fold {k+1:2d} to {te}: static rho {rho:.3f} nu {nu:.1f} | gas beta {par_g['beta']:.3f} alpha {par_g['alpha']:.3f} nu {par_g['nu']:.1f} | ms rho {par_m['rho1']:.2f}/{par_m['rho2']:.2f} p11 {par_m['p11']:.3f} p22 {par_m['p22']:.3f} nu {par_m['nu']:.1f}  ({time.time()-t0:.0f}s)", flush=True)

    with open("research/results/copulas_py.csv", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["date", "fold", "model", "logc", "h", "state"])
        for r in rows:
            w.writerow([r[0], r[1], r[2], f"{r[3]:.6f}", f"{r[4]:.8f}", f"{r[5]:.5f}"])
    for model in ("static_t", "rolling_t_252", "gas_t", "ms_t"):
        x = [(r[3], r[4]) for r in rows if r[2] == model and "2010-01-01" <= r[0] < "2020-01-01"]
        lc = np.array([a for a, _ in x]); h = np.array([b for _, b in x])
        print(f"design {model:14s} mean logc {lc.mean():.4f}  n {len(lc)}  h KS p {st.kstest(h, 'uniform').pvalue:.3f}  fires {100*np.mean(np.abs(h-0.5) > 0.45):.1f}%")
