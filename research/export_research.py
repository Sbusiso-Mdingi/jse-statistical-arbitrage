"""Collect the decay study and every tested rule into data/research.json for the dashboard.

Run after research/decay.py, research/h1_evaluate.py, research/h2_news.py, research/h3_exit.py,
research/04_cointegration.R and research/h4_cointegration.py.
"""
import json, sys
from datetime import date
import numpy as np

sys.path.insert(0, "service")
from app.main import HISTORY, cache, folds  # noqa: E402
from app.strategy import Params, backtest, metrics  # noqa: E402

PERIODS = {"design": ("2010-01-01", "2020-01-01"), "validation": ("2020-01-01", "2026-04-01"), "post_freeze": ("2026-04-01", "2100-01-01")}


def v1(period):
    s, e = (date.fromisoformat(x) for x in PERIODS[period])
    live = cache.rows
    allr = {k: (HISTORY[k] + live[k] if k == "date" else np.concatenate([HISTORY[k], live[k]])) for k in HISTORY}
    m = np.array([s <= d < e for d in allr["date"]])
    rows = {k: ([d for d, keep in zip(v, m) if keep] if k == "date" else v[m]) for k, v in allr.items()}
    bt = backtest(rows, folds, Params())
    r = metrics(rows["date"], bt["daily"], bt["equity"], bt["position"], bt["trades"])
    return {"sharpe": round(r["sharpe"], 2), "sortino": round(r["sortino"], 2), "cagr": round(r["cagr"], 4), "mdd": round(r["max_drawdown"], 4)}


def pick(r):
    return {"sharpe": r["sharpe"], "sortino": r["sortino"], "cagr": r["cagr"], "mdd": r["mdd"]}


h1 = json.load(open("research/results/h1.json"))
h2 = json.load(open("research/results/h2.json"))["results"]
rule5 = lambda k: {p: pick(h2[n][k]) for p, n in (("design", "design"), ("validation", "validation"), ("post_freeze", "post-freeze"))}

tests = [
    {"id": "v1", "name": "Report rule", "detail": "SBK against NED. Daily signal, opens past the 90th training percentile, closes below the 50th, volatility filter at the 80th. Refitted yearly.",
     "pass_mark": None, **{p: v1(p) for p in PERIODS}},
    {"id": "hold5", "name": "Five-day hold", "detail": "SBK against NED. Best of 78 rules on design data: open past the 90th percentile and hold five days.",
     "pass_mark": "Validation Sharpe above zero", **rule5("unfiltered")},
    {"id": "h1", "name": "Bank basket (H1)", "detail": "SBK against an equal-weight basket of FirstRand, Absa, Nedbank and Capitec, refitted monthly, five-day hold.",
     "pass_mark": "Validation Sharpe above zero and above the report rule",
     **{p: pick({**h1[n]["after_costs"]}) for p, n in (("design", "design"), ("validation", "validation"), ("post_freeze", "post-freeze"))},
     "before_costs": {p: pick(h1[n]["before_costs"]) for p, n in (("design", "design"), ("validation", "validation"))}},
    {"id": "h2a", "name": "Skip busy volume days (H2a)", "detail": "Five-day hold, but no new trade when either bank traded above 1.5 times its 60-session median volume.",
     "pass_mark": "Validation Sharpe above zero and above the five-day hold", **rule5("H2a volume")},
    {"id": "h2b", "name": "Skip news days, GDELT (H2b)", "detail": "Five-day hold, but no new trade when either bank's GDELT article count was above twice its 60-session median.",
     "pass_mark": "Validation Sharpe above zero and above the five-day hold", **rule5("H2b GDELT"),
     "design_note": f"GDELT design period from {json.load(open('research/results/h2.json'))['h2b_design_start']}",
     "design": pick(h2["H2b design"]["H2b GDELT"])},
]
h3 = json.load(open("research/results/h3.json"))
for key, name, detail in [
    ("h3a", "Learned exit, classifier (H3a)", "H1 entries. Each held day, a logistic model on news, tone, volume and market state decides whether to keep holding."),
    ("h3b", "Learned exit, reinforcement learning (H3b)", "H1 entries. Fitted Q-iteration on the same features learns when holding is worth less than exiting."),
]:
    r = h3[key]
    tests.append({"id": key, "name": name, "detail": detail, "pass_mark": "Validation Sharpe above zero and above H1",
                  **{p: pick(r[n]) for p, n in (("design", "design"), ("validation", "validation"), ("post_freeze", "post-freeze"))},
                  "design_note": "Design period 2017 to 2019",
                  "edge_vs_h1": r["vs_h1_validation"]})
h4 = json.load(open("research/results/h4.json"))
for key, name, detail in [
    ("H4a", "Classic z-score trade (H4a)", "NED against SBK on a rolling hedge ratio. Opens when the residual's z-score is extreme, closes when it reverts."),
    ("H4b", "Classic trade, cointegrated windows only (H4b)", "As H4a, but opens only when an Engle-Granger test on the same window rejects no cointegration at 5%."),
]:
    r = h4["chosen"][key]
    close = f"inside {r['exit']}" if r["exit"] else "when it crosses zero"
    tests.append({"id": key.lower(), "name": name, "detail": detail + f" Best of 18 rules on design data: {r['lookback']}-session window, open past {r['entry']}, close {close}.",
                  "pass_mark": "Validation Sharpe above zero",
                  **{p: pick(r[n]["after_costs"]) for p, n in (("design", "design"), ("validation", "validation"), ("post_freeze", "post-freeze"))},
                  "before_costs": {p: pick(r[n]["before_costs"]) for p, n in (("design", "design"), ("validation", "validation"))},
                  "entries": {p: r[n]["after_costs"]["entries"] for p, n in (("design", "design"), ("validation", "validation"), ("post_freeze", "post-freeze"))},
                  "edge_vs_h1": r["vs_h1_validation"]})
bars = {"h4a": 0.0, "h4b": 0.0, "v1": None, "hold5": 0.0, "h1": max(0.0, tests[0]["validation"]["sharpe"]), "h2a": max(0.0, tests[1]["validation"]["sharpe"]), "h2b": max(0.0, tests[1]["validation"]["sharpe"]), "h3a": max(0.0, tests[2]["validation"]["sharpe"]), "h3b": max(0.0, tests[2]["validation"]["sharpe"])}
for t in tests:
    if bars[t["id"]] is not None:
        t["passed"] = t["validation"]["sharpe"] > bars[t["id"]]

c = json.load(open("research/results/cointegration.json"))
cointegration = {
    "engle_granger": {k: round(c[k]["engle_granger"]["stat"], 2) for k in ("full_levels", "full_logs", "design_logs")},
    "crit5": c["rolling"]["crit5"],
    "rolling_share_rejecting": round(c["rolling"]["share_rejecting"], 3),
    "gregory_hansen": {k: round(v["stat"], 2) for k, v in c["gregory_hansen"].items()},
    "breaks": c["bai_perron"]["breaks"],
    "segments": [{"from": s["from"], "to": s["to"], "slope": round(s["slope"], 2)} for s in c["bai_perron"]["segments"]],
}
out = {"periods": PERIODS, "tests": tests, "decay": json.load(open("data/decay.json")), "cointegration": cointegration}
json.dump(out, open("data/research.json", "w"), separators=(",", ":"))
for t in tests:
    print(f"{t['name']:30s} design {t['design']['sharpe']:5.2f}  validation {t['validation']['sharpe']:5.2f}  post {t['post_freeze']['sharpe']:5.2f}  passed {t.get('passed')}")
