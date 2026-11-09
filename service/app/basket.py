"""H1: Standard Bank against an equal-weight basket of FirstRand, Absa, Nedbank and
Capitec, refitted monthly (research/02_basket.R, research/PROTOCOL.md).

Every day in the history was filtered by a model fitted only on data before its month.
Sessions after the latest month end are filtered live with the latest fit.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import date

import numpy as np

from .model import MarginalState, filter_marginal, gas_filter, h_func
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
class BasketParams:
    entry: int = 90  # percentile of |h - 0.5| under the model needed to open
    hold: int = 5  # trading days held after the latest signal
    cost_bps: float = 10.0  # flat brokerage per leg, used by the "protocol" tier
    costs: str = "protocol"  # protocol | institutional | retail

    def clamp(self) -> "BasketParams":
        return BasketParams(
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


class Basket:
    def __init__(self, data: dict, gas: dict | None = None) -> None:
        self.data = data
        self.fits = data["fits"]
        self.latest = data["latest"]
        self.train_end = date.fromisoformat(self.latest["train_end"])
        # The score-driven copula (H9) replaces the static one when its export is present and matches the fits.
        self.gas = gas if gas and gas["latest"]["train_end"] == self.latest["train_end"] else None
        if gas and not self.gas:
            logging.getLogger("pairs").warning(
                "basket_gas.json is fitted to %s but the basket fits end %s: falling back to the static copula; rerun research/models/export_gas.py",
                gas["latest"]["train_end"], self.latest["train_end"],
            )
        h = data["history"]
        if self.gas:
            gh = dict(zip(self.gas["history"]["date"], self.gas["history"]["h"]))
            h = {**h, "h": [gh.get(d, x) for d, x in zip(h["date"], h["h"])]}
        dates = [date.fromisoformat(d) for d in h["date"]]
        keep = np.array([d <= self.train_end for d in dates])
        basket = np.mean([np.array(h[k], dtype=float) for k in data["basket"]], axis=0)
        # Days after the latest month end are refiltered live from its terminal state.
        self.history = {
            "date": [d for d, k in zip(dates, keep) if k],
            "fit": np.array(h["fit"], dtype=int)[keep],
            "u": np.array(h["u"], dtype=float)[keep],
            "v": np.array(h["v"], dtype=float)[keep],
            "h": np.array(h["h"], dtype=float)[keep],
            "r_sbk": np.array(h["sbk"], dtype=float)[keep],
            "r_bsk": basket[keep],
        }

    def snapshot_rows(self) -> list[dict]:
        p = self.latest["parity"]
        return [
            {"date": date.fromisoformat(d), "r_sbk": a, "r_bsk": b, "vix": v}
            for d, a, b, v in zip(p["date"], p["r_sbk"], p["r_bsk"], p["vix"])
        ]

    def live_rows(self, rows: list[dict]) -> dict:
        r_sbk = np.array([r["r_sbk"] for r in rows])
        r_bsk = np.array([r["r_bsk"] for r in rows])
        vix = np.array([r["vix"] for r in rows])
        st = self.latest["state"]
        fs = filter_marginal(self.latest["sbk"], MarginalState(**st["sbk"]), r_sbk, vix)
        fb = filter_marginal(self.latest["bsk"], MarginalState(**st["bsk"]), r_bsk, vix)
        c = self.latest["copula"]
        if self.gas:
            h, rho, _ = gas_filter(self.gas["latest"], fs["u"], fb["u"])
            self.live_rho = float(rho[-1]) if len(rho) else None
        else:
            h = h_func(c["family"], fs["u"], fb["u"], c["par"], c.get("par2", 0.0))
        return {
            "date": [r["date"] for r in rows],
            "fit": np.full(len(rows), len(self.fits)),
            "u": fs["u"],
            "v": fb["u"],
            "h": h,
            # Simple returns for the backtest.
            "r_sbk": np.expm1(r_sbk),
            "r_bsk": np.expm1(r_bsk),
        }

    def rows(self, period: str, live: dict) -> dict:
        allr = {k: (self.history[k] + live[k] if k == "date" else np.concatenate([self.history[k], live[k]])) for k in self.history}
        if period == "all":
            return allr
        m = np.array([(d >= LIVE_FROM) == (period == "live") for d in allr["date"]])
        return {k: ([d for d, keep in zip(v, m) if keep] if k == "date" else v[m]) for k, v in allr.items()}


def positions(h: np.ndarray, p: BasketParams) -> np.ndarray:
    """Open on |h - 0.5| above the level, hold for p.hold days; a new signal restarts the count."""
    pos = np.zeros(len(h))
    current, left = 0.0, 0
    for t in range(len(h)):
        if abs(h[t] - 0.5) > p.level:
            # The basket moved up more than SBK implies: SBK is cheap, so long SBK / short basket.
            current, left = (1.0 if h[t] > 0.5 else -1.0), p.hold
        elif left > 0:
            left -= 1
        if left == 0:
            current = 0.0
        pos[t] = current
    return pos


def trading_costs(pos: np.ndarray, p: BasketParams) -> np.ndarray:
    """Daily costs of a position path under the chosen tier. Position +1 is long SBK and short the basket,
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


def run(rows: dict, p: BasketParams, period: str = "all") -> dict:
    """Run on the full record, then report the period, keeping positions carried into it."""
    pos = positions(rows["h"], p)
    rs, rb = rows["r_sbk"], rows["r_bsk"]
    held = np.concatenate([[0.0], pos[:-1]])
    net = held * 0.5 * (rs - rb) - trading_costs(pos, p)
    keep = np.ones(len(pos), bool) if period == "all" else np.array([(d >= LIVE_FROM) == (period == "live") for d in rows["date"]])
    w = window(rows["date"], keep, pos, net, 0.5 * (rs + rb))
    dates, pos, h = w["dates"], w["position"], rows["h"][w["slice"]]
    return {
        "strategy": "basket",
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
                "side": "Long SBK / short basket" if t["side"] > 0 else "Short SBK / long basket",
                "return": t["ret"],
            }
            for t in w["trades"]
        ],
    }


def spec(s: dict) -> dict:
    return {k: s[k] for k in ("model", "arma", "dist", "vix", "bic")}


def model_summary(b: Basket, live: dict) -> dict:
    hist = b.history
    return {
        "basket": b.data["basket"],
        "fits": [
            {
                "train_end": f["train_end"],
                "sbk": spec(f["sbk"]),
                "bsk": spec(f["bsk"]),
                "copula": {k: f["copula"][k] for k in ("family", "name", "par", "par2", "tau")},
            }
            for f in b.fits
        ],
        "latest": {
            "train_end": b.latest["train_end"],
            "sbk": spec(b.latest["sbk"]),
            "bsk": spec(b.latest["bsk"]),
            "copula": b.latest["copula"],
            "pit_ks": b.latest["pit_ks"],
        },
        "dependence": (
            {"model": "gas_t", **{k: b.gas["latest"][k] for k in ("omega", "beta", "alpha", "nu", "rho_train_end")}, "rho_live": getattr(b, "live_rho", None)}
            if b.gas
            else {"model": "static_t"}
        ),
        "pit": {
            "walkforward": {
                "u": [u for u, d in zip(hist["u"], hist["date"]) if d < LIVE_FROM],
                "v": [v for v, d in zip(hist["v"], hist["date"]) if d < LIVE_FROM],
            },
            "live": {
                "u": [u for u, d in zip(hist["u"], hist["date"]) if d >= LIVE_FROM] + list(live["u"]),
                "v": [v for v, d in zip(hist["v"], hist["date"]) if d >= LIVE_FROM] + list(live["v"]),
            },
        },
    }
