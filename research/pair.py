"""Standard Bank against Nedbank on the score-driven copula (research/PROTOCOL.md, "Re-centring").
Reporting only, each part run once: gross per signal by year, the rule at each cost tier, red team
(lag, cleaning, leave-one-year-out, placebo) and leg sizing. Writes research/results/pair.json."""
import csv, json, math, sys
import datetime as dt
import numpy as np
sys.path.insert(0, "research"); sys.path.insert(0, "research/models"); sys.path.insert(0, "service")
from h5_weights import positions, PERIODS, _filter_full  # noqa: E402
from costs import TIERS, VAT, round_trip, costs  # noqa: E402
from pairdata import load_pair  # noqa: E402

HOLD = 5
d = load_pair()
gas = {r["date"]: (float(r["h"]), float(r["state"])) for r in csv.DictReader(open("research/results/copulas_py.csv")) if r["model"] == "gas_t"}
keep = [i for i, x in enumerate(d["date"]) if x.isoformat() in gas]
dates = [d["date"][i].isoformat() for i in keep]; n = len(dates)
h = np.array([gas[x][0] for x in dates]); rho = np.array([gas[x][1] for x in dates])
rs, rn = np.expm1(d["r_sbk"][keep]), np.expm1(d["r_ned"][keep])
spread = 0.5 * (rs - rn)
years = np.array([int(x[:4]) for x in dates])
sig_idx = np.flatnonzero((np.abs(h - 0.5) > 0.45) & (np.arange(n) + HOLD < n))
direction = np.where(h[sig_idx] > 0.5, 1.0, -1.0)
BIG = (("2010_2019", 2010, 2020), ("2020_2026", 2020, 2100), ("2021_2026", 2021, 2100))
out = {"n_days": n, "first": dates[0], "last": dates[-1], "n_signals": len(sig_idx)}


def per_signal(lag=0, keep_t=None):
    v, y = [], []
    for t, s in zip(sig_idx, direction):
        a = t + 1 + lag
        if a + HOLD > n or (keep_t is not None and not keep_t[t]):
            continue
        v.append(s * spread[a:a + HOLD].sum() * 1e4); y.append(years[t])
    return np.array(v), np.array(y)


def summarise(v, y):
    o = {}
    for name, lo, hi in BIG:
        m = (y >= lo) & (y < hi)
        o[name] = {"n": int(m.sum()), "bps": round(float(v[m].mean()), 1), "se": round(float(v[m].std(ddof=1) / math.sqrt(m.sum())), 1)} if m.sum() > 1 else None
    return o


def sharpe(x):
    sd = x.std(ddof=1); return round(float(x.mean() / sd * math.sqrt(252)), 2) if sd > 0 else 0.0


def pmask(p):
    a, b = PERIODS[p]; return np.array([a <= x < b for x in dates])


# 1. gross per signal by year, against the round trip; the next session alone; the fixed copula alongside
def edge_block(hh):
    si = np.flatnonzero((np.abs(hh - 0.5) > 0.45) & (np.arange(n) + HOLD < n))
    dd = np.where(hh[si] > 0.5, 1.0, -1.0)
    f5 = np.array([s * spread[t + 1:t + 1 + HOLD].sum() for t, s in zip(si, dd)]) * 1e4
    f1 = spread[si + 1] * dd * 1e4
    yy = years[si]
    o = {"cost_round_trip_bps": 20.0, "hold": HOLD, "last_date": dates[-1], "by_year": []}
    for yr in sorted(set(yy)):
        m = yy == yr
        if m.sum() < 2: continue
        o["by_year"].append({"year": int(yr), "n": int(m.sum()), "bps": round(float(f5[m].mean()), 1), "se": round(float(f5[m].std(ddof=1) / math.sqrt(m.sum())), 1),
                             "next_bps": round(float(f1[m].mean()), 1), "next_se": round(float(f1[m].std(ddof=1) / math.sqrt(m.sum())), 1), "partial": str(yr) == dates[-1][:4]})
    for name, lo, hi in BIG:
        m = (yy >= lo) & (yy < hi)
        o[name] = {"n": int(m.sum()), "bps": round(float(f5[m].mean()), 1), "se": round(float(f5[m].std(ddof=1) / math.sqrt(m.sum())), 1), "next_bps": round(float(f1[m].mean()), 1)}
    return o


v, y = per_signal(0)
static_h = np.array([float(r["h"]) for r in csv.DictReader(open("research/results/copulas_py.csv")) if r["model"] == "static_t" and r["date"] in set(dates)])
out["edge"] = {**edge_block(h), "copula": "gas_t", "round_trip_bps": {k: round(round_trip(t), 1) for k, t in TIERS.items()}}
out["edge_static"] = {**edge_block(static_h), "copula": "static_t"}
print("edge:", {k: out["edge"][k] for k in ("2010_2019", "2021_2026")}, "| fixed copula:", {k: out["edge_static"][k] for k in ("2010_2019", "2021_2026")}, "| round trips", out["edge"]["round_trip_bps"])

# 2. the rule at each cost tier, and hold-until-normal (reported)
def positions_revert(h, open_level=0.45, close_level=0.25):
    pos = np.zeros(len(h)); cur = 0.0
    for t in range(len(h)):
        s = abs(h[t] - 0.5)
        if s > open_level: cur = 1.0 if h[t] > 0.5 else -1.0
        elif cur != 0 and s < close_level: cur = 0.0
        pos[t] = cur
    return pos

def stats(x):
    eq = np.cumprod(1 + x); sd = x.std(ddof=1)
    return {"sharpe": round(float(x.mean() / sd * math.sqrt(252)), 2) if sd > 0 else 0.0, "cagr": round(float(eq[-1] ** (252 / len(x)) - 1), 4),
            "mdd": round(float((eq / np.maximum.accumulate(eq) - 1).min()), 4)}


WF = np.array([x < "2026-04-01" for x in dates])
SPANS = {"design": pmask("design"), "validation": pmask("validation"), "post_freeze": pmask("post-freeze"), "full": WF}
out["costs"] = {"tiers": {}, "components_institutional": None, "hold_until_normal": None}
for label, pos in (("five_day_hold", positions(h)), ("hold_until_normal", positions_revert(h))):
    held = np.concatenate([[0.0], pos[:-1]]); gross = held * spread
    tiers = {}
    for k, t in TIERS.items():
        net = gross - costs(pos, t)
        tiers[k] = {"label": t["label"], "round_trip_bps": round(round_trip(t), 1), **{sp: stats(net[m]) for sp, m in SPANS.items()}}
    tiers["gross"] = {sp: stats(gross[m]) for sp, m in SPANS.items()}
    if label == "five_day_hold":
        out["costs"]["tiers"] = tiers
    else:
        runs, r_ = [], 0
        for x in pos:
            if x != 0: r_ += 1
            elif r_: runs.append(r_); r_ = 0
        out["costs"]["hold_until_normal"] = {"avg_days_held": round(float(np.mean(runs)), 1), "trades": len(runs), "in_market": round(float((pos != 0).mean()), 3), "tiers": tiers}
    print(label, "gross SR", {sp: tiers["gross"][sp]["sharpe"] for sp in SPANS}, "| institutional SR", {sp: tiers["institutional"][sp]["sharpe"] for sp in SPANS}, "CAGR full", tiers["institutional"]["full"]["cagr"])
T = TIERS["institutional"]
out["costs"]["components_institutional"] = {"brokerage_incl_vat": round(4 * 0.5 * T["brokerage"] * (1 + VAT), 1), "stt": round(2 * 0.5 * T["stt"], 1), "spread": round(4 * 0.5 * T["spread"], 1),
                                            "strate_levy": round(4 * 0.5 * T["strate"], 1), "borrow_per_5_days": round(0.5 * T["borrow"] * 5 / 252, 2)}
bench = 0.5 * (rs + rn)
out["benchmark_walkforward_cagr"] = round(float(np.prod(1 + bench[WF]) ** (252 / WF.sum()) - 1), 4)

# 3a. lag
out["lag"] = {f"lag_{k}_closes": summarise(*per_signal(k)) for k in (0, 1, 2)}
out["lag"]["next_10am_bar"] = {"restated_from": "research/results/redteam.json (pair)", **json.load(open("research/results/redteam.json"))["lag"]["pair"]}
print("lag 1 close:", out["lag"]["lag_1_closes"]["2010_2019"], "| lag 2:", out["lag"]["lag_2_closes"]["2010_2019"])

# 3b. causal cleaning on the two banks
cl = json.load(open("research/results/redteam.json"))["cleaning"]
out["cleaning"] = {"restated_from": "research/results/redteam.json", "sbk": cl["sbk"], "ned": cl["ned"]}
print("cleaning sbk flags", cl["sbk"]["causal_rule_flags"], "removes", cl["sbk"]["current_rule_removes"], "| ned flags", cl["ned"]["causal_rule_flags"], "removes", cl["ned"]["current_rule_removes"], "differs", cl["ned"]["n_different"])

# 3c. leave one year out
out["loo"] = {"full_bps": round(float(v.mean()), 1), "without": {}}
for yr in sorted(set(y)):
    m = y != yr
    out["loo"]["without"][str(yr)] = {"2010_2019": round(float(v[m & (y < 2020)].mean()), 1), "2020_2026": round(float(v[m & (y >= 2020)].mean()), 1)}
best = max(range(2010, 2020), key=lambda yr: v[y == yr].mean())
out["loo"]["best_design_year"] = best
print("loo: best design year", best, "->", out["loo"]["without"][str(best)], "| without 2020", out["loo"]["without"]["2020"])

# 3d. placebo: same count of signals per year, random days and directions
rng = np.random.default_rng(20261109)
cs = np.concatenate([[0.0], np.cumsum(spread)])
counts = {yr: int((y == yr).sum()) for yr in sorted(set(y))}
pool = {yr: np.flatnonzero((years == yr) & (np.arange(n) + 1 + HOLD <= n)) for yr in counts}
D = 10000
sims = {name: np.zeros(D) for name, _, _ in BIG}
for k in range(D):
    vals, ys = [], []
    for yr, c in counts.items():
        if c == 0: continue
        t = rng.choice(pool[yr], size=c, replace=False); s = rng.choice([-1.0, 1.0], size=c)
        vals.append(s * (cs[t + 1 + HOLD] - cs[t + 1]) * 1e4); ys.append(np.full(c, yr))
    vals, ys = np.concatenate(vals), np.concatenate(ys)
    for name, lo, hi in BIG:
        m = (ys >= lo) & (ys < hi); sims[name][k] = vals[m].mean()
act = summarise(v, y)
out["placebo"] = {name: {"actual_bps": act[name]["bps"], "placebo_mean": round(float(sims[name].mean()), 1), "placebo_sd": round(float(sims[name].std()), 1),
                         "percentile": round(float((sims[name] < act[name]["bps"]).mean() * 100), 1)} for name, _, _ in BIG}
print("placebo:", out["placebo"])

# 4. sizing from the instrument's own forecasts
W = json.load(open("data/walkforward.json")); folds = W["folds"]; ends = [f["train_end"] for f in folds]
alld = [x.isoformat() for x in d["date"]]
sig = {"sbk": np.full(len(alld), np.nan), "ned": np.full(len(alld), np.nan)}
for k, f in enumerate(folds):
    n_train = sum(1 for x in alld if x <= f["train_end"])
    n_all = sum(1 for x in alld if x <= ends[k + 1]) if k + 1 < len(folds) else len(alld)
    if n_all <= n_train: continue
    for s in ("sbk", "ned"):
        fm = _filter_full(f[s], d[f"r_{s}"][:n_all], d["vix"][:n_all], n_train)
        sig[s][n_train:n_all] = np.asarray(fm["sigma"])[n_train:n_all]
ss, sn = sig["sbk"][keep], sig["ned"][keep]
side = positions(h)


def weights(kind, t):
    if kind == "one_to_one": return 0.5, 0.5
    if kind == "inverse_vol": a, b = 1 / ss[t], 1 / sn[t]
    elif kind == "min_variance": a, b = 1.0, max(rho[t], 0.05) * ss[t] / sn[t]
    else:
        r = max(rho[t], 0.05)
        a = (sn[t] ** 2 + r * ss[t] * sn[t]) / (ss[t] ** 2 + sn[t] ** 2 + 2 * r * ss[t] * sn[t]); b = 1 - a
    return a / (a + b), b / (a + b)


def gross_and_cost(kind, tier):
    es, en = np.zeros(n), np.zeros(n); a = b = 0.0
    for t in range(n):
        if side[t] == 0: continue
        if t == 0 or side[t - 1] != side[t] or abs(h[t] - 0.5) > 0.45: a, b = weights(kind, t)
        es[t], en[t] = side[t] * a, -side[t] * b
    hs, hn = np.concatenate([[0.0], es[:-1]]), np.concatenate([[0.0], en[:-1]])
    g = hs * rs + hn * rn
    T = TIERS[tier]; pe = (T["brokerage"] * (1 + VAT if T["vat"] else 1) + T["spread"] + T["strate"]) / 1e4
    ds, dn = es - hs, en - hn
    c = (np.abs(ds) + np.abs(dn)) * pe + (np.maximum(ds, 0) + np.maximum(dn, 0)) * T["stt"] / 1e4 + (np.maximum(-hs, 0) + np.maximum(-hn, 0)) * T["borrow"] / 1e4 / 252
    return g, c, es


def dm(diff):
    mu = diff.mean(); T = len(diff)
    g = lambda k: float(np.sum((diff[k:] - mu) * (diff[:-k] - mu)) / T) if k else float(np.var(diff))
    var = g(0) + 2 * sum((1 - k / 6) * g(k) for k in range(1, 6))
    return round(float(mu / math.sqrt(var / T)), 2) if var > 0 else 0.0


out["sizing"] = {}
G = {}
for kind in ("one_to_one", "inverse_vol", "min_variance", "min_variance_gross"):
    g, _, es = gross_and_cost(kind, "protocol"); G[kind] = g
    rec = {"mean_sbk_weight": round(float(np.abs(es[es != 0]).mean()), 3), "periods": {}}
    for p in PERIODS:
        m = pmask(p)
        rec["periods"][p] = {"daily_vol_bps": round(float(g[m].std(ddof=1) * 1e4), 2), "gross_sharpe": sharpe(g[m]),
                             "institutional_sharpe": sharpe((g - gross_and_cost(kind, "institutional")[1])[m])}
    out["sizing"][kind] = rec
for kind in ("inverse_vol", "min_variance", "min_variance_gross"):
    for p in ("design", "validation"):
        m = pmask(p)
        out["sizing"][kind]["periods"][p]["variance_ratio_vs_1to1"] = round(float(G[kind][m].var() / G["one_to_one"][m].var()), 3)
        out["sizing"][kind]["periods"][p]["dm_t_vs_1to1"] = dm(G["one_to_one"][m] ** 2 - G[kind][m] ** 2)
for kind, rec in out["sizing"].items():
    print(f"sizing {kind:18s} SBK weight {rec['mean_sbk_weight']} | validation", rec["periods"]["validation"])
json.dump(out, open("research/results/pair.json", "w"), indent=1)
