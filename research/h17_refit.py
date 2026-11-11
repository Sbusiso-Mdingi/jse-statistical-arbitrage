"""H17 (research/PROTOCOL.md): history check of when the models refit, on development data only.

  Rscript research/h17_fits.R     # margin parameters at every month end
  python research/h17_refit.py    # GAS refits, the candidates' joint log scores and copula-rule trades

Every session after 31 March 2026 is deleted before any fit. Writes research/results/h17.json.
"""
import json, math, sys, time
import datetime as dt
from multiprocessing import Pool
import numpy as np
from scipy import stats as st, special

sys.path.insert(0, "research"); sys.path.insert(0, "research/models"); sys.path.insert(0, "service")
from pairdata import load_pair  # noqa: E402
from h5_weights import _filter_full  # noqa: E402
from app import switch as sw  # noqa: E402
import copulas_py as cp  # noqa: E402

DEV_END = dt.date(2026, 3, 31)
SCORE_FROM = dt.date(2010, 1, 1)
CRITS = (sw.GATE_CRIT, sw.EG_CRIT)
NW_LAGS, BAR, KS_MIN = 21, 2.33, 63
CL = 1e-6

raw = load_pair()
keep = [i for i, t in enumerate(raw["date"]) if t <= DEV_END]
d = {k: (np.asarray(v)[keep] if k != "date" else [v[i] for i in keep]) for k, v in raw.items()}
dates = d["date"]; n = len(dates)
F = json.load(open("research/results/h17_fits.json"))
assert F["sessions"] == n and F["last_session"] == dates[-1].isoformat()
ENDS = sorted({f["train_end"] for f in F["fits"]})
FITS = {(f["train_end"], f["bank"]): f for f in F["fits"]}
NTR = {e: sum(1 for t in dates if t.isoformat() <= e) for e in ENDS}


def spec(f):
    return {"model": f["model"], "dist": f["dist"], "vix": f["vix"], "coef": f["coef"]}


def margin_logpdf(fm, sp):
    z, sig = fm["z"], fm["sigma"]
    if sp["dist"] == "std":
        nu = sp["coef"]["shape"]; s = math.sqrt(nu / (nu - 2))
        return math.log(s) + st.t.logpdf(z * s, nu) - np.log(sig)
    return st.norm.logpdf(z) - np.log(sig)


def t_logc_vec(x, y, rho, nu):
    r2 = 1 - rho * rho
    q = (x * x - 2 * rho * x * y + y * y) / r2
    lf2 = special.gammaln((nu + 2) / 2) - special.gammaln(nu / 2) - math.log(nu * math.pi) - 0.5 * np.log(r2) - (nu + 2) / 2 * np.log1p(q / nu)
    return lf2 - st.t.logpdf(x, nu) - st.t.logpdf(y, nu)


def one_fit(e):
    """Everything a refit at e gives, on every session (the caller uses only those after e)."""
    n_train = NTR[e]
    out = {"end": e}
    us = []
    for b in ("sbk", "ned"):
        f = FITS[(e, b)]
        sp = spec(f)
        fm = _filter_full(sp, d[f"r_{b}"], d["vix"], n_train)
        out[f"lf_{b}"] = margin_logpdf(fm, sp)
        out[f"u_{b}"] = np.clip(fm["u"], CL, 1 - CL)
        us.append(out[f"u_{b}"])
    u, v = us
    p = cp.gas_fit(u[:n_train], v[:n_train], FITS[(e, "sbk")]["rho_start"])
    omega, beta, alpha, nu = cp.gas_unpack(p)
    f, x, y = cp.gas_filter(u, v, omega, beta, alpha, nu, omega / max(1 - beta, 1e-3))
    rho = np.tanh(f)
    out["logc"] = t_logc_vec(x, y, rho, nu)
    out["h"] = np.clip(st.t.cdf((y - rho * x) / np.sqrt((nu + x * x) * (1 - rho * rho) / (nu + 1)), nu + 1), 1e-10, 1 - 1e-10)
    out["gas"] = {"omega": omega, "beta": beta, "alpha": alpha, "nu": nu}
    return out


def nw_t(dd, lags=NW_LAGS):
    dd = np.asarray(dd, float); m = dd.mean(); u = dd - m; N = len(dd)
    v = u @ u / N
    for k in range(1, lags + 1):
        v += 2 * (1 - k / (lags + 1)) * (u[k:] @ u[:-k]) / N
    se = math.sqrt(v / N)
    return m, se, m / se if se > 0 else float("nan")


def main():
    t0 = time.time()
    with Pool(7) as pool:
        R = {o["end"]: o for o in pool.map(one_fit, ENDS)}
    print(f"{len(R)} GAS refits in {time.time() - t0:.0f}s", flush=True)

    x, y = np.cumsum(d["r_sbk"]), np.cumsum(d["r_ned"])
    b126, z126, eg = sw.rolling(x, y)
    s0 = next(i for i, t in enumerate(dates) if t >= SCORE_FROM)
    year_ends = [e for e in ENDS if e.endswith("-12-31")]
    # Refit dates eligible as triggers: month ends before the last development month.
    months = [e for e in ENDS if e < DEV_END.isoformat()]

    def crossed(e):
        lo = NTR[[m for m in ENDS if m < e][-1]] if e > ENDS[0] else 0
        seg = eg[max(lo - 1, 0):NTR[e]]
        seg = seg[~np.isnan(seg)]
        return any(np.any(np.diff(np.sign(seg - c)) != 0) for c in CRITS)

    def ks_drift(e, cur):
        a, z_ = NTR[cur], NTR[e]
        if z_ - a < KS_MIN:
            return False
        return any(st.kstest(R[cur][f"u_{b}"][a:z_], "uniform").pvalue < 0.05 for b in ("sbk", "ned"))

    def schedule(rule):
        refits, cur = [], None
        for e in months:
            if e.endswith("-12-31") or cur is None:
                fire = e.endswith("-12-31")
            else:
                fire = rule(e, cur)
            if fire:
                refits.append(e); cur = e
        return refits

    rules = {
        "Y": lambda e, cur: False,
        "Q": lambda e, cur: e[5:7] in ("03", "06", "09"),
        "M": lambda e, cur: True,
        "K": ks_drift,
        "E": lambda e, cur: crossed(e),
        "R": lambda e, cur: e[5:7] in ("03", "08"),
    }
    mode = sw.modes(x, y, eg, "E", None)
    out = {"protocol": "research/PROTOCOL.md, H17", "computed": dt.date.today().isoformat(), "dev_end": DEV_END.isoformat(),
           "scored": [dates[s0].isoformat(), dates[-1].isoformat()], "sessions_scored": n - s0, "candidates": {}}
    comp = {}
    for k, rule in rules.items():
        refits = schedule(rule)
        idx = np.full(n, -1)
        for e in refits:
            idx[NTR[e]:] = refits.index(e)
        parts = {q: np.full(n, np.nan) for q in ("lf_sbk", "lf_ned", "logc", "h", "u_sbk", "u_ned")}
        for j, e in enumerate(refits):
            m = idx == j
            for q in parts:
                parts[q][m] = R[e][q][m]
        sl = slice(s0, n)
        joint = parts["lf_sbk"] + parts["lf_ned"] + parts["logc"]
        comp[k] = {"joint": joint[sl], "margins": (parts["lf_sbk"] + parts["lf_ned"])[sl], "copula": parts["logc"][sl]}
        h = np.where(np.isnan(parts["h"]), 0.5, parts["h"])
        res = {"refits": len(refits), "refits_between_year_ends": len(refits) - len(year_ends),
               "mean_joint_logscore": round(float(joint[sl].mean()), 5),
               "ks_p": {"h": round(float(st.kstest(parts["h"][sl], "uniform").pvalue), 4),
                        **{b: round(float(st.kstest(parts[f"u_{b}"][sl], "uniform").pvalue), 4) for b in ("sbk", "ned")}},
               "trades": {}}
        rs, rn = np.expm1(d["r_sbk"]), np.expm1(d["r_ned"])
        hh = h.copy(); hh[:s0] = 0.5
        for name, trs in (("copula_alone", sw.trades(np.zeros(n, np.int8), hh, b126, z126, spread_on=False)),
                          ("switch", sw.trades(mode, hh, b126, z126))):
            res["trades"][name] = {}
            for sched in ("futures", "cash"):
                _, rows = sw.daily_returns(trs, dates, rs, rn, sched)
                v = np.array([r["net"] for r in rows if r["complete"] and dates[r["open"]] >= SCORE_FROM]) * 1e4
                res["trades"][name][sched] = {"trades": int(len(v)), "per_trade_bps": round(float(v.mean()), 1),
                                              "se_bps": round(float(v.std(ddof=1) / math.sqrt(len(v))), 1)}
        res["refit_dates"] = refits if k not in ("Y", "M") else None
        out["candidates"][k] = res
        if k == "Y":
            # Parity: yearly refits reproduce copulas_py.csv's gas_t h.
            import csv
            ref = {r["date"]: float(r["h"]) for r in csv.DictReader(open("research/results/copulas_py.csv")) if r["model"] == "gas_t"}
            diffs = [abs(h[i] - ref[dates[i].isoformat()]) for i in range(s0, n) if dates[i].isoformat() in ref]
            out["parity_max_abs_h_diff"] = float(max(diffs)); out["parity_days"] = len(diffs)
            print("parity: max |h - copulas_py gas_t|", max(diffs), "over", len(diffs), "days", flush=True)
    for k in rules:
        if k == "Y":
            continue
        c = out["candidates"][k]
        for part in ("joint", "margins", "copula"):
            m, se, t = nw_t(comp[k][part] - comp["Y"][part])
            c[f"vs_Y_{part}"] = {"mean_gain": round(m, 6), "se": round(se, 6), "t": round(t, 2)}
        c["beats_Y"] = bool(c["vs_Y_joint"]["mean_gain"] > 0 and c["vs_Y_joint"]["t"] > BAR)
        y_fut = out["candidates"]["Y"]["trades"]["copula_alone"]["futures"]["per_trade_bps"]
        c["copula_rule_not_worse"] = c["trades"]["copula_alone"]["futures"]["per_trade_bps"] >= y_fut
    ok = [k for k in rules if k != "Y" and out["candidates"][k]["beats_Y"] and out["candidates"][k]["copula_rule_not_worse"]]
    if ok:
        best = max(ok, key=lambda k: out["candidates"][k]["vs_Y_joint"]["mean_gain"])
        top = out["candidates"][best]["vs_Y_joint"]
        tied = [k for k in ok if top["mean_gain"] - out["candidates"][k]["vs_Y_joint"]["mean_gain"] < top["se"]]
        best = min(tied, key=lambda k: out["candidates"][k]["refits"])
    else:
        best = "Y"
    out["chosen"] = best
    out["gas_by_refit"] = {e: {q: round(v, 5) for q, v in R[e]["gas"].items()} for e in ENDS}
    json.dump(out, open("research/results/h17.json", "w"), indent=1)
    for k, c in out["candidates"].items():
        print(k, c["refits"], c["mean_joint_logscore"], c.get("vs_Y_joint"), c.get("vs_Y_margins", {}).get("t"), c.get("vs_Y_copula", {}).get("t"),
              c["ks_p"], {nm: (v["futures"]["trades"], v["futures"]["per_trade_bps"], v["cash"]["per_trade_bps"]) for nm, v in c["trades"].items()})
    print("chosen:", best, f"({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
