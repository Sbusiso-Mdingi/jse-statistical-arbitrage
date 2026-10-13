"""Daily JSE trading volume from Yahoo Finance for the banks used by H2a and H3."""
import csv, sys
from datetime import date, datetime, timedelta, timezone
import httpx

sys.path.insert(0, "service")
from app.data import YAHOO, SAST

for name, sym in {"sbk": "SBK.JO", "ned": "NED.JO", "fsr": "FSR.JO", "abg": "ABG.JO", "cpi": "CPI.JO"}.items():
    p1 = int(datetime(2005, 1, 1, tzinfo=timezone.utc).timestamp())
    p2 = int(datetime.now(timezone.utc).timestamp()) + 86400
    r = httpx.get(YAHOO.format(symbol=sym), params={"period1": p1, "period2": p2, "interval": "1d"},
                  headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
    r.raise_for_status()
    res = r.json()["chart"]["result"][0]
    vol = res["indicators"]["quote"][0]["volume"]
    with open(f"data/raw/{name}_volume.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "volume"])
        for ts, v in zip(res["timestamp"], vol):
            w.writerow([datetime.fromtimestamp(ts, SAST).date().isoformat(), "" if v is None else v])
    print(name, len(vol))
