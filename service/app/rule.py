"""The measurement rule and the JSE cost schedule for Standard Bank against Nedbank (research/PROTOCOL.md).

Open when |h - 0.5| passes the level, long SBK / short NED when h > 0.5 and the reverse below, hold five
sessions (a new signal restarts the count), half of capital a side. Costs follow research/costs.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np

from .strategy import metrics, window

LIVE_FROM = date(2026, 4, 1)


# JSE cost schedule (research/costs.py). Per execution: brokerage plus 15% VAT, a half bid-ask spread, Strate
# and the investor protection levy; securities transfer tax of 0.25% on every purchase; borrow on the short leg.
COST_TIERS: dict[str, dict] = {
    "protocol": dict(brokerage=10.0, vat=False, spread=0.0, strate=0.0, stt=0.0, borrow=0.0),
    "institutional": dict(brokerage=10.0, vat=True, spread=5.0, strate=0.3, stt=25.0, borrow=100.0),
    "retail": dict(brokerage=25.0, vat=True, spread=5.0, strate=1.0, stt=25.0, borrow=100.0),
}
VAT = 0.15


@dataclass(frozen=True)
class Params:
    entry: int = 90  # percentile of |h - 0.5| under the model needed to open
    hold: int = 5  # trading days held after the latest signal
    cost_bps: float = 10.0  # flat brokerage per leg, used by the "protocol" tier
    costs: str = "protocol"  # protocol | institutional | retail

    def clamp(self) -> "Params":
        return Params(
            entry=int(min(99, max(51, self.entry))),
            hold=int(min(20, max(1, self.hold))),
            cost_bps=float(min(100.0, max(0.0, self.cost_bps))),
            costs=self.costs if self.costs in COST_TIERS else "protocol",
        )

    def round_trip_bps(self) -> float:
        t = dict(COST_TIERS[self.costs])
        if self.costs == "protocol":
            t["brokerage"] = self.cost_bps
        b = t["brokerage"] * (1 + VAT if t["vat"] else 1)
        return 4 * 0.5 * (b + t["spread"] + t["strate"]) + 2 * 0.5 * t["stt"]

    @property
    def level(self) -> float:
        # h is uniform under the model, so |h - 0.5| has its p-th percentile at p / 2.
        return self.entry / 200


def positions(h: np.ndarray, p: Params) -> np.ndarray:
    """Open on |h - 0.5| above the level, hold for p.hold days; a new signal restarts the count."""
    pos = np.zeros(len(h))
    current, left = 0.0, 0
    for t in range(len(h)):
        if abs(h[t] - 0.5) > p.level:
            # Nedbank moved up more than SBK implies: SBK is cheap, so long SBK / short NED.
            current, left = (1.0 if h[t] > 0.5 else -1.0), p.hold
        elif left > 0:
            left -= 1
        if left == 0:
            current = 0.0
        pos[t] = current
    return pos


def trading_costs(pos: np.ndarray, p: Params) -> np.ndarray:
    """Daily costs of a position path under the chosen tier. Position +1 is long SBK and short NED,
    each leg at half of capital. Purchases (the long leg to open, the short leg to cover) pay STT."""
    t = dict(COST_TIERS[p.costs])
    if p.costs == "protocol":
        t["brokerage"] = p.cost_bps
    per_exec = (t["brokerage"] * (1 + VAT if t["vat"] else 1) + t["spread"] + t["strate"]) / 1e4
    stt = t["stt"] / 1e4
    prev = np.concatenate([[0.0], pos[:-1]])
    d = pos - prev
    executions = np.abs(d)  # 0.5 of capital on each of two legs
    purchases = 0.5 * np.maximum(d, 0) + 0.5 * np.maximum(-d, 0)
    borrow = 0.5 * np.abs(prev) * (t["borrow"] / 1e4) / 252
    return executions * per_exec + purchases * stt + borrow


def run(rows: dict, p: Params, period: str = "all") -> dict:
    """Run on the full record, then report the period, keeping positions carried into it."""
    pos = positions(rows["h"], p)
    rs, rn = rows["r_sbk"], rows["r_ned"]
    held = np.concatenate([[0.0], pos[:-1]])
    net = held * 0.5 * (rs - rn) - trading_costs(pos, p)
    keep = np.ones(len(pos), bool) if period == "all" else np.array([(d >= LIVE_FROM) == (period == "live") for d in rows["date"]])
    w = window(rows["date"], keep, pos, net, 0.5 * (rs + rn))
    dates, pos, h = w["dates"], w["position"], rows["h"][w["slice"]]
    return {
        "strategy": "pair",
        "period": period,
        "params": {**p.__dict__, "round_trip_bps": round(p.round_trip_bps(), 1)},
        "start": dates[0],
        "end": dates[-1],
        "metrics": metrics(dates, w["daily"], w["equity"], pos, w["trades"]),
        "benchmark": metrics(dates, w["bench_daily"], w["benchmark"], np.ones(len(pos)), []),
        "latest": {"date": dates[-1], "position": float(pos[-1]), "h": float(h[-1])},
        "series": {
            "date": dates,
            "equity": w["equity"],
            "benchmark": w["benchmark"],
            "position": pos,
            "h": h,
            "level": p.level,
        },
        "trades": [
            {
                "open": rows["date"][t["open"]],
                "close": rows["date"][t["close"]] if t["close"] is not None else None,
                "side": "Long SBK / short NED" if t["side"] > 0 else "Short SBK / long NED",
                "return": t["ret"],
            }
            for t in w["trades"]
        ],
    }


