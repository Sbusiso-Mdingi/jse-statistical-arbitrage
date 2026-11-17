"""H22 (research/PROTOCOL.md): the 16:00 version of the rule on the Big Four cross-pairs, scored live from 18 November 2026.

  python research/h22_score.py [path to jse-risk-management]     # use that repo's venv (pandas, httpx)

1. Copies the saved 16:00 prices (gs://jse-pairs-1600-720432866871/1600-banks/) into data/raw/1600-banks/ (gitignored).
2. Downloads each bank's daily closes and dividends from Yahoo at run time (jse-risk-management's downloader:
   total returns, no-trade days and bad prints dropped). Prices are not stored in the repo.
3. For each pair, H18's rule through service/app/switch.py's rolling_1600, on total-return levels: today's point is
   the 16:00 price (plus any dividend going ex that session), the 125 earlier points are closes; gate open below -2.8,
   open at |z| > 1.5, close at z back to 0, beyond +-4 or after 60 sessions, filled at the official close.
   Decisions only on sessions with a saved 16:00 price for both banks.
4. Scores trades opened from 18 November 2026 (pooled mean per trade at institutional futures, t clustered by month of
   entry, cash beside it). Trades opened earlier, on the back-saved 16:00 prices, are reported as reference only.

Writes research/results/h22.json.
"""
import datetime as dt
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np

RISK = Path(sys.argv[1] if len(sys.argv) > 1 else Path.home() / "Developer/jse-risk-management")
import importlib.util  # noqa: E402

sys.path.insert(0, "research"); sys.path.insert(0, "service")
from app import switch as sw  # noqa: E402  (this repo's service; jse-risk-management's is also called app)
import h20_other_pairs as h20  # noqa: E402  (puts jse-risk-management on the path for jserisk)
from jserisk import data as jd  # noqa: E402

_spec = importlib.util.spec_from_file_location("risk_market", RISK / "service" / "app" / "market.py")
market = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(market)  # jse-risk-management's Yahoo downloader
from h19_total_return import summary  # noqa: E402

sw.EXPIRIES = sw.third_thursdays(2004, 2031)
BUCKET = "gs://jse-pairs-1600-720432866871/1600-banks"
CACHE = Path("data/raw/1600-banks")
SCORE_FROM = dt.date(2026, 11, 18)
PAIRS = [("SBK", "FSR"), ("SBK", "ABG"), ("NED", "FSR"), ("NED", "ABG")]
VERDICT = "40 completed trades pooled across the four pairs or 31 December 2036; pass if mean > 0 and one-sided t > 1.65 (clustered by month of entry)"


def sync():
    CACHE.mkdir(parents=True, exist_ok=True)
    subprocess.run(["gcloud", "storage", "rsync", BUCKET, str(CACHE), "--quiet"], check=True, capture_output=True)
    out = {}
    for f in sorted(CACHE.glob("*.json")):
        d = json.loads(f.read_text())
        out[dt.date.fromisoformat(d["date"])] = {k.upper(): float(v) for k, v in d["price_1600"].items()}
    return out


def frame(t):
    df = market._download(f"{t}.JO")
    return jd.clean(df)


def pair(a, b, fa, fb, p16):
    idx = fa.index.intersection(fb.index)
    dates = [d.date() for d in idx]
    n = len(dates)
    lvl, l16, ret = {}, {}, {}
    for k, f in ((a, fa), (b, fb)):
        f = f.loc[idx]
        tr = np.log(f["adjusted"].to_numpy())
        close, div = f["close"].to_numpy(), f["dividend"].to_numpy() if "dividend" in f else np.zeros(n)
        x16 = np.full(n, np.nan)
        for t in range(1, n):
            p = p16.get(dates[t], {}).get(k)
            if p:
                x16[t] = tr[t - 1] + math.log((p + div[t]) / close[t - 1])
        lvl[k], l16[k], ret[k] = tr, x16, np.r_[0.0, np.expm1(np.diff(tr))]
    bb, z, eg = sw.rolling_1600(lvl[a], lvl[b], l16[a], l16[b])
    first16 = min(p16) if p16 else dates[-1]
    gate = ((eg < sw.GATE_CRIT) & np.array([d >= first16 for d in dates])).astype(np.int8)
    trs = sw.trades(gate, np.full(n, 0.5), bb, z, copula_on=False, hold_through=True)
    rows = {}
    for sched in ("futures", "cash"):
        _, rr = sw.daily_returns(trs, dates, ret[a], ret[b], sched)
        rows[sched] = [{"open": dates[r["open"]], "close": dates[r["close"]] if r["complete"] else None, "net": float(r["net"]),
                        "complete": r["complete"]} for r in rr]
    today = {"date": dates[-1].isoformat(), "eg_1600": None if np.isnan(eg[-1]) else round(float(eg[-1]), 3),
             "z_1600": None if np.isnan(z[-1]) else round(float(z[-1]), 3), "gate_open": bool(gate[-1])}
    return rows, today


def main():
    p16 = sync()
    frames = {t: frame(t) for t in {x for p in PAIRS for x in p}}
    out = {"protocol": "research/PROTOCOL.md, H22", "score_from": SCORE_FROM.isoformat(), "verdict_at": VERDICT,
           "saved_1600_sessions": len(p16), "first_1600": min(p16).isoformat(), "last_1600": max(p16).isoformat(), "pairs": []}
    scored = {"futures": [], "cash": []}
    reference = []
    for a, b in PAIRS:
        rows, today = pair(a, b, frames[a], frames[b], p16)
        live = {s: [r for r in rows[s] if r["open"] >= SCORE_FROM] for s in rows}
        ref = [r for r in rows["futures"] if r["open"] < SCORE_FROM and r["complete"]]
        for s in scored:
            scored[s] += [dict(r, pair=f"{a}/{b}") for r in live[s] if r["complete"]]
        reference += ref
        out["pairs"].append({"pair": f"{a}/{b}", "today": today,
                             "live": {"completed": sum(r["complete"] for r in live["futures"]), "open": sum(not r["complete"] for r in live["futures"]),
                                      "futures": summary([r["net"] for r in live["futures"] if r["complete"]])},
                             "reference_before_score_start": summary([r["net"] for r in ref])})
    m, t = h20.clustered_t(scored["futures"]) if len(scored["futures"]) > 2 else (None, None)
    out["live"] = {"completed": len(scored["futures"]), "futures": summary([r["net"] for r in scored["futures"]]),
                   "cash": summary([r["net"] for r in scored["cash"]]),
                   "t_clustered": None if t is None else round(t, 2), "verdict_reached": len(scored["futures"]) >= 40 or dt.date.today() > dt.date(2036, 12, 31)}
    out["reference_before_score_start"] = {"note": "back-saved 16:00 prices, not scored", **summary([r["net"] for r in reference])}
    out["trades"] = [{"pair": r["pair"], "open": r["open"].isoformat(), "close": r["close"].isoformat(), "net_futures_bps": round(r["net"] * 1e4, 1)}
                     for r in scored["futures"]]
    Path("research/results/h22.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "trades"}, indent=1))


if __name__ == "__main__":
    main()
