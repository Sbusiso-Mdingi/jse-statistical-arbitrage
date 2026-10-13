"""Live market data: Yahoo Finance daily prices and FRED VIX."""

from __future__ import annotations

import csv
import io
import math
from datetime import date, datetime, timedelta, timezone

import httpx

SAST = timezone(timedelta(hours=2))
JSE_CLOSE_BUFFER = (17, 30)  # Closing auction ends at 17:00 SAST; wait for the final print.
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; mdingi-research/1.0)"}


def _today_complete(now: datetime) -> bool:
    local = now.astimezone(SAST)
    return (local.hour, local.minute) >= JSE_CLOSE_BUFFER


def yahoo_daily(client: httpx.Client, symbol: str, start: date, local: bool = True) -> dict[date, float]:
    period1 = int(datetime.combine(start, datetime.min.time(), timezone.utc).timestamp())
    period2 = int(datetime.now(timezone.utc).timestamp()) + 86400
    resp = client.get(
        YAHOO.format(symbol=symbol),
        params={"period1": period1, "period2": period2, "interval": "1d", "events": "div,split"},
    )
    resp.raise_for_status()
    result = resp.json()["chart"]["result"][0]
    adj = result["indicators"]["adjclose"][0]["adjclose"]
    now = datetime.now(timezone.utc)
    today = now.astimezone(SAST).date()
    out: dict[date, float] = {}
    for ts, price in zip(result["timestamp"], adj):
        tz = SAST if local else timezone(timedelta(hours=-5))
        day = datetime.fromtimestamp(ts, tz).date()
        if price is None or price <= 0:
            continue
        if local and day == today and not _today_complete(now):
            continue
        out[day] = float(price)
    return out


def fred_vix(start: date) -> dict[date, float]:
    # FRED rejects some custom user agents, so it gets a plain client.
    resp = httpx.get(FRED, params={"id": "VIXCLS", "cosd": start.isoformat()}, timeout=20)
    resp.raise_for_status()
    out: dict[date, float] = {}
    for row in csv.reader(io.StringIO(resp.text)):
        if len(row) != 2 or row[1] in ("", ".") or row[0] in ("DATE", "observation_date"):
            continue
        out[date.fromisoformat(row[0])] = float(row[1]) / 100
    return out


def drop_bad_prints(series: dict[date, float], jump: float = 0.4) -> dict[date, float]:
    """Same rule as research/clean.R: a >40% jump that reverses the next day."""
    days = sorted(series)
    limit = math.log(1 + jump)
    while True:
        prices = [series[d] for d in days]
        r = [math.log(prices[i + 1] / prices[i]) for i in range(len(prices) - 1)]
        bad = [
            days[i + 1]
            for i in range(len(r) - 1)
            if abs(r[i]) > limit and (r[i] > 0) != (r[i + 1] > 0) and abs(r[i] + r[i + 1]) < limit / 4
        ]
        if not bad:
            return {d: series[d] for d in days}
        days = [d for d in days if d not in set(bad)]


BASKET = {"fsr": "FSR.JO", "abg": "ABG.JO", "ned": "NED.JO", "cpi": "CPI.JO"}


def fetch_live(freeze: date, basket_start: date) -> dict:
    """Prices from shortly before the pair's freeze date and the basket's latest fit
    to the latest completed session."""
    start = min(freeze, basket_start) - timedelta(days=10)
    with httpx.Client(headers=HEADERS, timeout=20, follow_redirects=True) as client:
        px = {k: drop_bad_prints(yahoo_daily(client, s, start)) for k, s in {"sbk": "SBK.JO", **BASKET}.items()}
        try:
            vix = fred_vix(start - timedelta(days=10))
        except httpx.HTTPError:
            # Same CBOE close, published by Yahoo.
            vix = {d: v / 100 for d, v in yahoo_daily(client, "^VIX", start - timedelta(days=10), local=False).items()}
    vix_days = sorted(vix)

    def known_vix(day: date) -> float | None:
        known = [v for v in vix_days if v < day]
        return vix[known[-1]] if known else None

    def rows_from(anchor: date, names: list[str], make) -> list[dict]:
        days = sorted(set.intersection(*(set(px[k]) for k in names)))
        if anchor not in days:
            raise RuntimeError(f"Prices for {anchor} missing from the live feed")
        days = [d for d in days if d >= anchor]
        out = []
        for prev, day in zip(days, days[1:]):
            vx = known_vix(day)
            if vx is not None:
                out.append({"date": day, "vix": vx, **make(prev, day)})
        return out

    pair = rows_from(freeze, ["sbk", "ned"], lambda a, b: {
        "r_sbk": math.log(px["sbk"][b] / px["sbk"][a]),
        "r_ned": math.log(px["ned"][b] / px["ned"][a]),
    })
    basket = rows_from(basket_start, ["sbk", *BASKET], lambda a, b: {
        "r_sbk": math.log(px["sbk"][b] / px["sbk"][a]),
        # Equal-weight basket rebalanced daily, as a log return for the volatility model.
        "r_bsk": math.log1p(sum(px[k][b] / px[k][a] - 1 for k in BASKET) / len(BASKET)),
    })
    last = max(r["date"] for r in pair)
    return {
        "rows": pair,
        "basket_rows": basket,
        "prices": {k: s[last] for k, s in px.items() if last in s},
        "as_of": last,
    }
