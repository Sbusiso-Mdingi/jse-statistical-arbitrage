"""Trading rules and performance metrics.

Positions are on the spread "long SBK, short NED" (+1) or the reverse (-1),
with each leg sized at half of capital, so gross exposure is 1x. A position
decided at the close of day t earns the spread return of day t + 1.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Params:
    rule: str = "probability"  # "probability" (report rule) or "mispricing" (cumulative index)
    entry: int = 90  # training percentile of |h - 0.5| needed to open
    exit: int = 50  # training percentile below which the trade closes
    vol_filter: bool = True
    vol_pct: int = 80  # no new entries when spread volatility is above this training percentile
    threshold: float = 0.6  # mispricing-index trigger
    cost_bps: float = 10.0  # per leg, per unit of notional traded

    def clamp(self) -> "Params":
        return Params(
            rule=self.rule if self.rule in ("probability", "mispricing") else "probability",
            entry=int(min(99, max(51, self.entry))),
            exit=int(min(self.entry - 1, max(50, self.exit))),
            vol_filter=bool(self.vol_filter),
            vol_pct=int(min(99, max(50, self.vol_pct))),
            threshold=float(min(3.0, max(0.1, self.threshold))),
            cost_bps=float(min(100.0, max(0.0, self.cost_bps))),
        )


def positions(rows: dict, folds: dict, p: Params) -> np.ndarray:
    """Position held at the close of each day (applies to the next day's return)."""
    h_ns, h_sn, vol, fold = rows["h_ns"], rows["h_sn"], rows["spread_vol"], rows["fold"]
    n = len(h_ns)
    pos = np.zeros(n)
    current = 0.0
    m1 = m2 = 0.0
    for t in range(n):
        q = folds[int(fold[t])]
        vol_ok = (not p.vol_filter) or (not math.isnan(vol[t]) and vol[t] < q["q_vol"][p.vol_pct - 50])
        if p.rule == "probability":
            signal = abs(h_ns[t] - 0.5)
            # NED high relative to what SBK implies: NED is rich, so long SBK / short NED.
            direction = 1.0 if h_ns[t] > 0.5 else -1.0
            open_level = q["q_signal"][p.entry - 50]
            close_level = q["q_signal"][p.exit - 50]
            if signal > open_level and direction != current:
                current = direction if vol_ok else 0.0
            elif current != 0 and signal < close_level:
                current = 0.0
        else:
            # Cumulative mispricing indices (Xie, Liew, Wu and Zou, 2016), reset after each exit.
            m1 += h_sn[t] - 0.5  # SBK relative to NED
            m2 += h_ns[t] - 0.5  # NED relative to SBK
            if current == 0:
                if vol_ok and m2 > p.threshold and m1 < -p.threshold:
                    current = 1.0
                elif vol_ok and m1 > p.threshold and m2 < -p.threshold:
                    current = -1.0
            elif (current > 0 and (m2 <= 0 or m1 >= 0)) or (current < 0 and (m1 <= 0 or m2 >= 0)):
                current = 0.0
                m1 = m2 = 0.0
        pos[t] = current
    return pos


def backtest(rows: dict, folds: dict, p: Params) -> dict:
    pos = positions(rows, folds, p)
    rs = np.expm1(rows["r_sbk"])
    rn = np.expm1(rows["r_ned"])
    held = np.concatenate([[0.0], pos[:-1]])
    gross = held * 0.5 * (rs - rn)
    turnover = np.abs(np.diff(np.concatenate([[0.0], pos])))
    # Each unit change trades both legs at half of capital: notional traded = turnover.
    costs = turnover * p.cost_bps / 1e4
    net = gross - costs
    equity = np.cumprod(1 + net)
    bench_daily = 0.5 * (rs + rn)
    return {
        "position": pos,
        "daily": net,
        "equity": equity,
        "benchmark": np.cumprod(1 + bench_daily),
        "bench_daily": bench_daily,
        "trades": _trades(pos, net),
    }


def window(dates: list, keep: np.ndarray, pos: np.ndarray, net: np.ndarray, bench_daily: np.ndarray) -> dict:
    """Slice a run on the full record to a period, so positions carried into it are kept.

    Equity and the benchmark are rebased to 1 at the start of the period. Trades are
    those open at any point in it, with full-trade returns and indices into the full record.
    """
    idx = np.flatnonzero(keep)
    a, b = int(idx[0]), int(idx[-1]) + 1
    trades = [t for t in _trades(pos, net) if (t["close"] is None or t["close"] > a) and t["open"] < b]
    return {
        "dates": dates[a:b],
        "position": pos[a:b],
        "daily": net[a:b],
        "equity": np.cumprod(1 + net[a:b]),
        "benchmark": np.cumprod(1 + bench_daily[a:b]),
        "bench_daily": bench_daily[a:b],
        "trades": trades,
        "slice": slice(a, b),
    }


def _trades(pos: np.ndarray, net: np.ndarray) -> list[dict]:
    trades = []
    start = None
    for t in range(len(pos)):
        prev = pos[t - 1] if t else 0.0
        if pos[t] != prev:
            if prev != 0 and start is not None:
                trades.append({"open": start, "close": t, "side": prev, "ret": float(np.prod(1 + net[start + 1 : t + 1]) - 1)})
            start = t if pos[t] != 0 else None
    if start is not None:
        trades.append({"open": start, "close": None, "side": pos[start], "ret": float(np.prod(1 + net[start + 1 :]) - 1)})
    return trades


def metrics(dates: list, daily: np.ndarray, equity: np.ndarray, pos: np.ndarray, trades: list[dict]) -> dict:
    n = len(daily)
    if n < 2:
        return {}
    days = (dates[-1] - dates[0]).days or 1
    total = float(equity[-1] - 1)
    sd = float(np.std(daily, ddof=1))
    peak = np.maximum.accumulate(np.concatenate([[1.0], equity]))
    dd = np.concatenate([[1.0], equity]) / peak - 1
    closed = [t for t in trades if t["close"] is not None]
    return {
        "total_return": total,
        "cagr": float((1 + total) ** (365.25 / days) - 1) if total > -1 else -1.0,
        "sharpe": float(np.mean(daily) / sd * math.sqrt(252)) if sd > 0 else 0.0,
        "volatility": sd * math.sqrt(252),
        "max_drawdown": float(dd.min()),
        "trades": len(trades),
        "hit_rate": (sum(t["ret"] > 0 for t in closed) / len(closed)) if closed else None,
        "avg_hold_days": (float(np.mean([t["close"] - t["open"] for t in closed])) if closed else None),
        "time_in_market": float(np.mean(pos != 0)),
        "days": n,
        "years": days / 365.25,
    }
