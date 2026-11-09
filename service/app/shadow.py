"""H13: two volatility variants scored only on live sessions (research/PROTOCOL.md). Served at /api/shadow,
kept off the dashboard.

A, the own-volatility copula (H12 gauge d): f_t = omega + beta f_{t-1} + alpha s_{t-1} + gamma x_t,
rho_t = tanh f_t, nu_t = 2 + exp(eta0 + eta1 x_t), x_t the standardised log 20-session volatility of the
equal-weighted SBK and NED log return before session t. Frozen in data/pair_shadow.json.
B, the VIX gate: the H8 signal opened only when the VIX before the session is above the frozen level.
"""

from __future__ import annotations

import math
from datetime import date

import numpy as np
from scipy import special, stats

from .model import t_copula_score_rho

SCORE_FROM = date(2026, 11, 10)
LEVEL = 0.45
HOLD = 5
CLIP = 1e-6
# Institutional round trips, bps (research/results/derivative_costs.json): single stock futures, and cash with borrow.
ROUND_TRIPS = {"futures_institutional": 33.8, "cash_institutional": 59.6}


def own_gauge(r_sbk: np.ndarray, r_ned: np.ndarray, mu: float, sd: float, window: int = 20) -> np.ndarray:
    """Standardised log volatility of the equal-weighted log return over the `window` sessions before each one."""
    eq = 0.5 * (np.asarray(r_sbk) + np.asarray(r_ned))
    x = np.zeros(len(eq))
    for t in range(window, len(eq)):
        x[t] = (math.log(np.std(eq[t - window : t], ddof=1)) - mu) / sd
    return x


def x_filter(p: dict, u: np.ndarray, v: np.ndarray, x: np.ndarray, f_prev: float, s_prev: float) -> dict:
    u, v = np.clip(u, CLIP, 1 - CLIP), np.clip(v, CLIP, 1 - CLIP)
    nu = 2 + np.exp(np.clip(p["eta0"] + p["eta1"] * x, -3, 6))
    xs, ys = stats.t.ppf(u, nu), stats.t.ppf(v, nu)
    f = np.empty(len(u))
    for t in range(len(u)):
        ft = p["omega"] + p["beta"] * f_prev + p["alpha"] * s_prev + p["gamma"] * x[t]
        ft = max(min(ft, 4.0), -4.0)
        f[t] = ft
        rho = math.tanh(ft)
        s_prev = t_copula_score_rho(xs[t], ys[t], rho, nu[t]) * (1 - rho * rho)
        f_prev = ft
    rho = np.tanh(f)
    q = (xs * xs - 2 * rho * xs * ys + ys * ys) / (1 - rho * rho)
    lf2 = (special.gammaln((nu + 2) / 2) - special.gammaln(nu / 2) - np.log(nu * math.pi)
           - 0.5 * np.log(1 - rho * rho) - (nu + 2) / 2 * np.log1p(q / nu))
    logc = lf2 - stats.t.logpdf(xs, nu) - stats.t.logpdf(ys, nu)
    h = stats.t.cdf((ys - rho * xs) / np.sqrt((nu + xs * xs) * (1 - rho * rho) / (nu + 1)), nu + 1)
    return {"h": np.clip(h, 1e-10, 1 - 1e-10), "logc": logc, "rho": rho, "nu": nu, "f_last": f_prev, "s_last": s_prev}


def own_vol_live(frozen: dict, hist_r: tuple, live: dict) -> np.ndarray:
    """h for the post-freeze sessions in `live`, filtered on from the state frozen at the end of training."""
    g = frozen["gauge"]
    rs = np.concatenate([hist_r[0], live["r_sbk_log"]])
    rn = np.concatenate([hist_r[1], live["r_ned_log"]])
    x = own_gauge(rs, rn, g["mu"], g["sd"], g["window"])[len(hist_r[0]):]
    st = frozen["state"]
    return x_filter(frozen["params"], live["u"], live["v"], x, st["f_last"], st["s_last"])["h"]


def score(dates: list, h: np.ndarray, r_sbk: np.ndarray, r_ned: np.ndarray, gate: np.ndarray | None,
          round_trips: dict) -> dict:
    """Signals on sessions from SCORE_FROM; gross five-day return per signal (simple returns, bps of capital)."""
    spread = 0.5 * (np.asarray(r_sbk) - np.asarray(r_ned))
    sig, done = [], []
    for t, d in enumerate(dates):
        if d < SCORE_FROM or abs(h[t] - 0.5) <= LEVEL or (gate is not None and not gate[t]):
            continue
        side = 1.0 if h[t] > 0.5 else -1.0
        complete = t + HOLD < len(dates)
        gross = float(side * spread[t + 1 : t + 1 + HOLD].sum() * 1e4) if complete else None
        sig.append({"date": d, "side": "Long SBK / short NED" if side > 0 else "Short SBK / long NED",
                    "h": float(h[t]), "gross_bps": None if gross is None else round(gross, 1)})
        if gross is not None:
            done.append(gross)
    out = {"signals": sig, "complete": len(done)}
    if done:
        g = np.array(done)
        se = float(g.std(ddof=1) / math.sqrt(len(g))) if len(g) > 1 else None
        out["gross_bps"] = round(float(g.mean()), 1)
        out["se"] = None if se is None else round(se, 1)
        for k, c in round_trips.items():
            net = float(g.mean() - c)
            out[f"net_{k}"] = round(net, 1)
            out[f"t_{k}"] = None if not se else round(net / se, 2)
    return out
