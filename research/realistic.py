"""Reporting only: H18 (decided at 16:00, filled in the closing auction) with its P&L on dividend-correct returns.

  python research/realistic.py     # needs the local hourly bars, as research/h18_auction.py

The page leads with this version of the spread rule because it is the one a person could trade. Its gate and
trades are H18's exactly; only the P&L is taken on total returns (H19's series). Writes research/results/realistic.json.
"""
import json, sys
import numpy as np

sys.path.insert(0, "research"); sys.path.insert(0, "research/models"); sys.path.insert(0, "service")
import h18_auction as h18  # noqa: E402
from h19_total_return import raw_closes, dividends, total_return, summary, completed, shifted, START, DEV_END, ERAS  # noqa: E402
from pairdata import load_pair  # noqa: E402
from app import switch as sw  # noqa: E402

captured = {}
_orig = sw.trades
def _spy(*a, **k):
    t = _orig(*a, **k); captured.setdefault("first", t); return t
sw.trades = _spy
_dump = json.dump
json.dump = lambda *a, **k: None  # h18's own output is not rewritten
try:
    h18.main()
finally:
    json.dump = _dump
    sw.trades = _orig
trs = captured["first"]

d = load_pair()
keep = [i for i, t in enumerate(d["date"]) if t <= DEV_END]
dates = [d["date"][i] for i in keep]
n = len(dates)
raw = {k: raw_closes(k) for k in ("sbk", "ned")}
div = dividends()
first_prev = max(t for t in sorted(set(raw["sbk"]) & set(raw["ned"])) if t < dates[0])
seq = [first_prev] + dates
tr = {k: total_return(seq, raw[k], div[k])[0][1:] for k in ("sbk", "ned")}
ts, tn = np.expm1(tr["sbk"]), np.expm1(tr["ned"])
rs, rn = np.expm1(d["r_sbk"][keep]), np.expm1(d["r_ned"][keep])
first = dates[min(t["open"] for t in trs)]


def done(t, a, b, sched="futures"):
    _, rows = sw.daily_returns(t, dates, a, b, sched)
    return [x for x in completed(rows, dates) if dates[x["open"]] >= START]


rows = done(trs, ts, tn)
out = {"note": "reporting only; H18's trades, P&L on total returns", "from": first.isoformat(), "to": DEV_END.isoformat(),
       "price_only": summary([x["net"] for x in done(trs, rs, rn)]),
       "with_dividends": summary([x["net"] for x in rows]),
       "with_dividends_cash": summary([x["net"] for x in done(trs, ts, tn, "cash")]),
       "with_dividends_one_close_late": summary([x["net"] for x in done(shifted(trs, 1, n), ts, tn)]),
       "eras": [{"from": a, "to": c, **summary([x["net"] for x in rows if a <= dates[x["open"]].isoformat() < c])} for a, c in ERAS],
       "trades": [{"open": dates[x["open"]].isoformat(), "close": dates[x["close"]].isoformat(), "net_bps": round(x["net"] * 1e4, 1)} for x in rows]}
_dump(out, open("research/results/realistic.json", "w"), indent=1)
print(json.dumps({k: v for k, v in out.items() if k != "trades"}, indent=1))
