"""Inputs for H15 (research/PROTOCOL.md), downloaded, not redistributed (data/raw is gitignored).

  python research/h15_data.py

Yahoo Finance daily closes: the two banks and two other large SA banks (FirstRand, Absa; a sector reference for the
decomposition only, never traded), and the dollar against the rand, naira, Kenyan shilling, kwanza and cedi.
Dividend events for SBK and NED from the same chart endpoint. The OECD South African immediate rate from FRED
(IRSTCI01ZAM156N, monthly). Writes data/raw/h15_px.csv, h15_div.csv and h15_rate.csv.
"""
import csv, sys, time
from datetime import date, datetime, timezone, timedelta
import httpx

sys.path.insert(0, "service")
from app.data import HEADERS, YAHOO  # noqa: E402

SYMBOLS = {"sbk": "SBK.JO", "ned": "NED.JO", "fsr": "FSR.JO", "abg": "ABG.JO",
           "usdzar": "ZAR=X", "usdngn": "NGN=X", "usdkes": "KES=X", "usdaoa": "AOA=X", "usdghs": "GHS=X"}
SAST = timezone(timedelta(hours=2))


def chart(client, symbol):
    p1 = int(datetime(2005, 1, 1, tzinfo=timezone.utc).timestamp()); p2 = int(time.time()) + 86400
    r = client.get(YAHOO.format(symbol=symbol), params={"period1": p1, "period2": p2, "interval": "1d", "events": "div,split"})
    r.raise_for_status()
    return r.json()["chart"]["result"][0]


def main():
    px, divs = {}, []
    with httpx.Client(headers=HEADERS, timeout=30, follow_redirects=True) as c:
        for k, s in SYMBOLS.items():
            res = chart(c, s)
            q = res["indicators"]
            vals = q["adjclose"][0]["adjclose"] if "adjclose" in q else q["quote"][0]["close"]
            for ts, v in zip(res["timestamp"], vals):
                if v is not None and v > 0:
                    px.setdefault(datetime.fromtimestamp(ts, SAST).date(), {})[k] = v
            for ev in (res.get("events", {}).get("dividends", {}) or {}).values():
                if k in ("sbk", "ned"):
                    divs.append((datetime.fromtimestamp(ev["date"], SAST).date().isoformat(), k, ev["amount"]))
            print(k, s, len(res["timestamp"]))
    with open("data/raw/h15_px.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["date", *SYMBOLS])
        for d in sorted(px):
            w.writerow([d.isoformat(), *[px[d].get(k, "") for k in SYMBOLS]])
    with open("data/raw/h15_div.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["ex_date", "bank", "amount"]); w.writerows(sorted(divs))
    r = httpx.get("https://fred.stlouisfed.org/graph/fredgraph.csv", params={"id": "IRSTCI01ZAM156N"}, timeout=30)
    r.raise_for_status()
    open("data/raw/h15_rate.csv", "w").write(r.text)


if __name__ == "__main__":
    main()
