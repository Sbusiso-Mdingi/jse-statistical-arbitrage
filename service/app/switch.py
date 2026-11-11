"""H14 (research/PROTOCOL.md): trade the spread while the long-run relationship holds, the copula when it breaks.

Spread mode is H4b's trade on a rolling 126-session regression of log NED on log SBK; copula mode is H8's rule.
A spread spell starts on a close where the 126-session Engle-Granger statistic is below -3.34 and lasts until the
detector says the relationship has broken: E (the statistic is no longer below -3.34), C (a CUSUM monitor of the
residuals from the spell's first window) or B (a real-time sup-F test for one break on the anchored sample).
Positions are weights (SBK, NED) set at each close, earning the next session. Shared by research/h14_switch.py
and the service.
"""

from __future__ import annotations

import datetime as dt
import math

import numpy as np

L = 126
EG_CRIT = -3.34
ENTRY, EXIT, STOP, MAX_HOLD = 1.5, 0.0, 4.0, 60
LEVEL, HOLD = 0.45, 5
TRIM = 0.15

# Institutional schedules, bps (research/costs.py and research/derivative_costs.py). Per execution on each leg's
# notional: cash pays brokerage with VAT, a half-spread and Strate with the levy, STT on purchases and borrow a
# year on the short leg; single stock futures pay commission and the exchange fee with VAT, a wider half-spread,
# funding a year on each leg, and both legs again at a roll.
VAT = 0.15
SCHEDULES = {
    "cash": dict(exec=10.0 * (1 + VAT) + 5.0 + 0.3, stt=25.0, long_year=0.0, short_year=100.0, rolls=False),
    "futures": dict(exec=(5.0 + 0.548) * (1 + VAT) + 10.0, stt=0.0, long_year=50.0, short_year=50.0, rolls=True),
}


def rolling(x: np.ndarray, y: np.ndarray, L: int = L) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Hedge ratio, z-score of the last residual and Engle-Granger statistic for the L sessions to each close."""
    n = len(x)
    b = np.full(n, np.nan); z = np.full(n, np.nan); eg = np.full(n, np.nan)
    for t in range(L - 1, n):
        b[t], z[t], eg[t] = window_stats(x[t - L + 1 : t + 1], y[t - L + 1 : t + 1])
    return b, z, eg


def window_stats(xi: np.ndarray, yi: np.ndarray) -> tuple[float, float, float]:
    xm, ym = xi.mean(), yi.mean()
    dx = xi - xm
    slope = float(dx @ (yi - ym) / (dx @ dx))
    u = yi - ym - slope * dx
    sd = math.sqrt(u @ u / (len(u) - 2))
    # ADF on the residuals: du_t = g u_{t-1} + c du_{t-1} + e, no constant (as research/h4_cointegration.py).
    du = np.diff(u)
    a1, a2, yy = u[1:-1], du[:-1], du[1:]
    s11, s12, s22 = a1 @ a1, a1 @ a2, a2 @ a2
    r1, r2 = a1 @ yy, a2 @ yy
    det = s11 * s22 - s12 * s12
    g = (s22 * r1 - s12 * r2) / det
    c = (s11 * r2 - s12 * r1) / det
    e = yy - g * a1 - c * a2
    s2 = e @ e / (len(yy) - 2)
    return slope, float(u[-1] / sd), float(g / math.sqrt(s2 * s22 / det))


def cusum_start(x: np.ndarray, y: np.ndarray, t0: int) -> dict:
    """The spell's reference line and long-run residual sd, from the window ending at its first close."""
    xi, yi = x[t0 - L + 1 : t0 + 1], y[t0 - L + 1 : t0 + 1]
    dx = xi - xi.mean()
    b = float(dx @ (yi - yi.mean()) / (dx @ dx))
    a = float(yi.mean() - b * xi.mean())
    u = yi - a - b * xi
    phi = float(u[1:] @ u[:-1] / (u[:-1] @ u[:-1]))
    e = u[1:] - phi * u[:-1]
    sig = math.sqrt(e @ e / (len(e) - 1))
    return {"a": a, "b": b, "omega": sig / (1 - phi), "s": 0.0}


def cusum_stat(k: int, s: float, omega: float) -> float:
    """c^2 at which |S_k| / (omega sqrt L) meets the boundary sqrt((1 + k/L)(c^2 + ln(1 + k/L)))."""
    r = k / L
    q = abs(s) / (omega * math.sqrt(L))
    return q * q / (1 + r) - math.log1p(r)


def sup_f(x: np.ndarray, y: np.ndarray) -> float:
    """sup-F for one break in intercept and slope, over the middle 70% of the sample."""
    n = len(x)
    x = x - x.mean(); y = y - y.mean()
    c1 = np.cumsum(np.ones(n)); cx = np.cumsum(x); cy = np.cumsum(y)
    cxx = np.cumsum(x * x); cxy = np.cumsum(x * y); cyy = np.cumsum(y * y)

    def ssr(m, sx, sy, sxx, sxy, syy):
        vxx = sxx - sx * sx / m
        vxy = sxy - sx * sy / m
        vyy = syy - sy * sy / m
        return vyy - vxy * vxy / vxx

    ssr0 = ssr(n, cx[-1], cy[-1], cxx[-1], cxy[-1], cyy[-1])
    lo, hi = int(math.ceil(TRIM * n)), int(math.floor((1 - TRIM) * n))
    k = np.arange(lo, hi + 1)  # first segment is the first k observations
    i = k - 1
    s1 = ssr(c1[i], cx[i], cy[i], cxx[i], cxy[i], cyy[i])
    s2 = ssr(n - c1[i], cx[-1] - cx[i], cy[-1] - cy[i], cxx[-1] - cxx[i], cxy[-1] - cxy[i], cyy[-1] - cyy[i])
    s = s1 + s2
    return float(np.max((ssr0 - s) / 2 / (s / (n - 4))))


def modes(x: np.ndarray, y: np.ndarray, eg: np.ndarray, detector: str, c: float | None, start: int = 0,
          horizon: int | None = None, trace: bool = False):
    """1 on closes in a spread spell, 0 otherwise. `trace` also returns the detector statistic each close
    (E: the Engle-Granger statistic; C: c^2 reached; B: sup-F), NaN outside spells."""
    n = len(x) if horizon is None else min(len(x), horizon)
    mode = np.zeros(n, dtype=np.int8)
    stat = np.full(n, np.nan)
    t0, st = None, None
    t = start
    while t < n:
        if t0 is None:
            if not np.isnan(eg[t]) and eg[t] < EG_CRIT:
                t0 = t
                mode[t] = 1
                if detector == "C":
                    st = cusum_start(x, y, t)
            t += 1
            continue
        k = t - t0
        if detector == "E":
            v = eg[t]; broke = not (v < EG_CRIT)
        elif detector == "C":
            st["s"] += y[t] - st["a"] - st["b"] * x[t]
            v = cusum_stat(k, st["s"], st["omega"]); broke = v > c * c
        else:
            v = sup_f(x[t0 - L + 1 : t + 1], y[t0 - L + 1 : t + 1]); broke = v > c
        stat[t] = v
        if broke:
            t0 = None  # the close that ends a spell cannot start the next
        else:
            mode[t] = 1
        t += 1
    return (mode, stat) if trace else mode


def trades(mode: np.ndarray, h: np.ndarray, b: np.ndarray, z: np.ndarray, spread_on: bool = True,
           copula_on: bool = True, hold_through: bool = False) -> list[dict]:
    """Position spells. Each: open close index, close index (None if still open), weights, method, side.
    With spread_on and copula_on both True this is the switch; with one off the other runs alone in its mode.
    hold_through keeps a spread trade open when its mode ends, as H4b's gate did (H4b alone)."""
    out = []
    n = len(mode)
    cur = None  # the open trade
    held = left = 0
    for t in range(n):
        m = mode[t]
        # Leave a position whose mode has ended.
        if cur is not None and cur["method"] != ("spread" if m else "copula") and not (hold_through and cur["method"] == "spread"):
            cur["close"] = t; out.append(cur); cur = None
        if spread_on and (m or (cur is not None and cur["method"] == "spread")):
            if cur is not None:
                held += 1
                side = cur["side"]
                back = (side == -1 and z[t] < EXIT) or (side == 1 and z[t] > -EXIT)
                if back or abs(z[t]) > STOP or held >= MAX_HOLD:
                    cur["close"] = t; out.append(cur); cur = None
            if cur is None and m and not np.isnan(z[t]) and abs(z[t]) > ENTRY:
                side = -1 if z[t] > 0 else 1  # z above the entry: NED rich, short NED and long SBK
                k = abs(b[t])
                cur = {"open": t, "close": None, "method": "spread", "side": side,
                       "w_sbk": -side * k / (1 + k), "w_ned": side / (1 + k)}
                held = 0
        elif not m and copula_on:
            if abs(h[t] - 0.5) > LEVEL:
                side = 1 if h[t] > 0.5 else -1
                if cur is not None and cur["side"] != side:
                    cur["close"] = t; out.append(cur); cur = None
                if cur is None:
                    cur = {"open": t, "close": None, "method": "copula", "side": side,
                           "w_sbk": 0.5 * side, "w_ned": -0.5 * side}
                left = HOLD
            elif cur is not None:
                left -= 1
            if cur is not None and left == 0:
                cur["close"] = t; out.append(cur); cur = None
    if cur is not None:
        out.append(cur)
    return out


def third_thursdays(y0: int = 2009, y1: int = 2031) -> list[dt.date]:
    out = []
    for yr in range(y0, y1 + 1):
        for mo in range(1, 13):
            first = dt.date(yr, mo, 1)
            out.append(first + dt.timedelta(days=(3 - first.weekday()) % 7 + 14))
    return out


EXPIRIES = third_thursdays()


def trade_costs(tr: dict, dates: list[dt.date], schedule: str) -> np.ndarray:
    """Cost of one trade by session (fraction of capital), charged on the close it falls on."""
    s = SCHEDULES[schedule]
    n = len(dates)
    c = np.zeros(n)
    ws, wn = tr["w_sbk"], tr["w_ned"]
    gross = abs(ws) + abs(wn)
    o, cl = tr["open"], tr["close"] if tr["close"] is not None else n
    buy_open = max(ws, 0) + max(wn, 0)  # legs bought to open; the short legs are bought back to close
    c[o] += (gross * s["exec"] + buy_open * s["stt"]) / 1e4
    if cl < n:
        c[cl] += (gross * s["exec"] + (gross - buy_open) * s["stt"]) / 1e4
    long_n = max(ws, 0) + max(wn, 0); short_n = gross - long_n
    daily = (long_n * s["long_year"] + short_n * s["short_year"]) / 1e4 / 252
    c[o + 1 : min(cl, n - 1) + 1] += daily
    if s["rolls"]:
        expiry = next(e for e in EXPIRIES if e >= dates[min(o + 10, n - 1)])
        for t in range(o + 1, min(cl, n)):
            if dates[t] >= expiry:
                c[t] += 2 * gross * s["exec"] / 1e4
                expiry = next(e for e in EXPIRIES if e >= dates[min(t + 10, n - 1)])
    return c


def daily_returns(trs: list[dict], dates: list[dt.date], r_sbk: np.ndarray, r_ned: np.ndarray,
                  schedule: str | None) -> tuple[np.ndarray, list[dict]]:
    """Daily net return (gross if schedule is None) and each trade's gross and net, simple returns."""
    n = len(dates)
    total = np.zeros(n)
    rows = []
    for tr in trs:
        cl = tr["close"] if tr["close"] is not None else n - 1
        g = np.zeros(n)
        g[tr["open"] + 1 : cl + 1] = tr["w_sbk"] * r_sbk[tr["open"] + 1 : cl + 1] + tr["w_ned"] * r_ned[tr["open"] + 1 : cl + 1]
        cost = trade_costs(tr, dates, schedule) if schedule else np.zeros(n)
        total += g - cost
        rows.append({**tr, "gross": float(g.sum()), "net": float((g - cost).sum()), "complete": tr["close"] is not None})
    return total, rows
