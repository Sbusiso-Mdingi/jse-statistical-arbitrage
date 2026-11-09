"""Red team: seven attacks on the instrument's one result (research/PROTOCOL.md). Each runs once.

Usage: python research/redteam.py [all|lag|cleaning|loo|placebo|basketcost|overlay|combine]
Writes research/results/redteam.json (merging sections as they finish).
"""
import csv, json, math, os, sys, time
from collections import defaultdict
import datetime as dt
import numpy as np
from joblib import Parallel, delayed
sys.path.insert(0, "research"); sys.path.insert(0, "research/models")
from h5_weights import load, positions, net_returns, PERIODS, BASKET, _read_px  # noqa: E402
from costs import TIERS, VAT  # noqa: E402

OUT = "research/results/redteam.json"
HOLD = 5
rng = np.random.default_rng(20261109)

d = load()
gas = json.load(open("data/basket_gas.json"))["history"]
gh = dict(zip(gas["date"], gas["h"]))
idx = [i for i, x in enumerate(d["date"]) if x.isoformat() in gh]
dates = [d["date"][i].isoformat() for i in idx]
n = len(dates)
h = np.array([gh[x] for x in dates])
rs = d["simple"]["sbk"][idx]
member = {k: d["simple"][k][idx] for k in BASKET}
rb = np.mean([member[k] for k in BASKET], axis=0)
spread = 0.5 * (rs - rb)
years = np.array([int(x[:4]) for x in dates])
sig_idx = np.flatnonzero((np.abs(h - 0.5) > 0.45) & (np.arange(n) + HOLD < n))
direction = np.where(h[sig_idx] > 0.5, 1.0, -1.0)


def save(section, payload):
    cur = json.load(open(OUT)) if os.path.exists(OUT) else {}
    cur[section] = payload
    json.dump(cur, open(OUT, "w"), indent=1)


def per_signal(lag=0, mask=None):
    """Gross return per signal (bps of capital) over the five-day hold entered `lag` closes after the signal."""
    vals, yrs = [], []
    for t, dd in zip(sig_idx, direction):
        a = t + 1 + lag
        if a + HOLD > n:
            continue
        if mask is not None and not mask[t]:
            continue
        vals.append(dd * spread[a:a + HOLD].sum() * 1e4)
        yrs.append(years[t])
    return np.array(vals), np.array(yrs)


def summarise(vals, yrs):
    out = {}
    for name, lo, hi in (("2010_2019", 2010, 2020), ("2020_2026", 2020, 2100), ("2021_2026", 2021, 2100)):
        m = (yrs >= lo) & (yrs < hi)
        x = vals[m]
        out[name] = {"n": int(m.sum()), "bps": round(float(x.mean()), 1), "se": round(float(x.std(ddof=1) / math.sqrt(m.sum())), 1)} if m.sum() > 1 else None
    return out


def rule_sharpes(pos_shift=0):
    """The rule's Sharpe by period and cost tier with positions taken `pos_shift` closes late."""
    pos = positions(h)
    if pos_shift:
        pos = np.concatenate([np.zeros(pos_shift), pos[:-pos_shift]])
    held = np.concatenate([[0.0], pos[:-1]])
    gross = held * spread
    res = {}
    for tier, t in TIERS.items():
        from costs import costs as cost_fn
        net = gross - cost_fn(pos, t)
        res[tier] = {}
        for p, (a, b) in PERIODS.items():
            m = np.array([a <= x < b for x in dates]); x = net[m]
            res[tier][p] = round(float(x.mean() / x.std(ddof=1) * math.sqrt(252)), 2) if x.std(ddof=1) > 0 else 0.0
    return res


# ---------------------------------------------------------------- 1. execution lag
def attack_lag():
    out = {"basket": {}}
    for lag in (0, 1, 2):
        v, y = per_signal(lag)
        out["basket"][f"lag_{lag}_closes"] = {"per_signal": summarise(v, y), "rule_sharpe": rule_sharpes(lag)}
    # the pair at the next 10:00 bar: hourly closes for SBK and NED
    def bars(name):
        b = defaultdict(dict)
        for r in csv.DictReader(open(f"data/raw/{name}_60m.csv")):
            t = dt.datetime.utcfromtimestamp(int(r["time"])); b[t.date()][t.hour] = float(r["close"])
        return b
    S, N = bars("sbk"), bars("ned")
    pair_h = {r["date"]: float(r["h"]) for r in csv.DictReader(open("research/results/copulas_py.csv")) if r["model"] == "gas_t"}
    px_s, px_n = dict(_read_px("sbk")), dict(_read_px("ned"))
    pdates = sorted(x for x in pair_h if dt.date.fromisoformat(x) in S and dt.date.fromisoformat(x) in px_s)
    pd_ = [dt.date.fromisoformat(x) for x in pdates]
    res = {"close_to_close": [], "next_open_to_close": [], "years": []}
    for i, x in enumerate(pdates[:-HOLD - 1]):
        hh = pair_h[x]
        if abs(hh - 0.5) <= 0.45:
            continue
        dd = 1.0 if hh > 0.5 else -1.0  # NED high relative to SBK: long SBK / short NED
        d0, d1, d5 = pd_[i], pd_[i + 1], pd_[i + HOLD]
        if 7 not in S.get(d1, {}) or 7 not in N.get(d1, {}):
            continue
        cc = dd * 0.5 * ((px_s[d5] / px_s[d0] - 1) - (px_n[d5] / px_n[d0] - 1)) * 1e4
        oc = dd * 0.5 * ((px_s[d5] / S[d1][7] - 1) - (px_n[d5] / N[d1][7] - 1)) * 1e4  # filled at the 10:00 bar close next day
        res["close_to_close"].append(cc); res["next_open_to_close"].append(oc); res["years"].append(d0.year)
    yrs = np.array(res["years"])
    out["pair"] = {k: summarise(np.array(res[k]), yrs) for k in ("close_to_close", "next_open_to_close")}
    save("lag", out)
    print("lag:", json.dumps(out["basket"]["lag_1_closes"]["per_signal"]), "| pair next-open", out["pair"]["next_open_to_close"]["2010_2019"])


# ---------------------------------------------------------------- 2. causal cleaning
def attack_cleaning():
    def causal_clean(rows, jump=0.4):
        out = []; prev = None
        dropped = []
        for dte, a in rows:
            if prev is not None and abs(math.log(a / prev)) > math.log(1 + jump):
                dropped.append(dte.isoformat()); out.append((dte, prev)); continue  # carry the previous price
            out.append((dte, a)); prev = a
        return out, dropped
    report = {}
    for k in ["sbk"] + BASKET:
        raw = []
        for r in csv.DictReader(open(f"data/raw/{k}.csv")):
            try:
                a = float(r["adjusted"])
            except ValueError:
                continue
            if a > 0:
                raw.append((dt.date.fromisoformat(r["date"]), a))
        current = dict(_read_px(k))
        causal, dropped = causal_clean(raw)
        causal = dict(causal)
        diff_days = [x.isoformat() for x in sorted(set(current) & set(causal)) if abs(current[x] / causal[x] - 1) > 1e-9]
        removed_by_current = [x.isoformat() for x, _ in raw if x not in current]
        report[k] = {"causal_rule_flags": dropped, "current_rule_removes": removed_by_current, "days_with_different_price": diff_days[:20], "n_different": len(diff_days)}
    save("cleaning", report)
    print("cleaning:", {k: (v["causal_rule_flags"], v["current_rule_removes"], v["n_different"]) for k, v in report.items()})


# ---------------------------------------------------------------- 3. leave-one-year-out
def attack_loo():
    v, y = per_signal(0)
    out = {"full_period_bps": round(float(v.mean()), 1), "without": {}}
    for yr in sorted(set(y)):
        m = y != yr
        out["without"][str(yr)] = {"all": round(float(v[m].mean()), 1), "2010_2019": round(float(v[m & (y < 2020)].mean()), 1) if (m & (y < 2020)).any() else None,
                                  "2020_2026": round(float(v[m & (y >= 2020)].mean()), 1) if (m & (y >= 2020)).any() else None}
    save("loo", out)
    print("leave-one-year-out: without 2020 ->", out["without"]["2020"], "| without 2015 ->", out["without"]["2015"])


# ---------------------------------------------------------------- 4. placebo
def attack_placebo(draws=10000):
    v, y = per_signal(0)
    counts = {yr: int((y == yr).sum()) for yr in sorted(set(y))}
    day_pool = {yr: np.flatnonzero((years == yr) & (np.arange(n) + 1 + HOLD <= n)) for yr in counts}

    def one(seed):
        r = np.random.default_rng(seed)
        res = {}
        for name, lo, hi in (("2010_2019", 2010, 2020), ("2020_2026", 2020, 2100), ("2021_2026", 2021, 2100)):
            vals = []
            for yr, c in counts.items():
                if not (lo <= yr < hi) or c == 0:
                    continue
                picks = r.choice(day_pool[yr], size=c, replace=False)
                signs = r.choice([-1.0, 1.0], size=c)
                vals += [s * spread[t + 1:t + 1 + HOLD].sum() * 1e4 for t, s in zip(picks, signs)]
            res[name] = float(np.mean(vals)) if vals else float("nan")
        return res

    sims = Parallel(n_jobs=-1)(delayed(one)(s) for s in range(draws))
    actual = summarise(v, y)
    out = {"draws": draws, "periods": {}}
    for name in ("2010_2019", "2020_2026", "2021_2026"):
        dist = np.array([s[name] for s in sims])
        a = actual[name]["bps"]
        out["periods"][name] = {"actual_bps": a, "placebo_mean": round(float(dist.mean()), 1), "placebo_sd": round(float(dist.std()), 1),
                                "percentile": round(float((dist < a).mean() * 100), 1)}
    # the same with random direction but the signal's own days: isolates timing from direction
    dir_sims = []
    for s in range(2000):
        r = np.random.default_rng(10**6 + s)
        signs = r.choice([-1.0, 1.0], size=len(sig_idx))
        vals = np.array([sg * spread[t + 1:t + 1 + HOLD].sum() * 1e4 for t, sg in zip(sig_idx, signs)])
        dir_sims.append({name: float(vals[(y >= lo) & (y < hi)].mean()) for name, lo, hi in (("2010_2019", 2010, 2020), ("2021_2026", 2021, 2100))})
    out["random_direction_same_days"] = {name: {"percentile": round(float((np.array([s[name] for s in dir_sims]) < actual[name]["bps"]).mean() * 100), 1)} for name in ("2010_2019", "2021_2026")}
    save("placebo", out)
    print("placebo:", out["periods"], "| direction only:", out["random_direction_same_days"])


# ---------------------------------------------------------------- 5. full basket costs
def attack_basketcost():
    # Daily rebalancing turnover of an equal-weight basket of four, as a share of the basket's notional.
    w = np.array([0.25] * 4)
    turn = np.zeros(n)
    for t in range(n):
        g = np.array([1 + member[k][t] for k in BASKET])
        drift = w * g / (w * g).sum()
        turn[t] = np.abs(drift - w).sum()  # buys + sells needed to return to equal weight
    pos = positions(h)
    held = np.concatenate([[0.0], pos[:-1]])
    out = {}
    for tier in ("institutional", "retail"):
        t = TIERS[tier]
        per_exec = (t["brokerage"] * (1 + VAT) + t["spread"] + t["strate"]) / 1e4
        # basket notional is 0.5 of capital while held; half of the turnover is purchases
        rebal = 0.5 * np.abs(held) * turn * (per_exec + 0.5 * t["stt"] / 1e4)
        trades = int((np.diff(np.concatenate([[0.0], pos])) != 0).sum() / 2) or 1
        out[tier] = {"mean_daily_turnover_pct": round(float(turn.mean() * 100), 2), "rebalancing_cost_per_round_trip_bps": round(float(rebal.sum() / trades * 1e4), 1),
                     "rebalancing_cost_per_year_bps": round(float(rebal.sum() / (n / 252) * 1e4), 1)}
    save("basketcost", out)
    print("basket rebalancing:", out)


# ---------------------------------------------------------------- 6. the overlay
def attack_overlay():
    v, y = per_signal(0)
    out = {}
    for name, lo, hi in (("2010_2019", 2010, 2020), ("2020_2026", 2020, 2100), ("2021_2026", 2021, 2100)):
        x = v[(y >= lo) & (y < hi)]
        if len(x) < 5:
            continue
        # block bootstrap on consecutive signals (blocks of 10) for the mean
        B = 10000; L = 10
        means = []
        for b in range(B):
            starts = rng.integers(0, max(len(x) - L, 1), size=math.ceil(len(x) / L))
            samp = np.concatenate([x[s:s + L] for s in starts])[:len(x)]
            means.append(samp.mean())
        lo_ci, hi_ci = np.percentile(means, [2.5, 97.5])
        wins = int((x > 0).sum())
        from scipy import stats as st
        out[name] = {"n": len(x), "bps": round(float(x.mean()), 1), "ci95": [round(float(lo_ci), 1), round(float(hi_ci), 1)],
                     "share_positive": round(wins / len(x), 3), "sign_test_p": round(float(st.binomtest(wins, len(x), 0.5).pvalue), 4)}
    save("overlay", out)
    print("overlay:", out)


# ---------------------------------------------------------------- 7. copula combination
def attack_combine():
    out = {}
    for label, path in (("pair", "research/results/copulas_py.csv"), ("basket", "research/results/copulas_basket.csv")):
        rows = list(csv.DictReader(open(path)))
        by = defaultdict(dict)
        for r in rows:
            by[r["date"]][r["model"]] = float(r["logc"])
        out[label] = {}
        for p, (a, b) in (("design", ("2010-01-01", "2020-01-01")), ("validation", ("2020-01-01", "2026-04-01"))):
            ds = sorted(x for x in by if a <= x < b and "gas_t" in by[x] and "ms_t" in by[x])
            g = np.array([by[x]["gas_t"] for x in ds]); m = np.array([by[x]["ms_t"] for x in ds])
            mix = np.logaddexp(g, m) - math.log(2)
            diff = mix - g
            mu = diff.mean(); T = len(diff)
            gk = lambda k: float(np.sum((diff[k:] - mu) * (diff[:-k] - mu)) / T) if k else float(np.var(diff))
            var = gk(0) + 2 * sum((1 - k / 6) * gk(k) for k in range(1, 6))
            out[label][p] = {"gain_per_day_x1000": round(float(mu * 1000), 2), "dm_t": round(float(mu / math.sqrt(var / T)), 2) if var > 0 else 0.0, "n": T}
    save("combine", out)
    print("combination:", out)


ATTACKS = {"lag": attack_lag, "cleaning": attack_cleaning, "loo": attack_loo, "placebo": attack_placebo, "basketcost": attack_basketcost, "overlay": attack_overlay, "combine": attack_combine}
if __name__ == "__main__":
    which = sys.argv[1:] or ["all"]
    t0 = time.time()
    for k in (ATTACKS if which == ["all"] else which):
        ATTACKS[k]()
    print(f"done in {time.time() - t0:.0f}s")
