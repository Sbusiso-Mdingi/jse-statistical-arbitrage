"""One refit under H17 (research/PROTOCOL.md), after research/refit.R: PITs, the GAS copula and the state at T.

  python research/refit_export.py 2026-08-31 [kind]   # kind: scheduled (default) or catch-up
  python research/refit_export.py init                # once, the 31 March 2026 fit as the first entry

Every session after T is deleted before anything is fitted. Appends the refit to data/refits.json with
applies_from unset; research/refit_apply.py sets it just before a person deploys, so a refit is never used
on a session before it went live. After the fit, sessions after T in data/raw are filtered with the new
parameters (fixed, nothing estimated) as the service's parity reference.
"""
import json, math, sys
import datetime as dt
import numpy as np
from scipy import stats as st

sys.path.insert(0, "research"); sys.path.insert(0, "research/models"); sys.path.insert(0, "service")
from pairdata import load_pair  # noqa: E402
from h5_weights import _filter_full  # noqa: E402
from copulas_py import gas_fit, gas_unpack, gas_filter, t_score_rho, fit_static  # noqa: E402
from app.model import gas_filter as live_gas  # noqa: E402

REFITS = "data/refits.json"
CL = 1e-6


def base_entry():
    """The fit of 31 March 2026, the first entry: the walk-forward's final fold and data/pair_gas.json."""
    f = json.load(open("data/model_final.json")); g = json.load(open("data/pair_gas.json"))["latest"]
    assert f["train_end"] == g["train_end"]
    return {"train_end": f["train_end"], "kind": "walk-forward freeze", "reselected": True, "applies_from": f["trade_start"],
            "data_to": f["train_end"], **{b: {k: f[b][k] for k in ("model", "arma", "dist", "vix", "bic", "coef")} for b in ("sbk", "ned")},
            "state": {b: f["state"][b] for b in ("sbk", "ned")}, "rho_start": f["copula"]["par"],
            "gas": {k: g[k] for k in ("omega", "beta", "alpha", "nu", "f_next", "rho_train_end")}}


def load(te=None):
    d = load_pair()
    keep = [i for i, t in enumerate(d["date"]) if te is None or t <= te]
    return {k: (np.asarray(v)[keep] if k != "date" else [v[i] for i in keep]) for k, v in d.items()}


def main(te_s, kind):
    te = dt.date.fromisoformat(te_s)
    book = json.load(open(REFITS))
    prior = book["refits"][-1]
    assert prior["train_end"] < te_s, f"{REFITS} already has a refit on or after {te_s}"
    r = json.load(open(f"research/results/refit_{te_s}.json"))
    d = load(te)  # nothing after T
    n = len(d["date"])
    entry = {"train_end": te_s, "kind": kind, "reselected": r["reselected"], "applies_from": None, "data_to": d["date"][-1].isoformat(), "state": {}}
    us = []
    for b in ("sbk", "ned"):
        if r[b]["ok"]:
            sp = {k: r[b][k] for k in ("model", "arma", "dist", "vix", "bic", "coef")}
        else:
            sp = dict(prior[b]); entry.setdefault("not_converged", []).append(b)
        fm = _filter_full(sp, d[f"r_{b}"], d["vix"], n)
        entry[b] = sp
        entry["state"][b] = {"r": float(d[f"r_{b}"][-1]), "mu": float(fm["mu"][-1]), "sigma": float(fm["sigma"][-1]), "z": float(fm["z"][-1])}
        us.append(np.clip(fm["u"], CL, 1 - CL))
    u, v = us
    entry["rho_start"] = fit_static(u, v)[0] if r["reselected"] else prior["rho_start"]
    p = gas_fit(u, v, entry["rho_start"])
    omega, beta, alpha, nu = gas_unpack(p)
    ff, _, _ = gas_filter(u, v, omega, beta, alpha, nu, omega / max(1 - beta, 1e-3))
    x_T, y_T = st.t.ppf(u[-1], nu), st.t.ppf(v[-1], nu)
    rho_T = math.tanh(ff[-1])
    f_next = max(min(omega + beta * ff[-1] + alpha * t_score_rho(x_T, y_T, rho_T, nu) * (1 - rho_T ** 2), 4.0), -4.0)
    entry["gas"] = {"omega": omega, "beta": beta, "alpha": alpha, "nu": nu, "f_next": f_next, "rho_train_end": rho_T}
    entry["pit_ks"] = {b: float(st.kstest(x, "uniform").pvalue) for b, x in (("sbk", u), ("ned", v))}

    # Parity reference, after the fit: later sessions filtered with the parameters just fixed.
    full = load()
    later = [i for i, t in enumerate(full["date"]) if t > te]
    if later:
        ref = {"date": [full["date"][i].isoformat() for i in later]}
        uu = []
        for b in ("sbk", "ned"):
            fm = _filter_full(entry[b], full[f"r_{b}"], full["vix"], n)
            assert abs(fm["sigma"][n - 1] - entry["state"][b]["sigma"]) < 1e-12
            uu.append(np.clip(fm["u"][later], CL, 1 - CL))
            ref[f"sigma_{b}"] = fm["sigma"][later].tolist()
        ref["u"], ref["v"] = uu[0].tolist(), uu[1].tolist()
        ref["h"] = live_gas(entry["gas"], uu[0], uu[1])[0].tolist()
        entry["reference"] = ref
    book["refits"].append(entry)
    json.dump(book, open(REFITS, "w"), indent=1)

    print(f"refit to {te_s} ({kind}), data to {entry['data_to']}, {n} sessions")
    for b in ("sbk", "ned"):
        a, c = prior[b]["coef"], entry[b]["coef"]
        print(f"  {b.upper()} {entry[b]['model']}({entry[b]['arma']}) {entry[b]['dist']}:",
              ", ".join(f"{k} {a.get(k, float('nan')):.4g} -> {c[k]:.4g}" for k in c))
    print("  GAS:", ", ".join(f"{k} {prior['gas'][k]:.4g} -> {entry['gas'][k]:.4g}" for k in entry["gas"]))


if __name__ == "__main__":
    if sys.argv[1] == "init":  # once: the history starts with the fit of 31 March 2026
        json.dump({"refits": [base_entry()]}, open(REFITS, "x"), indent=1)
    else:
        main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "scheduled")
