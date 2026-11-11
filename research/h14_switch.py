"""H14 (research/PROTOCOL.md): the spread while the long-run relationship holds, the copula when it breaks.

  python research/h14_switch.py select   # design calibration and the simulation that chooses the detector
  python research/h14_switch.py run      # the chosen detector on the record; writes h14.json and h14_daily.csv

The engine is service/app/switch.py, shared with the live service.
"""
import csv, json, math, sys
import datetime as dt
from multiprocessing import Pool
import numpy as np

sys.path.insert(0, "research"); sys.path.insert(0, "research/models"); sys.path.insert(0, "service")
from pairdata import load_pair  # noqa: E402
from app import switch as sw  # noqa: E402

SELECT = "research/results/h14_select.json"
PERIODS = {"design": ("2010-01-01", "2020-01-01"), "validation": ("2020-01-01", "2026-04-01"), "post_freeze": ("2026-04-01", "2100-01-01")}
CANDIDATES = [("E", None), ("C", 0.05), ("C", 0.10), ("B", 0.05), ("B", 0.10)]
HORIZON, BREAK_AT, N_EVAL, N_CAL = 252, 21, 1000, 2000
SEED_CAL, SEED_EVAL = 20261111, 20261112


def name(det, a):
    return det if a is None else f"{det}{int(a * 100):02d}"


def record():
    d = load_pair()
    dates = d["date"]
    x, y = np.cumsum(d["r_sbk"]), np.cumsum(d["r_ned"])  # log levels up to a constant, which the regression absorbs
    return d, dates, x, y


# ---------------------------------------------------------------- select
def calibration(dates, x, y):
    b, z, eg = sw.rolling(x, y)
    rows = []
    for t in range(len(dates)):
        ds = dates[t].isoformat()
        if PERIODS["design"][0] <= ds < PERIODS["design"][1] and eg[t] < sw.EG_CRIT:
            st = sw.cusum_start(x, y, t)
            xi, yi = x[t - sw.L + 1:t + 1], y[t - sw.L + 1:t + 1]
            u = yi - st["a"] - st["b"] * xi
            phi = float(u[1:] @ u[:-1] / (u[:-1] @ u[:-1]))
            e = u[1:] - phi * u[:-1]
            rows.append((st["b"], phi, float(e.std(ddof=1))))
    rows = np.array(rows)
    seg = json.load(open("research/results/cointegration.json"))["bai_perron"]["segments"]
    slopes = [s["slope"] for s in seg]
    design_r = np.array([r for r, t in zip(load_pair()["r_sbk"], dates) if PERIODS["design"][0] <= t.isoformat() < PERIODS["design"][1]])
    return {"windows": len(rows), "b": float(np.median(rows[:, 0])), "phi": float(np.median(rows[:, 1])), "sigma_e": float(np.median(rows[:, 2])),
            "delta": float(np.median(np.abs(np.diff(slopes)))), "bp_slopes": slopes}, design_r


def sim_path(rng, cal, rets, scenario, extra):
    """One path from a simulated spell's first close t0: x, y, eg and t0, or None if no spell starts."""
    b, phi, se = cal["b"], cal["phi"], cal["sigma_e"]
    walk = scenario == "n"
    n_max = sw.L + 3000 + extra
    x = np.cumsum(rng.choice(rets, n_max))
    e = rng.normal(0, se, n_max)
    u = np.zeros(n_max)
    for t in range(1, n_max):
        u[t] = (u[t - 1] if walk else phi * u[t - 1]) + e[t]
    y = b * x + u
    eg = np.full(n_max, np.nan)
    t0 = None
    for t in range(sw.L - 1, n_max - extra):
        eg[t] = sw.window_stats(x[t - sw.L + 1:t + 1], y[t - sw.L + 1:t + 1])[2]
        if eg[t] < sw.EG_CRIT:
            t0 = t; break
    if t0 is None:
        return None
    tb = t0 + BREAK_AT
    if scenario == "h":
        b2 = b + cal["delta"] * rng.choice([-1.0, 1.0])
        y[tb:] = (b * x[tb] + u[tb]) + b2 * (x[tb:] - x[tb]) + (u[tb:] - u[tb])
    elif scenario == "r":
        y[tb:] = b * x[tb:] + u[tb] + np.cumsum(np.concatenate([[0.0], e[tb + 1:]]))
    end = t0 + extra
    for t in range(t0 + 1, end):
        eg[t] = sw.window_stats(x[t - sw.L + 1:t + 1], y[t - sw.L + 1:t + 1])[2]
    return x[:end], y[:end], eg[:end], t0


def cal_worker(args):
    seed, cal, rets, count = args
    rng = np.random.default_rng(seed)
    out = {"C": [], "B": []}
    while len(out["C"]) < count:
        p = sim_path(rng, cal, rets, "s", HORIZON + 1)
        if p is None:
            continue
        x, y, eg, t0 = p
        st = sw.cusum_start(x, y, t0)
        cmax, bmax = -np.inf, -np.inf
        for t in range(t0 + 1, t0 + HORIZON + 1):
            st["s"] += y[t] - st["a"] - st["b"] * x[t]
            cmax = max(cmax, sw.cusum_stat(t - t0, st["s"], st["omega"]))
            bmax = max(bmax, sw.sup_f(x[t0 - sw.L + 1:t + 1], y[t0 - sw.L + 1:t + 1]))
        out["C"].append(cmax); out["B"].append(bmax)
    return out


def eval_worker(args):
    seed, cal, rets, scenario, count, crit = args
    rng = np.random.default_rng(seed)
    extra = (BREAK_AT if scenario in ("h", "r") else 0) + HORIZON + 1
    res = {name(*k): {"days": [], "delay": []} for k in CANDIDATES}
    done = 0
    while done < count:
        p = sim_path(rng, cal, rets, scenario, extra)
        if p is None:
            continue
        x, y, eg, t0 = p
        a = t0 + (BREAK_AT if scenario in ("h", "r") else 0)
        for det, al in CANDIDATES:
            k = name(det, al)
            m = sw.modes(x, y, eg, det, crit.get(k), start=t0)
            res[k]["days"].append(int(m[a + 1:a + 1 + HORIZON].sum()))
            if m[a]:
                off = np.flatnonzero(m[a + 1:a + 1 + HORIZON] == 0)
                res[k]["delay"].append(int(off[0] + 1) if len(off) else HORIZON)
        done += 1
    return res


def select():
    d, dates, x, y = record()
    cal, rets = calibration(dates, x, y)
    print("calibration:", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in cal.items() if k != "bp_slopes"})
    with Pool(8) as pool:
        parts = pool.map(cal_worker, [(SEED_CAL + i, cal, rets, N_CAL // 8) for i in range(8)])
        cstar = {k: np.concatenate([p[k] for p in parts]) for k in ("C", "B")}
        crit = {}
        for det, al in CANDIDATES:
            if al is None:
                continue
            q = float(np.quantile(cstar[det], 1 - al))
            crit[name(det, al)] = math.sqrt(max(q, 0.0)) if det == "C" else q
        print("thresholds:", {k: round(v, 3) for k, v in crit.items()})
        scores = {}
        for sc in ("s", "h", "r", "n"):
            parts = pool.map(eval_worker, [(SEED_EVAL + 100 * ord(sc) + i, cal, rets, sc, N_EVAL // 8, crit) for i in range(8)])
            scores[sc] = {}
            for det, al in CANDIDATES:
                k = name(det, al)
                days = np.concatenate([p[k]["days"] for p in parts]); delay = np.concatenate([p[k]["delay"] for p in parts])
                scores[sc][k] = {"mean_days": round(float(days.mean()), 1), "share": round(float(days.mean() / HORIZON), 3),
                                 "median_delay": float(np.median(delay)) if len(delay) else None, "in_spell_at_break": int(len(delay))}
            print(sc, {k: v["mean_days"] for k, v in scores[sc].items()})
    table = {}
    for det, al in CANDIDATES:
        k = name(det, al)
        table[k] = {"stable_share": scores["s"][k]["share"], "eligible": scores["s"][k]["share"] >= 0.90,
                    "break_score": round(float(np.mean([scores[sc][k]["mean_days"] for sc in ("h", "r", "n")])), 1)}
    eligible = [k for k in table if table[k]["eligible"]]
    chosen = min(eligible, key=lambda k: table[k]["break_score"]) if eligible else "E"
    print("table:", table, "\nchosen:", chosen)
    json.dump({"protocol": "research/PROTOCOL.md, H14", "computed": dt.date.today().isoformat(), "calibration": cal, "thresholds": crit,
               "horizon": HORIZON, "break_at": BREAK_AT, "paths_per_scenario": N_EVAL, "calibration_paths": N_CAL,
               "scores": scores, "table": table, "chosen": chosen}, open(SELECT, "w"), indent=1)


# ---------------------------------------------------------------- run
def stats(net, trs, mask, dates):
    x = net[mask]
    if not len(x):
        return None
    eq = np.cumprod(1 + x); sd = x.std(ddof=1)
    lo, hi = dates[int(np.argmax(mask))], dates[len(mask) - 1 - int(np.argmax(mask[::-1]))]
    tt = [t for t in trs if t["complete"] and lo <= dates[t["open"]] <= hi]
    v = np.array([t["net"] for t in tt]) * 1e4
    return {"sharpe": round(float(x.mean() / sd * math.sqrt(252)), 2) if sd > 0 else 0.0,
            "cagr": round(float(eq[-1] ** (252 / len(x)) - 1), 4), "mdd": round(float((eq / np.maximum.accumulate(eq) - 1).min()), 4),
            "trades": len(tt), "per_trade_bps": round(float(v.mean()), 1) if len(v) else None,
            "se_bps": round(float(v.std(ddof=1) / math.sqrt(len(v))), 1) if len(v) > 1 else None,
            "spread_trades": sum(t["method"] == "spread" for t in tt),
            **{f"{m_}_per_trade_bps": (round(float(np.mean([t["net"] for t in tt if t["method"] == m_]) * 1e4), 1) if any(t["method"] == m_ for t in tt) else None)
               for m_ in ("spread", "copula")}}


def run():
    sel = json.load(open(SELECT))
    chosen = sel["chosen"]; crit = sel["thresholds"]
    d, dates_all, x, y = record()
    b, z, eg = sw.rolling(x, y)
    gas = {r["date"]: float(r["h"]) for r in csv.DictReader(open("research/results/copulas_py.csv")) if r["model"] == "gas_t"}
    keep = np.array([t.isoformat() in gas for t in dates_all])
    first = int(np.argmax(keep))
    assert keep[first:].all(), "the copula record has gaps inside the price record"
    full_modes = {name(det, al): sw.modes(x, y, eg, det, crit.get(name(det, al))) for det, al in CANDIDATES}
    sl = slice(first, None)
    dates = dates_all[sl]; ds = [t.isoformat() for t in dates]; n = len(dates)
    h = np.array([gas[t] for t in ds])
    rs, rn = np.expm1(d["r_sbk"][sl]), np.expm1(d["r_ned"][sl])
    bb, zz, ee = b[sl], z[sl], eg[sl]
    mode = full_modes[chosen][sl]
    gate = full_modes["E"][sl]
    strategies = {
        "switch": sw.trades(mode, h, bb, zz),
        "copula_alone": sw.trades(np.zeros(n, np.int8), h, bb, zz, spread_on=False),
        "spread_alone": sw.trades(gate, h, bb, zz, copula_on=False, hold_through=True),
    }
    masks = {k: np.array([a <= t < c for t in ds]) for k, (a, c) in PERIODS.items()}

    # Parity: the two halves alone reproduce their recorded figures.
    pair = json.load(open("research/results/pair.json"))["costs"]["tiers"]["institutional"]
    deriv = json.load(open("research/results/derivative_costs.json"))
    h4 = json.load(open("research/results/h4.json"))["chosen"]["H4b"]
    net_c, rows_c = sw.daily_returns(strategies["copula_alone"], dates, rs, rn, "cash")
    net_f, _ = sw.daily_returns(strategies["copula_alone"], dates, rs, rn, "futures")
    g4, rows4 = sw.daily_returns(strategies["spread_alone"], dates, rs, rn, None)
    flat = g4.copy()
    for t in rows4:
        c = abs(t["w_sbk"]) + abs(t["w_ned"])
        flat[t["open"]] -= c * 10 / 1e4
        if t["complete"]:
            flat[t["close"]] -= c * 10 / 1e4
    parity = {"copula_alone_cash_design_sharpe": [stats(net_c, rows_c, masks["design"], dates)["sharpe"], pair["design"]["sharpe"]],
              "copula_alone_futures_design_sharpe": [stats(net_f, rows_c, masks["design"], dates)["sharpe"], deriv["derivatives"]["ssf_institutional"]["design"]["sharpe"]],
              "spread_alone_10bps_design_sharpe": [stats(flat, rows4, masks["design"], dates)["sharpe"], h4["design"]["after_costs"]["sharpe"]],
              "spread_alone_10bps_validation_sharpe": [stats(flat, rows4, masks["validation"], dates)["sharpe"], h4["validation"]["after_costs"]["sharpe"]],
              "spread_alone_design_trades": [sum(1 for t in rows4 if ds[t["open"]] < "2020-01-01"), h4["design"]["after_costs"]["entries"]]}
    print("parity (this script, recorded):", parity)

    out = {"protocol": "research/PROTOCOL.md, H14", "chosen_detector": chosen, "first": ds[0], "last": ds[-1], "parity": parity,
           "note": "validation (2020 to March 2026) is already seen: both halves were scored on it before H14; reported, not a test",
           "periods": {}, "by_year": [], "mode_share_by_year": {}, "after_bp_breaks": [], "latest": {}}
    daily = {}
    for k, trs in strategies.items():
        for sched in ("cash", "futures"):
            net, rows = sw.daily_returns(trs, dates, rs, rn, sched)
            daily[(k, sched)] = (net, rows)
            for method in ("spread", "copula"):
                daily[(k, sched, method)] = sw.daily_returns([t for t in trs if t["method"] == method], dates, rs, rn, sched)
        daily[(k, "gross")] = sw.daily_returns(trs, dates, rs, rn, None)
    for p, m in masks.items():
        label = "validation_already_seen" if p == "validation" else p
        out["periods"][label] = {"spread_mode_share": round(float(mode[m].mean()), 3)}
        for k in strategies:
            out["periods"][label][k] = {s: stats(*daily[(k, s)], m, dates) for s in ("gross", "cash", "futures")}
        dd = (daily[("switch", "futures")][0] - daily[("copula_alone", "futures")][0])[m]
        out["periods"][label]["switch_vs_copula_futures"] = {"bps_per_year": round(float(dd.mean() * 252 * 1e4), 1),
                                                             "t_stat": round(float(dd.mean() / (dd.std(ddof=1) / math.sqrt(len(dd)))), 2) if dd.std() > 0 else None}
    years = sorted({t[:4] for t in ds})
    for yr in years:
        m = np.array([t[:4] == yr for t in ds])
        row = {"year": int(yr), "sessions": int(m.sum()), "spread_mode_share": round(float(mode[m].mean()), 3)}
        for sched in ("cash", "futures"):
            row[f"switch_spread_mode_{sched}"] = round(float(daily[("switch", sched, "spread")][0][m].sum()), 4)
            row[f"switch_copula_mode_{sched}"] = round(float(daily[("switch", sched, "copula")][0][m].sum()), 4)
            row[f"switch_{sched}"] = round(float(daily[("switch", sched)][0][m].sum()), 4)
            row[f"copula_alone_{sched}"] = round(float(daily[("copula_alone", sched)][0][m].sum()), 4)
            row[f"spread_alone_{sched}"] = round(float(daily[("spread_alone", sched)][0][m].sum()), 4)
        row["spread_mode_trades"] = sum(1 for t in daily[("switch", "cash")][1] if t["method"] == "spread" and ds[t["open"]][:4] == yr)
        row["copula_mode_trades"] = sum(1 for t in daily[("switch", "cash")][1] if t["method"] == "copula" and ds[t["open"]][:4] == yr)
        out["by_year"].append(row)
        out["mode_share_by_year"][yr] = {k: round(float(v[sl][m].mean()), 3) for k, v in full_modes.items()}
    bp = json.load(open("research/results/cointegration.json"))["bai_perron"]["breaks"]
    for brk in bp:
        if PERIODS["design"][0] <= brk < PERIODS["design"][1]:
            i = next(j for j, t in enumerate(ds) if t > brk)
            out["after_bp_breaks"].append({"break": brk, "spread_sessions_in_next_252": int(mode[i:i + 252].sum()),
                                           "in_spread_mode_at_break": bool(mode[i - 1])})
    seg = json.load(open("research/results/cointegration.json"))["bai_perron"]["segments"][-1]
    out["latest"] = {"date": ds[-1], "eg126": round(float(ee[-1]), 3), "crit": sw.EG_CRIT, "b126": round(float(bb[-1]), 3), "mode": "spread" if mode[-1] else "copula",
                     "last_spread_close": next((ds[i] for i in range(n - 1, -1, -1) if mode[i]), None),
                     "bai_perron_last_segment": seg}
    out["transitions"] = int(np.abs(np.diff(mode.astype(int))).sum())
    json.dump(out, open("research/results/h14.json", "w"), indent=1)
    # The frozen record the service serves: the chosen detector carries no fitted parameter, so this is the
    # rule's identity, the dates and the reference figures the dashboard shows.
    json.dump({"protocol": "research/PROTOCOL.md, H14", "frozen_on": "2026-11-11", "score_from": "2026-11-12", "detector": chosen,
               "threshold": crit.get(chosen), "window": sw.L, "crit": sw.EG_CRIT,
               "verdict": "225 completed trades or 31 December 2030; mean net per trade at the institutional futures schedule above zero, one-sided t > 1.65",
               "bai_perron": json.load(open("research/results/cointegration.json"))["bai_perron"],
               "spread_mode_share_by_year": {r["year"]: r["spread_mode_share"] for r in out["by_year"]},
               "reference": {p: {"spread_mode_share": r["spread_mode_share"], "switch_vs_copula_t": r["switch_vs_copula_futures"]["t_stat"],
                                 **{k: {s_: r[k][s_]["per_trade_bps"] for s_ in ("cash", "futures")} | {"trades": r[k]["futures"]["trades"]}
                                    for k in ("switch", "copula_alone")}}
                             for p, r in out["periods"].items() if p != "post_freeze"}},
              open("data/pair_switch.json", "w"), indent=1)
    with open("research/results/h14_daily.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "eg126", "crit", "hedge_ratio126", "z126", "mode", "h", "switch_net_cash", "switch_net_futures",
                    "copula_alone_net_cash", "copula_alone_net_futures", "spread_alone_net_cash", "spread_alone_net_futures"])
        for i in range(n):
            w.writerow([ds[i], "" if np.isnan(ee[i]) else f"{ee[i]:.4f}", sw.EG_CRIT, "" if np.isnan(bb[i]) else f"{bb[i]:.4f}", "" if np.isnan(zz[i]) else f"{zz[i]:.4f}",
                        "spread" if mode[i] else "copula", f"{h[i]:.5f}"] + [f"{daily[(k, s)][0][i]:.6f}" for k in strategies for s in ("cash", "futures")])
    with open("research/results/h14_by_year.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out["by_year"][0])); w.writeheader(); w.writerows(out["by_year"])
    for p, r in out["periods"].items():
        print(p, "spread share", r["spread_mode_share"])
        for k in strategies:
            print(f"   {k:13s}", {s: (r[k][s]["sharpe"], r[k][s]["per_trade_bps"], r[k][s]["trades"], r[k][s]["spread_trades"], r[k][s]["spread_per_trade_bps"], r[k][s]["copula_per_trade_bps"]) for s in ("gross", "cash", "futures")})
        print("   switch vs copula, futures", r["switch_vs_copula_futures"])
    print("mode share by year", {y_: v[chosen] for y_, v in out["mode_share_by_year"].items()})
    print("after BP breaks", out["after_bp_breaks"]); print("latest", out["latest"]); print("transitions", out["transitions"])


if __name__ == "__main__":
    {"select": select, "run": run}[sys.argv[1]]()
