"""H11: a direct repair to the Nedbank margin (research/PROTOCOL.md, H11). Design-only diagnosis and choice,
then a forecast check on validation. No trading figure is computed here.

Usage: python research/h11_ned_repair.py [design|validation]
Writes research/results/h11.json (merging stages).
"""
import json, math, os, sys
import numpy as np
from scipy import stats as st, optimize
sys.path.insert(0, "research"); sys.path.insert(0, "research/models"); sys.path.insert(0, "service")
from pairdata import load_pair  # noqa: E402
from h5_weights import _filter_full, edit_spec  # noqa: E402

OUT = "research/results/h11.json"
d = load_pair(); dates = d["date"]; n = len(dates)
W = json.load(open("data/walkforward.json")); folds = W["folds"]; ends = [f["train_end"] for f in folds]
hist = W["history"]; hv = dict(zip(hist["date"], hist["v"]))
DESIGN, VALID = ("2010-01-01", "2020-01-01"), ("2020-01-01", "2026-04-01")


def save(section, payload):
    cur = json.load(open(OUT)) if os.path.exists(OUT) else {}
    cur[section] = payload
    json.dump(cur, open(OUT, "w"), indent=1)


def windows():
    for k, f in enumerate(folds):
        n_train = sum(1 for x in dates if x.isoformat() <= f["train_end"])
        n_all = sum(1 for x in dates if x.isoformat() <= ends[k + 1]) if k + 1 < len(folds) else n
        if n_all > n_train:
            yield k, f, n_train, n_all


def logf_std(r, mu, sigma, dist, shape):
    """Log density and PIT of a return under a location-scale margin (as research/models/margins_py.py)."""
    z = (r - mu) / sigma
    if dist == "std":
        s = math.sqrt(shape / (shape - 2))
        return st.t.logpdf(z * s, shape) + math.log(s) - np.log(sigma), st.t.cdf(z * s, shape)
    return st.norm.logpdf(z) - np.log(sigma), st.norm.cdf(z)


def std_tail(nu, c=3.0):
    """P(|z| > c) for a unit-variance Student t with nu degrees of freedom."""
    s = math.sqrt(nu / (nu - 2))
    return 2 * st.t.sf(c * s, nu)


def nu_for_tail(p, c=3.0, lo=3.25, hi=500.0):
    """Degrees of freedom matching the share beyond c sd (PROTOCOL.md, H11 amendment)."""
    if p <= 2 * st.norm.sf(c):
        return None  # thinner than the normal: keep the fitted distribution
    if p >= std_tail(lo, c):
        return lo
    if p <= std_tail(hi, c):
        return hi
    return optimize.brentq(lambda nu: std_tail(nu, c) - p, lo, hi)


def edited(spec, fm, n_train, r, vix, n_all, kind):
    """(mu, sigma, dist, shape) on the test slice under an edit set from this fold's training residuals."""
    sl = slice(n_train, n_all)
    c = spec["coef"]; dist, shape = spec["dist"], c.get("shape")
    zt = fm["z"][:n_train]
    if kind == "none":
        return fm["mu"][sl], fm["sigma"][sl], dist, shape, {}
    if kind == "scale":
        k = float(np.var(zt))
        return fm["mu"][sl], fm["sigma"][sl] * math.sqrt(k), dist, shape, {"variance_ratio": round(k, 4)}
    if kind == "shape":
        p = float(np.mean(np.abs(zt) > 3))
        nu = nu_for_tail(p)
        if nu is None:
            return fm["mu"][sl], fm["sigma"][sl], dist, shape, {"tail_freq": round(p, 4), "nu": None}
        return fm["mu"][sl], fm["sigma"][sl], "std", nu, {"tail_freq": round(p, 4), "nu": round(nu, 2), "was": shape}
    if kind == "location":
        s2 = edit_spec(spec, lambda cc: {**cc, "ar1": 0.0, "ma1": 0.0})
        g = _filter_full(s2, r[:n_all], vix[:n_all], n_train)
        return g["mu"][sl], g["sigma"][sl], dist, shape, {"arma_was": spec["arma"]}
    raise ValueError(kind)


def nw_t(x, lags=5):
    x = np.asarray(x); mu = x.mean(); T = len(x); e = x - mu
    v = e @ e / T + 2 * sum((1 - k / (lags + 1)) * (e[k:] @ e[:-k]) / T for k in range(1, lags + 1))
    return float(mu / math.sqrt(v / T))


KINDS = ("none", "scale", "shape", "location")


def collect():
    rows = {k: {"date": [], "u": [], "logf": []} for k in KINDS}
    info = {k: [] for k in KINDS}
    parity = 0.0
    for k, f, n_train, n_all in windows():
        spec = f["ned"]
        fm = _filter_full(spec, d["r_ned"][:n_all], d["vix"][:n_all], n_train)
        r = d["r_ned"][n_train:n_all]
        td = [x.isoformat() for x in dates[n_train:n_all]]
        for kind in KINDS:
            mu, sig, dist, shape, meta = edited(spec, fm, n_train, d["r_ned"], d["vix"], n_all, kind)
            lf, u = logf_std(r, mu, sig, dist, shape)
            rows[kind]["date"] += td; rows[kind]["u"].append(np.clip(u, 1e-6, 1 - 1e-6)); rows[kind]["logf"].append(lf)
            info[kind].append({"fold": k + 1, "trade_year": f["trade_start"][:4], "model": f"{spec['model']} ARMA({spec['arma']}) {spec['dist']}", **meta})
        parity = max(parity, max((abs(a - hv[t]) for a, t in zip(fm["u"][n_train:n_all], td) if t in hv), default=0.0))
    for kind in KINDS:
        rows[kind]["u"] = np.concatenate(rows[kind]["u"]); rows[kind]["logf"] = np.concatenate(rows[kind]["logf"])
        rows[kind]["date"] = np.array(rows[kind]["date"])
    return rows, info, parity


def by_year(rows, lo, hi):
    out = {}
    dd = rows["date"]
    for y in range(int(lo[:4]), int(hi[:4]) + 1):
        m = np.array([x[:4] == str(y) for x in dd])
        if m.sum() < 20:
            continue
        out[str(y)] = round(float(st.kstest(rows["u"][m], "uniform").pvalue), 4)
    return out


def diagnose(rows):
    """Where each design year's miss sits, under the unedited margin."""
    out = {}
    dd = rows["none"]["date"]
    u = rows["none"]["u"]
    for y in range(2010, 2020):
        m = np.array([x[:4] == str(y) for x in dd])
        z = st.norm.ppf(u[m])  # Gaussianised PIT: location, scale and tails on one footing
        out[str(y)] = {"ks_p": round(float(st.kstest(u[m], "uniform").pvalue), 4), "mean_z": round(float(z.mean()), 3),
                       "var_z": round(float(z.var(ddof=1)), 3), "share_outside_2": round(float(np.mean(np.abs(z) > 2)), 4),
                       "share_below_0.5": round(float(np.mean(u[m] < 0.5)), 3), "n": int(m.sum())}
    return out


def mask(dd, span):
    return np.array([span[0] <= x < span[1] for x in dd])


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "design"
    rows, info, parity = collect()
    print(f"parity with the stored walk-forward v: max |diff| {parity:.2e}")
    assert parity < 1e-6
    dm = mask(rows["none"]["date"], DESIGN)
    if stage == "design":
        diag = diagnose(rows)
        res = {}
        for kind in KINDS:
            yrs = by_year(rows[kind], *DESIGN)
            yrs = {y: p for y, p in yrs.items() if y < "2020"}
            res[kind] = {"design_years_failing": [y for y, p in yrs.items() if p < 0.05], "design_ks_by_year": yrs,
                         "design_mean_logf": round(float(rows[kind]["logf"][dm].mean()), 5)}
            if kind != "none":
                diff = rows[kind]["logf"][dm] - rows["none"]["logf"][dm]
                res[kind]["design_gain_per_day_x1000"] = round(float(diff.mean() * 1000), 3)
                res[kind]["design_dm_t"] = round(nw_t(diff), 2)
        cands = [k for k in KINDS if k != "none"]
        best = min(cands, key=lambda k: (len(res[k]["design_years_failing"]), -res[k]["design_mean_logf"]))
        qualifies = res[best]["design_dm_t"] > 2
        payload = {"parity_max_abs_diff": parity, "diagnosis": diag, "edits": res, "edit_meta": info, "chosen": best, "qualifies": bool(qualifies)}
        save("design", payload)
        print(json.dumps(diag, indent=0))
        for k in KINDS:
            print(k, res[k])
        print("chosen:", best, "| qualifies (DM t > 2):", qualifies)
