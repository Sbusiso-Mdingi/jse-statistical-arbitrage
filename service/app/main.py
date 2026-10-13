"""HTTP service for the JSE bank copula-GARCH pairs dashboard."""

from __future__ import annotations

import json
import logging
import math
import os
import threading
import time
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import basket as bk
from . import data as market
from .model import MarginalState, conditional_probabilities, filter_marginal
from .strategy import Params, backtest, metrics, window

log = logging.getLogger("pairs")
ROOT = Path(os.environ.get("APP_ROOT", Path(__file__).resolve().parents[2]))
DATA = ROOT / "data"
STATIC = ROOT / "dashboard" / "dist"
REFRESH_SECONDS = int(os.environ.get("REFRESH_SECONDS", "1800"))
ALLOWED_ORIGINS = [
    "https://mdingi.co.za",
    "https://www.mdingi.co.za",
    "http://localhost:3000",
    "http://localhost:4321",
    "http://localhost:5173",
]
FRAME_ANCESTORS = "'self' https://mdingi.co.za https://www.mdingi.co.za http://localhost:*"

walkforward = json.loads((DATA / "walkforward.json").read_text())
final = json.loads((DATA / "model_final.json").read_text())
BASKET = bk.Basket(json.loads((DATA / "basket.json").read_text()))
FREEZE = date.fromisoformat(walkforward["freeze"])
VOL_WINDOW = walkforward["vol_window"]
folds = {f["id"]: f for f in walkforward["folds"]}
FINAL_ID = final["id"]


def _history() -> dict:
    h = walkforward["history"]
    return {
        "date": [date.fromisoformat(d) for d in h["date"]],
        "fold": np.array(h["fold"], dtype=int),
        "r_sbk": np.array(h["r_sbk"], dtype=float),
        "r_ned": np.array(h["r_ned"], dtype=float),
        "u": np.array(h["u"], dtype=float),
        "v": np.array(h["v"], dtype=float),
        "h_ns": np.array(h["h_ns"], dtype=float),
        "h_sn": np.array(h["h_sn"], dtype=float),
        "spread_vol": np.array(h["spread_vol"], dtype=float),
    }


HISTORY = _history()


def _state(key: str) -> MarginalState:
    s = final["state"][key]
    return MarginalState(r=s["r"], mu=s["mu"], sigma=s["sigma"], z=s["z"])


def live_rows(rows: list[dict]) -> dict:
    """Filter post-freeze returns with the parameters frozen on 31 March 2026."""
    r_sbk = np.array([r["r_sbk"] for r in rows])
    r_ned = np.array([r["r_ned"] for r in rows])
    vix = np.array([r["vix"] for r in rows])
    fs = filter_marginal(final["sbk"], _state("sbk"), r_sbk, vix)
    fn = filter_marginal(final["ned"], _state("ned"), r_ned, vix)
    h_ns, h_sn = conditional_probabilities(final["copula"], fs["u"], fn["u"])
    spread = np.concatenate(
        [np.array(final["state"]["vol_tail_sbk"]) - np.array(final["state"]["vol_tail_ned"]), r_sbk - r_ned]
    )
    vol = np.array([np.std(spread[i : i + VOL_WINDOW], ddof=1) for i in range(len(rows))])
    return {
        "date": [r["date"] for r in rows],
        "fold": np.full(len(rows), FINAL_ID),
        "r_sbk": r_sbk,
        "r_ned": r_ned,
        "u": fs["u"],
        "v": fn["u"],
        "h_ns": h_ns,
        "h_sn": h_sn,
        "spread_vol": vol,
        "sigma_sbk": fs["sigma"],
        "sigma_ned": fn["sigma"],
    }


def snapshot_rows() -> list[dict]:
    p = final["parity"]
    return [
        {"date": date.fromisoformat(d), "r_sbk": a, "r_ned": b, "vix": v}
        for d, a, b, v in zip(p["date"], p["r_sbk"], p["r_ned"], p["vix"])
    ]


class LiveCache:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.rows = live_rows(snapshot_rows())
        self.basket_rows = BASKET.live_rows(BASKET.snapshot_rows())
        self.source = "snapshot"
        self.prices: dict | None = None
        self.fetched_at: float = 0.0
        self.error: str | None = None

    def get(self) -> "LiveCache":
        if time.time() - self.fetched_at > REFRESH_SECONDS and self.lock.acquire(blocking=False):
            try:
                live = market.fetch_live(FREEZE, BASKET.train_end)
                if live["rows"] and live["basket_rows"]:
                    self.rows = live_rows(live["rows"])
                    self.basket_rows = BASKET.live_rows(live["basket_rows"])
                    self.prices = live["prices"]
                    self.source = "live"
                    self.error = None
            except Exception as exc:  # keep serving the last good data
                log.warning("live refresh failed: %s", exc)
                self.error = str(exc)
            finally:
                self.fetched_at = time.time()
                self.lock.release()
        return self


cache = LiveCache()
app = FastAPI(title="SBK/NED copula-GARCH pairs", docs_url="/api/docs", openapi_url="/api/openapi.json")
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_methods=["GET"], allow_headers=["*"])


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = f"frame-ancestors {FRAME_ANCESTORS}"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "public, max-age=300"
    return response


def _rows(period: str) -> dict:
    live = cache.get().rows
    if period == "live":
        return live
    if period == "walkforward":
        return HISTORY
    return {k: (HISTORY[k] + live[k] if k == "date" else np.concatenate([HISTORY[k], live[k]])) for k in HISTORY}


def _clean(x):
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return None
    if isinstance(x, (np.floating,)):
        return _clean(float(x))
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, dict):
        return {k: _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if isinstance(x, np.ndarray):
        return [_clean(v) for v in x.tolist()]
    if isinstance(x, date):
        return x.isoformat()
    return x


def _keep(dates: list, period: str) -> np.ndarray:
    if period == "all":
        return np.ones(len(dates), bool)
    return np.array([(d > FREEZE) == (period == "live") for d in dates])


def run(period: str, p: Params) -> dict:
    rows = _rows("all")
    full = backtest(rows, folds, p)
    w = window(rows["date"], _keep(rows["date"], period), full["position"], full["daily"], full["bench_daily"])
    sl, dates, pos = w["slice"], w["dates"], w["position"]
    fold_ids = rows["fold"][sl]
    open_level = [
        folds[int(f)]["q_signal"][p.entry - 50] if p.rule == "probability" else p.threshold for f in fold_ids
    ]
    close_level = [
        folds[int(f)]["q_signal"][p.exit - 50] if p.rule == "probability" else 0.0 for f in fold_ids
    ]
    trades = [
        {
            "open": rows["date"][t["open"]],
            "close": rows["date"][t["close"]] if t["close"] is not None else None,
            "side": "Long SBK / short NED" if t["side"] > 0 else "Short SBK / long NED",
            "return": t["ret"],
        }
        for t in w["trades"]
    ]
    return {
        "period": period,
        "params": p.__dict__,
        "start": dates[0],
        "end": dates[-1],
        "metrics": metrics(dates, w["daily"], w["equity"], pos, w["trades"]),
        "benchmark": metrics(dates, w["bench_daily"], w["benchmark"], np.ones(len(pos)), []),
        "latest": {
            "date": dates[-1],
            "position": float(pos[-1]),
            "h_ns": float(rows["h_ns"][sl][-1]),
            "h_sn": float(rows["h_sn"][sl][-1]),
        },
        "series": {
            "date": dates,
            "equity": w["equity"],
            "benchmark": w["benchmark"],
            "position": pos,
            "h_ns": rows["h_ns"][sl],
            "h_sn": rows["h_sn"][sl],
            "open_level": open_level,
            "close_level": close_level,
        },
        "trades": trades,
    }


def _params(rule, entry, exit, vol_filter, vol_pct, threshold, cost_bps) -> Params:
    return Params(rule, entry, exit, vol_filter, vol_pct, threshold, cost_bps).clamp()


@app.get("/api/backtest")
def api_backtest(
    period: str = Query("live", pattern="^(live|walkforward|all)$"),
    rule: str = "probability",
    entry: int = 90,
    exit: int = 50,
    vol_filter: bool = True,
    vol_pct: int = 80,
    threshold: float = 0.6,
    cost_bps: float = 10.0,
):
    return JSONResponse(_clean(run(period, _params(rule, entry, exit, vol_filter, vol_pct, threshold, cost_bps))))


def _basket_run(period: str, p: bk.BasketParams) -> dict:
    return bk.run(BASKET.rows("all", cache.get().basket_rows), p, period)


@app.get("/api/basket/backtest")
def api_basket_backtest(
    period: str = Query("live", pattern="^(live|walkforward|all)$"),
    entry: int = 90,
    hold: int = 5,
    cost_bps: float = 10.0,
):
    return JSONResponse(_clean(_basket_run(period, bk.BasketParams(entry, hold, cost_bps).clamp())))


@app.get("/api/basket/model")
def api_basket_model():
    return JSONResponse(_clean({"status": _status(), **bk.model_summary(BASKET, cache.get().basket_rows)}))


@app.get("/api/research")
def api_research():
    """Decay study and every pre-registered test, written by research/export_research.py."""
    return FileResponse(DATA / "research.json", media_type="application/json")


@app.get("/api/summary")
def api_summary():
    """Pre-registered strategies, used by the portfolio case study. The basket is the headline."""
    def block(r):
        return {"start": r["start"], "end": r["end"], **r["metrics"]}

    bp, pp = bk.BasketParams(), Params()
    live = _basket_run("live", bp)
    return JSONResponse(
        _clean(
            {
                "strategy": "basket",
                "params": bp.__dict__,
                "live": block(live),
                "walkforward": block(_basket_run("walkforward", bp)),
                "latest": live["latest"],
                "pair": {"params": pp.__dict__, "live": block(run("live", pp)), "walkforward": block(run("walkforward", pp))},
                "status": _status(),
            }
        )
    )


def _status() -> dict:
    c = cache.get()
    return {
        "freeze": FREEZE,
        "as_of": c.rows["date"][-1],
        "source": c.source,
        "fetched_at": datetime.fromtimestamp(c.fetched_at, timezone.utc).isoformat() if c.fetched_at else None,
        "error": c.error,
        "prices": c.prices,
    }


@app.get("/api/model")
def api_model():
    c = cache.get()
    def spec(s):
        return {k: s[k] for k in ("model", "arma", "dist", "vix", "coef", "bic")}
    return JSONResponse(
        _clean(
            {
                "status": _status(),
                "folds": [
                    {
                        "id": f["id"],
                        "train_end": f["train_end"],
                        "trade_start": f["trade_start"],
                        "trade_end": f["trade_end"] if not f["final"] else c.rows["date"][-1],
                        "final": f["final"],
                        "sbk": spec(f["sbk"]),
                        "ned": spec(f["ned"]),
                        "copula": f["copula"],
                        "pit_ks": f["pit_ks"],
                    }
                    for f in walkforward["folds"]
                ],
                "pit": {
                    "walkforward": {"u": HISTORY["u"], "v": HISTORY["v"]},
                    "live": {"u": c.rows["u"], "v": c.rows["v"], "date": c.rows["date"]},
                },
            }
        )
    )


@app.get("/healthz")
def healthz():
    return {"ok": True}


if STATIC.exists():
    app.mount("/assets", StaticFiles(directory=STATIC / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        target = STATIC / path
        if path and target.is_file():
            return FileResponse(target)
        return FileResponse(STATIC / "index.html")
