"""H6: a learned exit for the H1 trade, trained on virtual episodes from every day (research/PROTOCOL.md).

Entries, decision points and exits as in H3. Training episodes start at every close, in the
direction of that day's signal, so the fitted Q-iteration sees every day rather than the ~600
decision points inside real trades. A small network replaces H3b's ridge regression, and the
H5 calibrated signal is a state variable.
"""
import csv, json, math, sys, time
from bisect import bisect_left
import numpy as np
from joblib import Parallel, delayed
from sklearn.neural_network import MLPRegressor

COST = 10 / 1e4
Q, HOLD = 0.90, 5
BASKET = ["fsr", "abg", "ned", "cpi"]
FIRST_TEST_YEAR = 2013
PERIODS = {
    "design": ("2013-01-01", "2020-01-01"),
    "validation": ("2020-01-01", "2026-04-01"),
    "post-freeze": ("2026-04-01", "2100-01-01"),
}

rows = list(csv.DictReader(open("data/h1_daily.csv")))
dates = [r["date"] for r in rows]
n = len(dates)
h = np.array([float(r["h"]) for r in rows])
rs = np.array([float(r["sbk"]) for r in rows])
rb = np.array([[float(r[k]) for k in BASKET] for r in rows]).mean(axis=1)
spread = 0.5 * (rs - rb)
e_rows = {r["date"]: float(r["h_edited"]) for r in csv.DictReader(open("research/results/h5_daily.csv"))}
he = np.array([e_rows[d] for d in dates])
vix_rows = [(r["date"], float(r["vix"])) for r in csv.DictReader(open("data/raw/vix.csv")) if r["vix"] not in ("", "NA")]
vix_d = [d for d, _ in vix_rows]
vix = np.array([vix_rows[max(bisect_left(vix_d, d) - 1, 0)][1] for d in dates])
rv = np.array([np.std(rs[max(0, t - 19):t + 1] - rb[max(0, t - 19):t + 1]) for t in range(n)])

# ---- real H1 trades and decision points (as H3) -------------------------------------------
signal = np.abs(h - 0.5) > Q / 2
side = np.where(h > 0.5, 1.0, -1.0)
start = np.full(n, -1)
s = -10**9
for t in range(n):
    if signal[t]:
        s = t
    if t - s < HOLD:
        start[t] = s
decision = np.array([start[t] >= 0 and 1 <= t - start[t] <= HOLD - 1 and t + 1 < n for t in range(n)])

NAMES = ["days_held", "signal_now", "signal_entry", "edit_now", "edit_entry", "pnl", "today", "rv20", "vix"]
EDIT = ["edit_now", "edit_entry"]


def features(t0, t):
    d = side[t0]
    return [t - t0, d * (h[t] - 0.5), abs(h[t0] - 0.5), d * (he[t] - 0.5), abs(he[t0] - 0.5),
            d * spread[t0 + 1:t + 1].sum(), d * spread[t], rv[t], vix[t]]


# ---- virtual episodes from every close -----------------------------------------------------
ep = [(t0, t0 + k) for t0 in range(n) for k in range(1, HOLD) if t0 + k + 1 < n]
X_all = np.array([features(t0, t) for t0, t in ep])
reward = np.array([side[t0] * spread[t + 1] for t0, t in ep])
pos_in = {(t0, t): i for i, (t0, t) in enumerate(ep)}
nxt = np.array([pos_in.get((t0, t + 1), -1) if t - t0 < HOLD - 1 else -1 for t0, t in ep])
out_date = np.array([dates[t + 1] for t0, t in ep])
dp_date = np.array([dates[t] for t0, t in ep])
real = np.array([start[t] == t0 and decision[t] for t0, t in ep])  # real H1 decision points sit inside the episodes
print(f"{len(ep)} virtual decision points, of which {real.sum()} are real H1 decision points")


def fit_year(y, reg, cols, seed=0):
    cut = f"{y - 1}-12-31"
    train = out_date <= cut
    test = np.array([d[:4] == str(y) for d in dp_date])
    X = X_all[:, cols]
    mu, sd = X[train].mean(0), X[train].std(0) + 1e-12
    Z = (X - mu) / sd
    q = np.zeros(len(ep))
    for _ in range(HOLD - 1):
        cont = np.where(nxt >= 0, np.maximum(0.0, q[np.maximum(nxt, 0)]), 0.0)
        m = MLPRegressor(hidden_layer_sizes=(16, 16), alpha=reg, max_iter=300, random_state=seed, tol=1e-5)
        m.fit(Z[train], (reward + cont)[train] * 1e4)
        q = m.predict(Z) / 1e4
    return y, test, q[test]


def walk_forward(reg, cols, years):
    q = np.zeros(len(ep))
    res = Parallel(n_jobs=-1)(delayed(fit_year)(y, reg, cols) for y in years)
    for y, test, qt in res:
        q[test] = qt
    return q


def positions(q=None):
    pos = np.zeros(n)
    exited = False
    for t in range(n):
        if signal[t]:
            exited = False
        elif q is not None and decision[t] and q[pos_in[(start[t], t)]] < 0:
            exited = True
        pos[t] = side[start[t]] if start[t] >= 0 and not exited else 0.0
    return pos


def net_returns(pos):
    held = np.concatenate([[0.0], pos[:-1]])
    return held * spread - np.abs(np.diff(np.concatenate([[0.0], pos]))) * COST


def evaluate(pos, a, b):
    net_all = net_returns(pos)
    m = np.array([a <= d < b for d in dates])
    net, p = net_all[m], pos[m]
    eq = np.cumprod(1 + net)
    sd = net.std(ddof=1)
    return dict(start=dates[int(np.argmax(m))], end=dates[n - 1 - int(np.argmax(m[::-1]))],
                sharpe=round(net.mean() / sd * math.sqrt(252), 2),
                sortino=round(net.mean() / math.sqrt(np.mean(np.minimum(net, 0) ** 2)) * math.sqrt(252), 2),
                cagr=round(eq[-1] ** (252 / len(net)) - 1, 4), mdd=round(float((eq / np.maximum.accumulate(eq) - 1).min()), 4),
                in_market=round(float((p != 0).mean()), 3))


def report(q=None):
    pos = positions(q)
    out = {k: evaluate(pos, a, b) for k, (a, b) in PERIODS.items()}
    if q is not None:
        for k, (a, b) in PERIODS.items():
            m = real & (dp_date >= a) & (dp_date < b)
            out[k]["exit_share"] = round(float((q[m] < 0).mean()), 3) if m.any() else None
    return out


def paired(pos_a, pos_b, period):
    a, b = PERIODS[period]
    m = np.array([a <= d < b for d in dates])
    diff = (net_returns(pos_a) - net_returns(pos_b))[m]
    return {"bps_per_year": round(float(diff.mean() * 252 * 1e4), 1), "t_stat": round(float(diff.mean() / (diff.std(ddof=1) / math.sqrt(len(diff)))), 2)}


t_start = time.time()
all_cols = list(range(len(NAMES)))
no_edit = [i for i, k in enumerate(NAMES) if k not in EDIT]
design_years = list(range(FIRST_TEST_YEAR, 2020))
all_years = list(range(FIRST_TEST_YEAR, int(dates[-1][:4]) + 1))
results = {"h1": report(), "decision_points": len(ep), "real_decision_points": int(real.sum()), "features": NAMES}

# L2 penalty chosen once, by design-period Sharpe only (design years fitted first; validation years only for the choice).
grid = [0.001, 0.01, 0.1]
design = {}
q_design = {}
for reg in grid:
    q_design[reg] = walk_forward(reg, all_cols, design_years)
    design[reg] = evaluate(positions(q_design[reg]), *PERIODS["design"])["sharpe"]
    print(f"alpha {reg}: design Sharpe {design[reg]}  ({time.time() - t_start:.0f}s)")
reg = max(grid, key=lambda r: design[r])
print("chosen alpha", reg)

# The one validation run for the chosen penalty.
q = q_design[reg].copy()
for y, test, qt in Parallel(n_jobs=-1)(delayed(fit_year)(y, reg, all_cols) for y in all_years if y >= 2020):
    q[test] = qt
pos6 = positions(q)
results["h6"] = {"reg": reg, "design_grid": design, **report(q)}
results["h6"]["passed"] = bool(results["h6"]["validation"]["sharpe"] > max(0.0, 0.06))
results["h6"]["vs_h1_validation"] = paired(pos6, positions(), "validation")
results["h6"]["vs_h1_design"] = paired(pos6, positions(), "design")

# Reported, not tested: the same model without the H5 features; H3b over the same windows.
q_ne = walk_forward(reg, no_edit, all_years)
results["h6_no_edit"] = {"reg": reg, **report(q_ne)}
results["h6_no_edit"]["vs_h1_validation"] = paired(positions(q_ne), positions(), "validation")
h3 = json.load(open("research/results/h3.json"))
results["h3b_validation_sharpe"] = h3["h3b"]["validation"]["sharpe"]
# H3b positions are not stored; its daily record is rebuilt from research/h3_exit.py if needed. Paired against H1 only here.
results["runtime_s"] = round(time.time() - t_start)
json.dump(results, open("research/results/h6.json", "w"), indent=1)
with open("research/results/h6_daily.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["date", "pos_h1", "pos_h6", "net_h1", "net_h6"])
    pos1 = positions()
    nb, n6 = net_returns(pos1), net_returns(pos6)
    for i, d in enumerate(dates):
        w.writerow([d, int(pos1[i]), int(pos6[i]), f"{nb[i]:.8f}", f"{n6[i]:.8f}"])
for k in ("h1", "h6", "h6_no_edit"):
    r = results[k]
    print(f"{k:11s} design SR {r['design']['sharpe']:6.2f}  validation SR {r['validation']['sharpe']:6.2f}  post {r['post-freeze']['sharpe']:6.2f}" + (f"  exit share val {r['validation']['exit_share']}" if k != "h1" else ""))
print("vs H1 validation", results["h6"]["vs_h1_validation"], "| no-edit", results["h6_no_edit"]["vs_h1_validation"])
print("PASSED" if results["h6"]["passed"] else "FAILED", "runtime", results["runtime_s"], "s")
