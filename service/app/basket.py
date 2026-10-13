"""H1: Standard Bank against an equal-weight basket of FirstRand, Absa, Nedbank and
Capitec, refitted monthly (research/02_basket.R, research/PROTOCOL.md).

Every day in the history was filtered by a model fitted only on data before its month.
Sessions after the latest month end are filtered live with the latest fit.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

import numpy as np

from .model import MarginalState, filter_marginal, h_func
from .strategy import metrics, window

LIVE_FROM = date(2026, 4, 1)


@dataclass(frozen=True)
class BasketParams:
    entry: int = 90  # percentile of |h - 0.5| under the model needed to open
    hold: int = 5  # trading days held after the latest signal
    cost_bps: float = 10.0

    def clamp(self) -> "BasketParams":
        return BasketParams(
            entry=int(min(99, max(51, self.entry))),
            hold=int(min(20, max(1, self.hold))),
            cost_bps=float(min(100.0, max(0.0, self.cost_bps))),
        )

    @property
    def level(self) -> float:
        # h is uniform under the model, so |h - 0.5| has its p-th percentile at p / 2.
        return self.entry / 200


class Basket:
    def __init__(self, data: dict) -> None:
        self.data = data
        self.fits = data["fits"]
        self.latest = data["latest"]
        self.train_end = date.fromisoformat(self.latest["train_end"])
        h = data["history"]
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
        return {
            "date": [r["date"] for r in rows],
            "fit": np.full(len(rows), len(self.fits)),
            "u": fs["u"],
            "v": fb["u"],
            "h": h_func(c["family"], fs["u"], fb["u"], c["par"], c.get("par2", 0.0)),
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


def run(rows: dict, p: BasketParams, period: str = "all") -> dict:
    """Run on the full record, then report the period, keeping positions carried into it."""
    pos = positions(rows["h"], p)
    rs, rb = rows["r_sbk"], rows["r_bsk"]
    held = np.concatenate([[0.0], pos[:-1]])
    turnover = np.abs(np.diff(np.concatenate([[0.0], pos])))
    net = held * 0.5 * (rs - rb) - turnover * p.cost_bps / 1e4
    keep = np.ones(len(pos), bool) if period == "all" else np.array([(d >= LIVE_FROM) == (period == "live") for d in rows["date"]])
    w = window(rows["date"], keep, pos, net, 0.5 * (rs + rb))
    dates, pos, h = w["dates"], w["position"], rows["h"][w["slice"]]
    return {
        "strategy": "basket",
        "period": period,
        "params": p.__dict__,
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
