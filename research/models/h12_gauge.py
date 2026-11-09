"""H12: a market volatility gauge in the pair's copula (research/PROTOCOL.md).

For each gauge x (known before the session it is used for, logged and standardised on the fold's training years):
f_t = omega + beta f_{t-1} + alpha s_{t-1} + gamma x_t, rho_t = tanh f_t, nu_t = 2 + exp(eta0 + eta1 x_t).
Nests H8 (gamma = eta1 = 0); each fit starts from the fold's H8 fit. Writes research/results/h12.json and h12_daily.csv.

Usage: python research/models/h12_gauge.py   (about ten minutes on eight cores)
Rand prints: Yahoo's ZAR=X has one-day spikes that reverse (Nov 2024, Jan 2025); a print more than 7% from the
previous kept print and followed by one within 3% of that previous print is dropped.
"""
import csv, json, math, sys, time
import datetime as dt
import numpy as np
from scipy import stats as st, optimize, special
from joblib import Parallel, delayed
sys.path.insert(0, "research"); sys.path.insert(0, "research/models"); sys.path.insert(0, "service")
from copulas_py import d, dates, n, folds, ends, pits, gas_fit, gas_score, t_score_rho  # noqa: E402

DESIGN, VALID, FREEZE = ("2010-01-01", "2020-01-01"), ("2020-01-01", "2026-04-01"), "2026-04-01"
WIN = 20


def nw_t(x, lags=5):
    x = np.asarray(x); mu = x.mean(); T = len(x); e = x - mu
    v = e @ e / T + 2 * sum((1 - k / (lags + 1)) * (e[k:] @ e[:-k]) / T for k in range(1, lags + 1))
    return float(mu / math.sqrt(v / T))


def read_series(path):
    rows = []
    for r in csv.DictReader(open(path)):
        try:
            rows.append((dt.date.fromisoformat(r["date"]), float(r["adjusted"])))
        except ValueError:
            pass
    return sorted(rows)


def clean_spikes(rows, jump=0.07, back=0.03):
    keep = [rows[0]]
    for i in range(1, len(rows)):
        prev = keep[-1][1]; a = rows[i][1]
        if i + 1 < len(rows) and abs(math.log(a / prev)) > jump and abs(math.log(rows[i + 1][1] / prev)) < back:
            continue
        keep.append(rows[i])
    return keep


def rv_before(rows, strictly_before):
    """20-observation realised volatility of log changes, using prints dated before each session."""
    ds = np.array([x.toordinal() for x, _ in rows]); lr = np.diff(np.log([p for _, p in rows]))
    out = np.full(n, np.nan)
    for t, day in enumerate(dates):
        j = np.searchsorted(ds, day.toordinal(), side="left") - 1 if strictly_before else t  # index of last print < session
        if j >= WIN:
            out[t] = lr[j - WIN:j].std(ddof=1)
    return out


def build_gauges():
    g = {"vix": np.log(d["vix"])}
    zar_rows = clean_spikes(read_series("data/raw/zar.csv"))
    g["zar"] = np.log(rv_before(zar_rows, True))
    eq = 0.5 * (d["r_sbk"] + d["r_ned"])
    own = np.full(n, np.nan)
    for t in range(WIN, n):
        own[t] = eq[t - WIN:t].std(ddof=1)  # sessions before t
    g["own"] = np.log(own)
    top = read_series("data/raw/top40.csv")
    dropped = {"top40": f"history starts {top[0][0].isoformat()}, not 2005"} if top[0][0] > dt.date(2005, 1, 31) else {}
    return g, dropped, len(read_series("data/raw/zar.csv")) - len(zar_rows)


GAUGES, DROPPED, ZAR_DROPPED = build_gauges()


def x_filter(p, u, v, x):
    omega, beta, alpha = p[0], 1 / (1 + math.exp(-p[1])), math.exp(p[2])
    eta0, gamma, eta1 = p[3], p[4], p[5]
    nu = 2 + np.exp(np.clip(eta0 + eta1 * x, -3, 6))
    xs, ys = st.t.ppf(u, nu), st.t.ppf(v, nu)
    f = np.empty(len(u)); prev = omega / max(1 - beta, 1e-3); s = 0.0
    for t in range(len(u)):
        ft = omega + beta * prev + alpha * s + gamma * x[t] if t else prev + gamma * x[t]
        ft = max(min(ft, 4.0), -4.0); f[t] = ft
        rho = math.tanh(ft)
        s = t_score_rho(xs[t], ys[t], rho, nu[t]) * (1 - rho * rho)
        prev = ft
    rho = np.tanh(f)
    q = (xs * xs - 2 * rho * xs * ys + ys * ys) / (1 - rho * rho)
    lf2 = special.gammaln((nu + 2) / 2) - special.gammaln(nu / 2) - np.log(nu * math.pi) - 0.5 * np.log(1 - rho * rho) - (nu + 2) / 2 * np.log1p(q / nu)
    logc = lf2 - st.t.logpdf(xs, nu) - st.t.logpdf(ys, nu)
    h = st.t.cdf((ys - rho * xs) / np.sqrt((nu + xs * xs) * (1 - rho * rho) / (nu + 1)), nu + 1)
    return logc, np.clip(h, 1e-10, 1 - 1e-10), rho, nu


def fit_fold(k):
    f = folds[k]; te = f["train_end"]
    n_train = sum(1 for x in dates if x.isoformat() <= te)
    n_all = sum(1 for x in dates if x.isoformat() <= ends[k + 1]) if k + 1 < len(folds) else n
    if n_all <= n_train:
        return None
    u, v = pits(f, n_all, n_train)
    pg = gas_fit(u[:n_train], v[:n_train], f["copula"]["par"])
    lc_g, h_g, _, par_g = gas_score(pg, u[:n_all], v[:n_all], n_train)
    out = {"fold": k + 1, "train_end": te, "dates": [dates[t].isoformat() for t in range(n_train, n_all)],
           "h8": {"logc": lc_g.tolist(), "h": h_g.tolist()}, "fits": {}}
    p0 = [pg[0], pg[1], pg[2], math.log(par_g["nu"] - 2), 0.0, 0.0]
    for name, raw in GAUGES.items():
        tr = raw[:n_train]; mu, sd = np.nanmean(tr), np.nanstd(tr)
        x = np.nan_to_num((raw[:n_all] - mu) / sd, nan=0.0)
        nll = lambda p: -float(np.sum(x_filter(p, u[:n_train], v[:n_train], x[:n_train])[0]))
        res = optimize.minimize(nll, p0, method="Nelder-Mead", options={"maxiter": 4000, "xatol": 1e-4, "fatol": 1e-4})
        p = res.x if res.fun <= nll(p0) else np.array(p0)
        lc, h, rho, nu = x_filter(p, u[:n_all], v[:n_all], x)
        out["fits"][name] = {"logc": lc[n_train:].tolist(), "h": h[n_train:].tolist(), "gamma": float(p[4]), "eta1": float(p[5]),
                             "beta": float(1 / (1 + math.exp(-p[1]))), "nu_mean": float(nu[:n_train].mean()), "train_gain": float(nll(p0) - res.fun)}
    return out


def span(ds, a, b):
    return np.array([a <= x < b for x in ds])


if __name__ == "__main__":
    t0 = time.time()
    res = [r for r in Parallel(n_jobs=8, verbose=5)(delayed(fit_fold)(k) for k in range(len(folds))) if r]
    ds = sum((r["dates"] for r in res), [])
    base = np.concatenate([r["h8"]["logc"] for r in res])
    # parity: the refitted H8 must reproduce the stored H8 scores
    stored = {r["date"]: float(r["logc"]) for r in csv.DictReader(open("research/results/copulas_py.csv")) if r["model"] == "gas_t"}
    parity = max(abs(stored[x] - b) for x, b in zip(ds, base) if x in stored)
    out = {"dropped": DROPPED, "zar_prints_dropped": ZAR_DROPPED, "h8_parity_max_abs": parity, "gauges": {}}
    yrs = np.array([int(x[:4]) for x in ds])
    for name in GAUGES:
        lc = np.concatenate([r["fits"][name]["logc"] for r in res]); h = np.concatenate([r["fits"][name]["h"] for r in res])
        rec = {"by_fold": [{"train_end": r["train_end"], **{k: round(r["fits"][name][k], 4) for k in ("gamma", "eta1", "beta", "nu_mean", "train_gain")}} for r in res]}
        for nm, (a, b) in (("design", DESIGN), ("validation", VALID), ("post_freeze", (FREEZE, "2100"))):
            m = span(ds, a, b); dlt = lc[m] - base[m]
            rec[nm] = {"n": int(m.sum()), "gain_per_day_x1000": round(float(dlt.mean() * 1000), 2), "dm_t": round(nw_t(dlt), 2) if m.sum() > 10 else None,
                       "h_ks_p": round(float(st.kstest(h[m], "uniform").pvalue), 3)}
        out["gauges"][name] = rec
    hb = np.concatenate([r["h8"]["h"] for r in res])
    out["h8_h_ks_p"] = {nm: round(float(st.kstest(hb[span(ds, a, b)], "uniform").pvalue), 3) for nm, (a, b) in (("design", DESIGN), ("validation", VALID))}
    best = max(GAUGES, key=lambda g: out["gauges"][g]["design"]["gain_per_day_x1000"])
    chosen = best if out["gauges"][best]["design"]["dm_t"] > 2 else None
    out["chosen"] = chosen
    out["verdict"] = ("stopped at design: no gauge beat H8 by DM t > 2" if chosen is None else
                      ("pass" if out["gauges"][chosen]["validation"]["dm_t"] > 1.96 else "fail on validation"))
    with open("research/results/h12_daily.csv", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["date", "h8_logc", "h8_h"] + [f"{g}_{c}" for g in GAUGES for c in ("logc", "h")])
        cols = [base, hb] + [np.concatenate([r["fits"][g][c] for r in res]) for g in GAUGES for c in ("logc", "h")]
        for i, x in enumerate(ds):
            w.writerow([x] + [f"{c[i]:.8f}" for c in cols])
    json.dump(out, open("research/results/h12.json", "w"), indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != "gauges"}))
    for g, r in out["gauges"].items():
        print(g, {k: r[k] for k in ("design", "validation", "post_freeze")})
    print(f"done in {time.time() - t0:.0f}s")
