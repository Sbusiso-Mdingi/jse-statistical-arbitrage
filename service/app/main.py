"""HTTP service for the Standard Bank against Nedbank copula-GARCH dashboard."""

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

from . import data as market
from . import pair as pr
from . import rule
from . import shadow
from . import switch
from .model import MarginalState, conditional_probabilities, filter_marginal

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
    "http://localhost:8080",
]
FRAME_ANCESTORS = "'self' https://mdingi.co.za https://www.mdingi.co.za http://localhost:*"

walkforward = json.loads((DATA / "walkforward.json").read_text())
final = json.loads((DATA / "model_final.json").read_text())
PAIR = pr.Pair(walkforward, final, json.loads((DATA / "pair_gas.json").read_text()), json.loads((DATA / "refits.json").read_text())["refits"])
FREEZE = date.fromisoformat(walkforward["freeze"])
VOL_WINDOW = walkforward["vol_window"]
FINAL_ID = final["id"]
SHADOW = json.loads((DATA / "pair_shadow.json").read_text())
SWITCH = json.loads((DATA / "pair_switch.json").read_text())
SPREAD_GATE = json.loads((DATA / "pair_spread_gate.json").read_text())
H19 = json.loads((DATA / "pair_h19.json").read_text())
H18 = json.loads((DATA / "pair_h18.json").read_text())
DIVIDENDS = json.loads((DATA / "pair_dividends.json").read_text())
_switch_cache: dict = {}


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
        "vix": vix,
        # The dividend-correct series (H19, reporting): None where the live feed did not provide it.
        "div_sbk": [r.get("div_sbk") for r in rows],
        "div_ned": [r.get("div_ned") for r in rows],
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
        self.source = "snapshot"
        self.prices: dict | None = None
        self.gaps_1600: dict | None = None
        self.fetched_at: float = 0.0
        self.error: str | None = None

    def get(self) -> "LiveCache":
        if time.time() - self.fetched_at > REFRESH_SECONDS and self.lock.acquire(blocking=False):
            try:
                live = market.fetch_live(FREEZE)
                if live["rows"]:
                    self.rows = live_rows(live["rows"])
                    self.prices = live["prices"]
                    self.gaps_1600 = live.get("gaps_1600")
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


def _pair_run(period: str, p: rule.Params) -> dict:
    return rule.run(PAIR.rows(PAIR.live(cache.get().rows)), p, period)


@app.get("/api/pair/backtest")
def api_pair_backtest(
    period: str = Query("live", pattern="^(live|walkforward|all)$"),
    entry: int = 90,
    hold: int = 5,
    cost_bps: float = 10.0,
    costs: str = "protocol",
):
    """The instrument: SBK against NED on the score-driven copula, five-day hold."""
    return JSONResponse(_clean(_pair_run(period, rule.Params(entry, hold, cost_bps, costs).clamp())))


@app.get("/api/pair/model")
def api_pair_model():
    live = PAIR.live(cache.get().rows)
    return JSONResponse(_clean({"status": _status(), **pr.model_summary(PAIR, live)}))


@app.get("/api/shadow")
def api_shadow():
    """H13 (research/PROTOCOL.md): two volatility variants scored only on sessions from 10 November 2026."""
    rows = cache.get().rows
    pair = PAIR.rows(PAIR.live(rows))
    hist = walkforward["history"]
    a_h = shadow.own_vol_live(SHADOW["own_vol"], (np.array(hist["r_sbk"]), np.array(hist["r_ned"])),
                              {"u": rows["u"], "v": rows["v"], "r_sbk_log": rows["r_sbk"], "r_ned_log": rows["r_ned"]})
    rs, rn = np.expm1(rows["r_sbk"]), np.expm1(rows["r_ned"])
    gate = np.concatenate([np.zeros(len(hist["date"]), bool), rows["vix"] > SHADOW["vix_gate"]["level"]])
    rt = shadow.ROUND_TRIPS
    return JSONResponse(_clean({
        "protocol": "research/PROTOCOL.md, H13",
        "score_from": shadow.SCORE_FROM,
        "frozen_on": SHADOW["frozen_on"],
        "verdict_at": "225 signals or 31 December 2030; net per signal at the futures round trip above zero, one-sided t > 1.65",
        "round_trips_bps": rt,
        "as_of": rows["date"][-1],
        "own_vol_copula": shadow.score(rows["date"], a_h, rs, rn, None, rt),
        "vix_gate": {"level": SHADOW["vix_gate"]["level"], **shadow.score(pair["date"], pair["h0"], pair["r_sbk"], pair["r_ned"], gate, rt)},
        "h8_reference": shadow.score(pair["date"], pair["h0"], pair["r_sbk"], pair["r_ned"], None, rt),
    }))


def dividend_series(pair: dict):
    """Dividend-correct simple returns for the whole record (H19 and the reporting figures; PROTOCOL.md, amendment
    of 12 November 2026): the frozen returns plus, on ex-dividend sessions, the correction from research to 31 March
    2026 and from the live feed after it. Also the ex-dividend sessions and the live feed's state."""
    rows = cache.get().rows
    live = {d: (a, b) for d, a, b in zip(rows["date"], rows["div_sbk"], rows["div_ned"])}
    hist = DIVIDENDS["corrections"]
    n = len(pair["date"])
    corr = {"sbk": np.zeros(n), "ned": np.zeros(n)}
    ex_day = np.zeros(n, bool)
    missing, events = 0, []
    for i, d in enumerate(pair["date"]):
        if d.isoformat() <= DIVIDENDS["to"]:
            for k in corr:
                c = hist[k].get(d.isoformat())
                if c is not None:
                    corr[k][i] = c; ex_day[i] = True
            continue
        got = live.get(d)
        if got is None or got[0] is None or got[1] is None:
            missing += 1
            continue
        for k, g in zip(("sbk", "ned"), got):
            corr[k][i] = g["corr"]
            if g["dividend"]:
                ex_day[i] = True
                events.append({"date": d, "bank": k, "dividend_cents": g["dividend"], "yield": round(g["yield"], 5), "bad": g["bad"],
                               "yahoo_step_over_yield": None if g["yahoo_step_over_yield"] is None else round(g["yahoo_step_over_yield"], 4)})
    total = tuple(np.expm1(np.log1p(pair[f"r_{k}"]) + corr[k]) for k in ("sbk", "ned"))
    return total, ex_day, {"sessions_without_dividend_data": missing, "live_ex_dividend": events}


def switch_state(pair: dict) -> dict:
    """H14 and H16 (research/PROTOCOL.md): the rolling Engle-Granger statistic, today's method and the live records
    of the switch, the copula rule alone and the gated spread trade, each scored on trades opened from 1 April
    2026 (PROTOCOL.md, amendment of 11 November 2026), with the position each carries into the next session."""
    as_of = pair["date"][-1]
    if _switch_cache.get("as_of") != as_of:
        frm = {"switch": SWITCH["score_from"], "copula_alone": SWITCH["score_from"], "spread_gate": SPREAD_GATE["score_from"],
               "spread_gate_dividends": H19["score_from"], "spread_gate_1600": H18["score_from"]}
        total, ex_day, div_live = dividend_series(pair)
        g = cache.get().gaps_1600
        gap = None
        if g:
            gap = tuple(np.array([g[d][j] if d in g else np.nan for d in pair["date"]]) for j in (0, 1))
        r = switch.record(pair["date"], pair["r_sbk"], pair["r_ned"], pair["h"], {k: date.fromisoformat(v) for k, v in frm.items()},
                          total=total, ex_day=ex_day, gap_1600=gap)
        mode, eg, b, gate = r["mode"], r["eg"], r["b"], r["gate"]
        spread_days = np.flatnonzero(mode)
        gate_days = np.flatnonzero(gate)
        seg = SWITCH["bai_perron"]["segments"][-1]
        _switch_cache.clear()
        _switch_cache.update(as_of=as_of, body={
            "protocol": "research/PROTOCOL.md, H14",
            "frozen_on": SWITCH["frozen_on"],
            "score_from": SWITCH["score_from"],
            "verdict_at": SWITCH["verdict"],
            "window": switch.L,
            "crit": switch.EG_CRIT,
            "as_of": as_of,
            "today": {"eg": float(eg[-1]), "hedge_ratio": float(b[-1]), "z": float(r["z"][-1]), "holds": bool(eg[-1] < switch.EG_CRIT),
                      "mode": "spread" if mode[-1] else "copula",
                      "last_spread_day": pair["date"][spread_days[-1]] if len(spread_days) else None,
                      "gate_open": bool(eg[-1] < switch.GATE_CRIT),
                      "last_gate_day": pair["date"][gate_days[-1]] if len(gate_days) else None},
            "segment": seg,
            "reference": SWITCH["reference"],
            "series": {"date": pair["date"], "eg": eg, "mode": mode, "gate": gate},
            # The service's record starts in 2010, so its window first fills in mid-2010; that year comes from research.
            "spread_share_by_year": {str(y): (SWITCH["spread_mode_share_by_year"]["2010"] if y == 2010 else float(mode[[d.year == y for d in pair["date"]]].mean()))
                                     for y in sorted({d.year for d in pair["date"]})},
            "switch": {k: v for k, v in r["switch"].items() if k not in ("daily", "history")},
            "copula_alone": {k: v for k, v in r["copula_alone"].items() if k not in ("daily", "history")},
            "spread_gate": {**{k: v for k, v in r["spread_gate"].items() if k not in ("daily", "history")}, "crit": switch.GATE_CRIT, "frozen_on": SPREAD_GATE["frozen_on"], "score_from": SPREAD_GATE["score_from"],
                            "verdict_at": SPREAD_GATE["verdict"], "development": SPREAD_GATE["development"],
                            "expected_live_bps": SPREAD_GATE["expected_live_bps"]},
            "spread_gate_dividends": {**{k: v for k, v in r["spread_gate_dividends"].items() if k not in ("daily", "history")},
                                      **{k: H19[k] for k in ("protocol", "frozen_on", "score_from", "verdict", "critical_value", "development", "expected_live_bps")},
                                      "today": {"eg": float(r["dividends"]["eg"][-1]), "z": float(r["dividends"]["z"][-1]), "gate_open": bool(r["dividends"]["eg"][-1] < switch.GATE_CRIT)},
                                      "data": div_live},
            "spread_gate_1600": ({**{k: v for k, v in r["spread_gate_1600"].items() if k not in ("daily", "history")},
                                  **{k: H18[k] for k in ("protocol", "frozen_on", "score_from", "verdict", "critical_value", "development", "expected_live_bps")},
                                  "today": {"eg": float(r["h18"]["eg"][-1]) if not np.isnan(r["h18"]["eg"][-1]) else None,
                                            "z": float(r["h18"]["z"][-1]) if not np.isnan(r["h18"]["z"][-1]) else None},
                                  "data": {"first_1600": min(g).isoformat(), "sessions_with_1600": int(np.isfinite(gap[0]).sum()),
                                           "sessions_without_1600_since_score_from": int(sum(1 for d, v in zip(pair["date"], gap[0])
                                                                                            if d.isoformat() >= H18["score_from"] and np.isnan(v)))}}
                                 if gap is not None else {"available": False}),
        })
        # Each strategy as a book: cumulative net P&L in % of capital (daily net returns summed, no compounding).
        _switch_cache["pnl"] = {
            "as_of": as_of, "date": pair["date"], "score_from": SPREAD_GATE["score_from"], "development_end": "2026-03-31", "frozen_on": SPREAD_GATE["frozen_on"],
            "strategies": {k: {"cum": {sch: np.round(np.cumsum(r[k]["daily"][sch]) * 100, 4) for sch in switch.SCHEDULES},
                               "trades": r[k]["history"]}
                           for k in ("spread_gate", "switch", "copula_alone")},
        }
    return _switch_cache["body"]


@app.get("/api/switch")
def api_switch():
    return JSONResponse(_clean(switch_state(PAIR.rows(PAIR.live(cache.get().rows)))))


@app.get("/api/pnl")
def api_pnl():
    """Each strategy's cumulative net P&L over the service's record, at both institutional schedules, and its trades."""
    switch_state(PAIR.rows(PAIR.live(cache.get().rows)))
    last = PAIR.refits[-1]
    return JSONResponse(_clean({**_switch_cache["pnl"], "last_refit": last["train_end"] if len(PAIR.refits) > 1 else None,
                                "last_refit_from": last["applies_from"] if len(PAIR.refits) > 1 else None}))


@app.get("/api/research")
def api_research():
    """Decay study and every pre-registered test, written by research/export_research.py."""
    return FileResponse(DATA / "research.json", media_type="application/json")


@app.get("/api/summary")
def api_summary():
    """The instrument's record, used by the portfolio case study: SBK against NED on the score-driven copula."""
    def block(r):
        return {"start": r["start"], "end": r["end"], **r["metrics"]}

    bp = rule.Params()
    live = _pair_run("live", bp)
    inst = rule.Params(costs="institutional")
    return JSONResponse(
        _clean(
            {
                "strategy": "pair",
                "params": bp.__dict__,
                "live": block(live),
                "walkforward": block(_pair_run("walkforward", bp)),
                "live_institutional": block(_pair_run("live", inst)),
                "latest": live["latest"],
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
