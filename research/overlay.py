"""Overlay: timing a trade that must be done anyway (research/PROTOCOL.md). Reporting only.
Writes research/results/overlay.json."""
import csv, json, math, datetime as dt
from collections import defaultdict
import numpy as np
import sys
sys.path.insert(0, "research")
from h5_weights import load, BASKET, _read_px  # noqa: E402

rng = np.random.default_rng(7)
d = load()
gas = json.load(open("data/basket_gas.json"))["history"]
gh = dict(zip(gas["date"], gas["h"]))
idx = [i for i, x in enumerate(d["date"]) if x.isoformat() in gh]
dates = [d["date"][i].isoformat() for i in idx]; n = len(dates)
h = np.array([gh[x] for x in dates])
# price levels (relative): cumulative products of simple returns
ps = np.cumprod(1 + d["simple"]["sbk"][idx]); pb = np.cumprod(1 + np.mean([d["simple"][k] for k in BASKET], axis=0)[idx])
years = np.array([int(x[:4]) for x in dates])


def improvement(p_long, p_short, i_base, i_fill):
    """bps gained by filling a 'buy long leg / sell short leg' trade at i_fill instead of i_base, half notional each leg."""
    return 0.5 * (math.log(p_long[i_base] / p_long[i_fill]) + math.log(p_short[i_fill] / p_short[i_base])) * 1e4


def run(p_long, p_short, hsig, favour, W, fill_offset=0):
    """favour(h) -> True when the signal says the long leg is cheap. fill_offset shifts fills (0 = at that close)."""
    rows = []
    for t in range(0, n - W - 1 - fill_offset):
        base = t + 1 + fill_offset
        chosen = None
        for s in range(t + 2, t + W + 1):
            if favour(hsig[s - 1]):
                chosen = s + fill_offset; break
        fill = chosen if chosen is not None else t + W + fill_offset
        pl = rng.integers(t + 1, t + W + 1) + fill_offset
        rows.append((years[t], improvement(p_long, p_short, base, fill), improvement(p_long, p_short, base, pl), chosen is not None, t))
    return rows


def boot(x, B=10000, L=20):
    r = np.random.default_rng(11); k = math.ceil(len(x) / L)
    starts = r.integers(0, len(x) - L, size=(B, k))
    m = np.array([np.concatenate([x[a:a + L] for a in row])[:len(x)].mean() for row in starts])
    return [round(float(v), 1) for v in np.percentile(m, [2.5, 97.5])]


def summarise(rows):
    by = defaultdict(list)
    for y, a, b, c, t in rows:
        by[t].append((y, a, b, c))
    ts = sorted(by)
    yr = np.array([by[t][0][0] for t in ts]); a = np.array([np.mean([r[1] for r in by[t]]) for t in ts])
    b = np.array([np.mean([r[2] for r in by[t]]) for t in ts]); c = np.array([np.mean([r[3] for r in by[t]]) for t in ts])
    cond = [(y, v) for y, v, _, hit, _ in rows if hit]
    cy = np.array([q[0] for q in cond]); cv = np.array([q[1] for q in cond])
    out = {}
    for name, lo, hi in (("2010_2019", 2010, 2020), ("2020_2026", 2020, 2100), ("2021_2026", 2021, 2100)):
        m = (yr >= lo) & (yr < hi); mc = (cy >= lo) & (cy < hi)
        if m.sum() < 40: continue
        out[name] = {"sessions": int(m.sum()), "overlay_bps": round(float(a[m].mean()), 2), "ci95": boot(a[m]),
                     "placebo_bps": round(float(b[m].mean()), 2), "placebo_ci95": boot(b[m]),
                     "share_of_trades_with_signal": round(float(c[m].mean()), 3),
                     "when_signal_arrives_bps": round(float(cv[mc].mean()), 1), "when_signal_arrives_n": int(mc.sum())}
    out["by_year"] = [{"year": int(y), "overlay_bps": round(float(a[yr == y].mean()), 1)} for y in sorted(set(yr))]
    return out


out = {"basket": {}}
for W in (5, 10):
    buy = run(ps, pb, h, lambda x: x > 0.95, W)          # buy SBK / sell basket: wants SBK cheap
    sell = run(pb, ps, h, lambda x: x < 0.05, W)         # sell SBK / buy basket: wants SBK rich
    out["basket"][f"W{W}"] = {"buy_sbk": summarise(buy), "sell_sbk": summarise(sell), "both": summarise(buy + sell)}
    b = out["basket"][f"W{W}"]["both"]
    print("basket", W, json.dumps({k: v for k, v in b.items() if k != "by_year"}))

# The pair with next-morning fills from the hourly bars.
bars = {}
for name in ("sbk", "ned"):
    bb = defaultdict(dict)
    for r in csv.DictReader(open(f"data/raw/{name}_60m.csv")):
        tt = dt.datetime.utcfromtimestamp(int(r["time"])); bb[tt.date()][tt.hour] = float(r["close"])
    bars[name] = bb
pair_h = {r["date"]: float(r["h"]) for r in csv.DictReader(open("research/results/copulas_py.csv")) if r["model"] == "gas_t"}
px_s, px_n = dict(_read_px("sbk")), dict(_read_px("ned"))
pdays = [dt.date.fromisoformat(x) for x in sorted(pair_h) if dt.date.fromisoformat(x) in bars["sbk"] and dt.date.fromisoformat(x) in bars["ned"] and 7 in bars["sbk"][dt.date.fromisoformat(x)] and 7 in bars["ned"][dt.date.fromisoformat(x)]]
open_s = np.array([bars["sbk"][x][7] for x in pdays]); open_n = np.array([bars["ned"][x][7] for x in pdays])
close_s = np.array([px_s[x] for x in pdays]); close_n = np.array([px_n[x] for x in pdays])
hp = np.array([pair_h[x.isoformat()] for x in pdays]); yp = np.array([x.year for x in pdays])
n_p = len(pdays)
out["pair_next_morning"] = {}
for W in (5, 10):
    rows_all = []
    for long_leg, short_leg, fav in ((("s", "n"), None, lambda x: x > 0.95), (("n", "s"), None, lambda x: x < 0.05)):
        pl_o = open_s if long_leg[0] == "s" else open_n; psh_o = open_n if long_leg[0] == "s" else open_s
        for t in range(0, n_p - W - 1):
            base = t + 1
            chosen = next((s for s in range(t + 2, t + W + 1) if fav(hp[s - 1])), None)
            fill = chosen if chosen is not None else t + W
            pl = rng.integers(t + 1, t + W + 1)
            imp = improvement(pl_o, psh_o, base, fill)
            imp_pl = improvement(pl_o, psh_o, base, pl)
            rows_all.append((yp[t], imp, imp_pl, chosen is not None, t))
    out["pair_next_morning"][f"W{W}"] = summarise(rows_all)
    b = out["pair_next_morning"][f"W{W}"]
    print("pair 10:00", W, json.dumps({k: v for k, v in b.items() if k != "by_year"}))
json.dump(out, open("research/results/overlay.json", "w"), indent=1)
