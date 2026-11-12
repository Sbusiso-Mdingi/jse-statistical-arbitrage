"""The episode-grouped verdict test for H18 and H19 (research/PROTOCOL.md), calibrated on development trades.

  python research/verdict_episodes.py     # after research/h18_auction.py and research/h19_total_return.py

Trades bunch: a gate spell often holds several trades in a row, so the 79 H16 trades are about 20 episodes, and
the plain t on trades passes a rule with no edge about 9% of the time at 40 trades (left-skewed nets). Here an
episode is a run of completed trades in which each opens within 21 sessions of the previous one's close. The
statistic is the mean net per trade over its episode-clustered standard error. Its critical value is set so that
a rule with no edge passes 5% of the time: development trades are re-centred to a zero mean, whole episodes are
resampled until a 40-trade record is reached, and the 95th percentile of the statistic is taken. Writes
research/results/verdict_episodes.json with the critical value and the power at several true means.
"""
import json, math, sys
import datetime as dt
import numpy as np

sys.path.insert(0, "research"); sys.path.insert(0, "research/models")
from pairdata import load_pair  # noqa: E402

GAP, N_TRADES, DRAWS, SEED = 21, 40, 20000, 20261112


def episodes(opens, closes, sessions):
    ix = {d: i for i, d in enumerate(sessions)}
    o = [ix[dt.date.fromisoformat(x)] for x in opens]; c = [ix[dt.date.fromisoformat(x)] for x in closes]
    ep, cur = [], 0
    for k in range(len(o)):
        if k and o[k] - c[k - 1] > GAP:
            cur += 1
        ep.append(cur)
    return np.array(ep)


def stat(v, ep):
    """Mean over its episode-clustered standard error (CR1)."""
    n, m = len(v), v.mean()
    g = np.unique(ep)
    if len(g) < 2:
        return None
    s = np.array([(v[ep == e] - m).sum() for e in g])
    se = math.sqrt((s @ s) / n ** 2 * len(g) / (len(g) - 1))
    return m / se if se > 0 else None


def draw(rng, groups, mu):
    vals, eps, k = [], [], 0
    while len(vals) < N_TRADES:
        gidx = groups[rng.integers(len(groups))]
        vals.extend((gidx + mu)[: N_TRADES - len(vals)]); eps.extend([k] * min(len(gidx), N_TRADES - len(eps))); k += 1
    return np.array(vals), np.array(eps)


def calibrate(v, ep):
    rng = np.random.default_rng(SEED)
    c0 = v - v.mean()
    groups = [c0[ep == e] for e in np.unique(ep)]
    null = np.array([s for s in (stat(*draw(rng, groups, 0.0)) for _ in range(DRAWS)) if s is not None])
    crit = float(np.quantile(null, 0.95))
    plain = []
    for _ in range(DRAWS):
        x, _ = draw(rng, groups, 0.0)
        plain.append(x.mean() / (x.std(ddof=1) / math.sqrt(len(x))))
    power = {}
    for mu in (20, 40, 60, 80):
        hits = 0
        for _ in range(DRAWS // 4):
            x, e = draw(rng, groups, mu)
            s = stat(x, e)
            hits += s is not None and x.mean() > 0 and s > crit
        power[str(mu)] = round(hits / (DRAWS // 4), 3)
    return {"critical_value": round(crit, 3), "plain_t_false_pass_at_1.65": round(float(np.mean(np.array(plain) > 1.65)), 3),
            "power_by_true_mean_bps": power}


def main():
    sessions = load_pair()["date"]
    out = {"gap_sessions": GAP, "trades": N_TRADES, "draws": DRAWS, "seed": SEED}
    for key, path, sub in (("h18", "research/results/h18.json", "h18"), ("h19", "research/results/h19.json", "h19")):
        r = json.load(open(path))[sub]
        v = np.array(r["trade_nets_bps"]); ep = episodes(r["trade_opens"], r["trade_closes"], sessions)
        out[key] = {"development_trades": len(v), "episodes": int(ep.max() + 1), "development_statistic": round(stat(v, ep), 2),
                    "development_mean_bps": round(float(v.mean()), 1), **calibrate(v, ep)}
        print(key, out[key])
    json.dump(out, open("research/results/verdict_episodes.json", "w"), indent=1)
    # The frozen records the service serves: identity, dates, the verdict and the development reference.
    h18 = json.load(open("research/results/h18.json")); h19 = json.load(open("research/results/h19.json"))
    common = {"frozen_on": "2026-11-12", "window": 126, "crit": -2.8, "episode_gap_sessions": GAP}
    json.dump({"protocol": "research/PROTOCOL.md, H18", **common, "score_from": None,
               "score_from_note": "the first session for which the live 16:00 record holds a price for both banks",
               "verdict": f"40 completed trades or 31 December 2036; mean net per trade at the institutional futures schedule above zero and the episode-clustered statistic above {out['h18']['critical_value']}",
               "critical_value": out["h18"]["critical_value"], "expected_live_bps": [30, 55],
               "development": {k: h18[k] for k in ("development", "h16_same_span", "h16_same_span_next_close", "h18_next_close")} | {"h18": {s_: {a: b for a, b in v.items()} for s_, v in h18["h18"].items() if s_ in ("futures", "cash")}}},
              open("data/pair_h18.json", "w"), indent=1)
    json.dump({"protocol": "research/PROTOCOL.md, H19", **common, "score_from": "2026-04-01",
               "verdict": f"40 completed trades or 31 December 2036; mean net per trade at the institutional futures schedule above zero and the episode-clustered statistic above {out['h19']['critical_value']}",
               "critical_value": out["h19"]["critical_value"], "expected_live_bps": [-10, 30],
               "development": {k: h19["h19"][k] for k in ("futures", "cash", "eras", "next_close_fill", "trades_per_year")}},
              open("data/pair_h19.json", "w"), indent=1)


if __name__ == "__main__":
    main()
