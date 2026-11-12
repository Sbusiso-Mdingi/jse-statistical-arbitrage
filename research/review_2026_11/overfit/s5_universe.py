"""Rebuild explore_gap's 50 trade specs on truncated data (no file writes in repo), plus an expanded EG grid.
Saves per-trade nets (futures) with open index and daily futures net series."""
import sys, pickle, os; sys.path.insert(0, "/tmp/jse-review/overfit")
from common import *
os.chdir(REPO)
import explore_gap as eg_mod  # functions only; main() not called
import h15_forecast as h15
from sklearn.linear_model import LogisticRegression
d, dates, x, y, rs, rn, dev0 = setup(); n = len(dates)
N = 60
W = {L: eg_mod.wstats(x, y, L) for L in (63, 126, 252)}
w = W[126]
lab, _ = h15.labels(x, y, w["a"], w["b"], w["s"], w["z"])
last_dev = n - 1
dev = np.array([dates[i] >= START and i + N <= last_dev for i in range(n)])
dev_all = np.array([dates[i] >= START for i in range(n)])
ev = dev & ~np.isnan(lab)
specs = {"absz_eg126": [np.abs(w["z"]), w["eg"]], "absz_eg_multi": [np.abs(w["z"]), W[63]["eg"], w["eg"], W[252]["eg"]]}
P = {k: eg_mod.oof_probs(f, lab, dev, dates) for k, f in specs.items()}
U = {}
def add(name, trs, lo="2006-01-01"):
    daily, rows = score(trs, dates, rs, rn, "futures", lo)
    U[name] = {"v": np.array([r["net"] for r in rows]) * 1e4, "open": np.array([r["open"] for r in rows]), "daily": daily}
gates = {"always": np.ones(n, bool), "eg126_below_crit": w["eg"] < sw.EG_CRIT}
for k in specs:
    for th in (0.5, 0.55, 0.6, 0.65, 0.7):
        gates[f"p_{k}>{th}"] = np.nan_to_num(P[k], nan=0) > th
for g, m in gates.items():
    add(f"fixed|{g}", eg_mod.fixed_line_trades(x, y, w, m & dev))
    add(f"rolling|{g}", sw.trades((m & dev).astype(np.int8), np.full(n, 0.5), w["b"], w["z"], copula_on=False, hold_through=True))
X = np.column_stack([np.abs(w["z"]), w["eg"]]); p = np.full(n, np.nan); first = int(np.argmax(dev))
for yr in range(2009, 2027):
    s0 = next(i for i in range(n) if dates[i].year == yr); s1 = next((i for i in range(n) if dates[i].year == yr + 1), n)
    tr = ev.copy(); tr[s0 - N:] = False; tr[:first] = False
    m = LogisticRegression(C=1.0, max_iter=1000).fit(X[tr], lab[tr])
    te = np.arange(s0, s1); gg = ~np.isnan(X[te]).any(1); p[te[gg]] = m.predict_proba(X[te[gg]])[:, 1]
for th in (0.5, 0.55, 0.6, 0.65, 0.7):
    add(f"rolling|walk_forward_p>{th}|from_2009", run_rule(np.nan_to_num(p, nan=0) > th, w["b"], w["z"], dev_all), lo="2009-01-01")
for L in (63, 126, 252):
    for c in (-2.0, -2.4, -2.6, -2.8, -3.0, -3.34, -3.6):
        if L != 126 and c not in (-2.4, -2.8, -3.34): continue
        add(f"rolling|L{L}|eg<{c}", run_rule(W[L]["eg"] < c, W[L]["b"], W[L]["z"], dev_all))
for e in (1.0, 1.25, 1.75, 2.0):
    add(f"rolling|L126|eg<-2.8|entry{e}", run_rule(w["eg"] < -2.8, w["b"], w["z"], dev_all, entry=e))
def logret(name):
    px = dict(read_px(name)); out = np.zeros(n); prev = None
    for i, t in enumerate(dates):
        if t in px:
            if prev is not None: out[i] = math.log(px[t] / prev)
            prev = px[t]
    return out
sec = 0.5 * (logret("fsr") + logret("abg"))
xo, yo = eg_mod._own(d["r_sbk"], sec), eg_mod._own(d["r_ned"], sec)
dev_sec = np.array([dates[i] >= dt.date(2006, 7, 1) for i in range(n)])
with np.errstate(invalid="ignore", divide="ignore"):
    bo, zo, ego = sw.rolling(xo, yo)
for c in (None, -2.4, -2.8, -3.34):
    gate = np.ones(n, bool) if c is None else ego < c
    add(f"sector_hedged|eg<{c}", run_rule(gate, bo, zo, dev_sec))
print(len(U))
import json
ref = json.load(open("research/results/explore_gap.json"))["trades"]
bad = 0
for k, u in U.items():
    r = ref[k]["futures"]; mine = (len(u["v"]), round(float(u["v"].mean()), 1))
    if mine != (r["trades"], r["per_trade_bps"]): bad += 1; print("MISMATCH", k, mine, r)
print("mismatches", bad)
# expanded EG family grid
Ls = (63, 84, 105, 126, 147, 168, 189, 252)
WR = {L: rolling(x, y, L) for L in Ls}
G = {}
for L in Ls:
    b, z, egs = WR[L]
    for c in [round(-2.0 - 0.2 * i, 1) for i in range(10)]:
        for e in (1.0, 1.25, 1.5, 1.75, 2.0):
            trs = run_rule(egs < c, b, z, dev_all, entry=e)
            daily, rows = score(trs, dates, rs, rn)
            G[(L, c, e)] = {"v": np.array([r["net"] for r in rows]) * 1e4, "open": np.array([r["open"] for r in rows]), "daily": daily}
print("grid", len(G))
pickle.dump({"U": U, "G": G, "dates": dates, "dev_all": dev_all}, open("/tmp/jse-review/overfit/universe.pkl", "wb"))
