"""Daily capture of the 16:00 prices H18 decides on (research/PROTOCOL.md, H18), run as a Cloud Run job.

For each of the last sessions Yahoo's hourly bars cover (10 calendar days), the close of the 15:00-16:00 SAST bar
for Standard Bank and Nedbank is written to the private bucket as 1600/<date>.json, only if that object does not
exist yet (so a missed run fills itself in on the next, and nothing captured is ever overwritten). The raw bars of
the day are kept with it for audit. Standard library only; the job's own service account authenticates through the
metadata server, so no key exists anywhere.
"""
import datetime as dt
import json
import os
import urllib.error
import urllib.parse
import urllib.request

BUCKET = os.environ["BUCKET"]
SYMBOLS = {"sbk": "SBK.JO", "ned": "NED.JO"}
SAST = dt.timezone(dt.timedelta(hours=2))
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/{}?interval=60m&range=10d"
UA = {"User-Agent": "Mozilla/5.0 (compatible; mdingi-research/1.0)"}


def get_json(url, headers=None):
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers or {}), timeout=30) as r:
        return json.load(r)


def token():
    url = "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token"
    return get_json(url, {"Metadata-Flavor": "Google"})["access_token"]


def bars(symbol):
    res = get_json(YAHOO.format(symbol), UA)["chart"]["result"][0]
    q = res["indicators"]["quote"][0]
    out = {}
    for i, ts in enumerate(res["timestamp"]):
        t = dt.datetime.fromtimestamp(ts, SAST)
        out.setdefault(t.date().isoformat(), {})[t.strftime("%H:%M")] = {k: q[k][i] for k in ("open", "high", "low", "close", "volume")}
    return out


def put_if_absent(tok, name, body):
    """Create gs://BUCKET/name only if it does not exist (ifGenerationMatch=0). True if written."""
    url = ("https://storage.googleapis.com/upload/storage/v1/b/" + BUCKET + "/o?uploadType=media&ifGenerationMatch=0&name="
           + urllib.parse.quote(name, safe=""))
    req = urllib.request.Request(url, data=json.dumps(body, indent=1).encode(), method="POST",
                                 headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=30).read()
        return True
    except urllib.error.HTTPError as e:
        if e.code == 412:  # already captured
            return False
        raise


def main():
    now = dt.datetime.now(SAST)
    b = {k: bars(s) for k, s in SYMBOLS.items()}
    tok = token()
    written, skipped, missing = [], [], []
    for day in sorted(set(b["sbk"]) & set(b["ned"])):
        if day == now.date().isoformat() and (now.hour, now.minute) < (17, 15):
            continue  # today's bars are not final yet
        p = {k: (b[k][day].get("15:00") or {}).get("close") for k in SYMBOLS}
        if any(v is None for v in p.values()):
            missing.append(day)
            continue
        body = {"date": day, "price_1600": p, "bar": "15:00-16:00 SAST, last trade", "units": "cents", "source": "Yahoo Finance chart API, 60m",
                "captured_at": now.isoformat(), "bars": {k: b[k][day] for k in SYMBOLS}}
        (written if put_if_absent(tok, f"1600/{day}.json", body) else skipped).append(day)
    print(json.dumps({"written": written, "already_captured": skipped, "no_1600_bar": missing}), flush=True)


if __name__ == "__main__":
    main()
