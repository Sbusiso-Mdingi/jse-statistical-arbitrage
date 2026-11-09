"""H10: leg sizing from the instrument's own volatilities and correlation (research/PROTOCOL.md).

Three sizings fixed at entry: 1:1, inverse volatility, minimum-variance hedge. The one test is on realised
position variance in validation; returns under each sizing and cost schedule are reported.
Writes research/results/h10.json and research/results/h10_daily.csv.
"""
import csv, json, math, sys
import numpy as np
sys.path.insert(0, "research")
from h5_weights import load, signals, positions, PERIODS, BASKET  # noqa: E402
from costs import TIERS, VAT  # noqa: E402

d = load()
B = json.load(open("data/basket.json"))
sig = signals(d, B["fits"])  # fitted margins: sig_sbk, sig_bsk per day; dates aligned with the walk-forward record
dates = [x.isoformat() for x in sig["date"]]
n = len(dates)
gas = {r["date"]: (float(r["h"]), float(r["state"])) for r in csv.DictReader(open("research/results/copulas_basket.csv")) if r["model"] == "gas_t"}
h = np.array([gas[x][0] for x in dates]); rho = np.array([gas[x][1] for x in dates])
ss, sb = sig["sig_sbk"], sig["sig_bsk"]
rs, rb = sig["rs"], sig["rb"]
bank_ew = np.mean([d["simple"][k] for k in ["sbk"] + BASKET], axis=0)[[i for i, x in enumerate(d["date"]) if x.isoformat() in gas]]
side = positions(h)  # +1 long SBK / short basket, -1 reverse, 0 flat; a new signal restarts and may flip


def weights(kind, t):
    if kind == "one_to_one":
        ws, wb = 0.5, 0.5
    elif kind == "inverse_vol":
        ws, wb = 1 / ss[t], 1 / sb[t]
    elif kind == "min_variance":  # as registered: basket per unit SBK = rho * sigma_s / sigma_b, then scaled to gross one
        ws, wb = 1.0, max(rho[t], 0.05) * ss[t] / sb[t]
    else:  # post hoc, reported: the weights that minimise the variance of w_s r_s - w_b r_b subject to w_s + w_b = 1
        r = max(rho[t], 0.05)
        ws = (sb[t] ** 2 + r * ss[t] * sb[t]) / (ss[t] ** 2 + sb[t] ** 2 + 2 * r * ss[t] * sb[t])
        wb = 1 - ws
    tot = ws + wb
    return ws / tot, wb / tot


def exposures(kind):
    """Signed exposure of each leg (units of capital) set at the close of each day; sized at entry and on restarts."""
    es, eb = np.zeros(n), np.zeros(n)
    ws = wb = 0.0
    for t in range(n):
        if side[t] == 0:
            continue
        new_trade = t == 0 or side[t - 1] != side[t] or abs(h[t] - 0.5) > 0.45
        if new_trade:
            ws, wb = weights(kind, t)
        es[t], eb[t] = side[t] * ws, -side[t] * wb
    return es, eb


def gross_and_costs(es, eb, tier):
    held_s, held_b = np.concatenate([[0.0], es[:-1]]), np.concatenate([[0.0], eb[:-1]])
    gross = held_s * rs + held_b * rb
    t = TIERS[tier]
    per_exec = (t["brokerage"] * (1 + VAT if t["vat"] else 1) + t["spread"] + t["strate"]) / 1e4
    stt = t["stt"] / 1e4
    ds, db = es - held_s, eb - held_b
    cost = (np.abs(ds) + np.abs(db)) * per_exec + (np.maximum(ds, 0) + np.maximum(db, 0)) * stt
    cost += (np.maximum(-held_s, 0) + np.maximum(-held_b, 0)) * (t["borrow"] / 1e4) / 252
    return gross, cost


def mask(p):
    a, b = PERIODS[p] if p in PERIODS else ("2010-01-01", "2026-04-01")
    return np.array([a <= x < b for x in dates])


def dm(diff):
    mu = diff.mean(); T = len(diff)
    g = lambda k: float(np.sum((diff[k:] - mu) * (diff[:-k] - mu)) / T) if k else float(np.var(diff))
    var = g(0) + 2 * sum((1 - k / 6) * g(k) for k in range(1, 6))
    return float(mu / math.sqrt(var / T)) if var > 0 else 0.0


def sharpe(x):
    sd = x.std(ddof=1); return round(float(x.mean() / sd * math.sqrt(252)), 2) if sd > 0 else 0.0


out = {"sizings": {}}
G = {}
for kind in ("one_to_one", "inverse_vol", "min_variance", "min_variance_gross"):
    es, eb = exposures(kind)
    gross, _ = gross_and_costs(es, eb, "protocol")
    G[kind] = gross
    rec = {"periods": {}}
    for p in ("design", "validation", "post-freeze"):
        m = mask(p)
        x = gross[m]; held = (es[m] != 0)
        beta = float(np.polyfit(bank_ew[m][held], x[held], 1)[0]) if held.sum() > 10 else None
        rec["periods"][p] = {"daily_vol_bps": round(float(x.std(ddof=1) * 1e4), 2), "vol_on_held_days_bps": round(float(x[held].std(ddof=1) * 1e4), 2),
                             "beta_to_banks": round(beta, 3) if beta is not None else None,
                             "sharpe": {tier: sharpe((gross - gross_and_costs(es, eb, tier)[1])[m]) for tier in TIERS}}
    # gross return per signal over the five-day hold under this sizing, by big period
    sig_days = np.flatnonzero((np.abs(h - 0.5) > 0.45) & (np.arange(n) + 5 < n))
    per_signal = {}
    for name, lo, hi in (("2010_2019", "2010", "2020"), ("2021_2026", "2021", "2100")):
        vals = []
        for t in sig_days:
            if not (lo <= dates[t][:4] < hi): continue
            ws, wb = weights(kind, t); dd = 1.0 if h[t] > 0.5 else -1.0
            vals.append(dd * (ws * rs[t + 1:t + 6].sum() - wb * rb[t + 1:t + 6].sum()) * 1e4)
        vals = np.array(vals)
        per_signal[name] = {"n": len(vals), "bps": round(float(vals.mean()), 1), "se": round(float(vals.std(ddof=1) / math.sqrt(len(vals))), 1)}
    rec["per_signal"] = per_signal
    # typical weights
    held_idx = np.flatnonzero(es != 0)
    rec["mean_sbk_weight"] = round(float(np.abs(es[held_idx]).mean()), 3)
    out["sizings"][kind] = rec
    print(f"{kind:13s} mean SBK weight {rec['mean_sbk_weight']:.3f} | validation daily vol {rec['periods']['validation']['daily_vol_bps']} bps, beta {rec['periods']['validation']['beta_to_banks']} | Sharpe protocol/inst/retail " + "/".join(str(rec['periods']['validation']['sharpe'][k]) for k in TIERS) + f" | per signal {per_signal['2010_2019']['bps']} -> {per_signal['2021_2026']['bps']} bps")

# The one test: minimum-variance hedge vs 1:1 on validation squared gross returns.
m = mask("validation")
diff = G["one_to_one"][m] ** 2 - G["min_variance"][m] ** 2
out["test"] = {"dm_t": round(dm(diff), 2), "variance_ratio": round(float(G["min_variance"][m].var() / G["one_to_one"][m].var()), 3)}
out["test"]["passed"] = bool(out["test"]["dm_t"] > 1.96)
out["reported_inverse_vol"] = {"dm_t": round(dm(G["one_to_one"][m] ** 2 - G["inverse_vol"][m] ** 2), 2), "variance_ratio": round(float(G["inverse_vol"][m].var() / G["one_to_one"][m].var()), 3)}
out["post_hoc_min_variance_gross"] = {"note": "not pre-registered; the registered ratio minimises variance per unit of SBK, this one per unit of gross exposure",
    "validation": {"dm_t": round(dm(G["one_to_one"][m] ** 2 - G["min_variance_gross"][m] ** 2), 2), "variance_ratio": round(float(G["min_variance_gross"][m].var() / G["one_to_one"][m].var()), 3)}}
print("post hoc: gross-constrained min-variance vs 1:1 ratio", out["post_hoc_min_variance_gross"]["validation"]["variance_ratio"], "DM t", out["post_hoc_min_variance_gross"]["validation"]["dm_t"])
md = mask("design")
out["design"] = {"min_variance": {"dm_t": round(dm(G["one_to_one"][md] ** 2 - G["min_variance"][md] ** 2), 2), "variance_ratio": round(float(G["min_variance"][md].var() / G["one_to_one"][md].var()), 3)}}
print("validation: min-variance vs 1:1 variance ratio", out["test"]["variance_ratio"], "DM t", out["test"]["dm_t"], "PASSED" if out["test"]["passed"] else "FAILED")
print("           inverse-vol vs 1:1 (reported) ratio", out["reported_inverse_vol"]["variance_ratio"], "DM t", out["reported_inverse_vol"]["dm_t"])
print("design:    min-variance vs 1:1 ratio", out["design"]["min_variance"]["variance_ratio"], "DM t", out["design"]["min_variance"]["dm_t"])
json.dump(out, open("research/results/h10.json", "w"), indent=1)
with open("research/results/h10_daily.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["date", "side", "sigma_sbk", "sigma_bsk", "rho", "gross_1to1", "gross_invvol", "gross_minvar", "gross_minvar_gross"])
    for i, x in enumerate(dates):
        w.writerow([x, int(side[i]), f"{ss[i]:.6f}", f"{sb[i]:.6f}", f"{rho[i]:.4f}", f"{G['one_to_one'][i]:.8f}", f"{G['inverse_vol'][i]:.8f}", f"{G['min_variance'][i]:.8f}", f"{G['min_variance_gross'][i]:.8f}"])
