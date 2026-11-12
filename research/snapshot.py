"""A dated copy of the data the frozen rules read, so their scores can be reproduced whatever Yahoo does later.

  python research/snapshot.py

Copies data/raw/{sbk,ned,vix,h15_div}.csv and the service's live fetch (Yahoo adjusted closes and VIX from the
freeze) to data/snapshots/<date>/. The copies are third-party data, so they stay local (gitignored); keep a second
copy off the Mac. data/snapshot_manifest.json (committed) records each file's SHA-256, rows and last date.
"""
import csv, datetime as dt, hashlib, json, os, shutil, sys

sys.path.insert(0, "service")
from app.data import fetch_live  # noqa: E402

FREEZE = dt.date.fromisoformat(json.load(open("data/walkforward.json"))["freeze"])
FILES = ["sbk.csv", "ned.csv", "vix.csv", "h15_div.csv"]


def main():
    day = dt.date.today().isoformat()
    out = f"data/snapshots/{day}"
    os.makedirs(out, exist_ok=False)
    for f in FILES:
        shutil.copy2(f"data/raw/{f}", f"{out}/{f}")
    live = fetch_live(FREEZE)
    json.dump({"freeze": FREEZE.isoformat(), "as_of": live["as_of"].isoformat(), "fetched": dt.datetime.now(dt.timezone.utc).isoformat(),
               "rows": [{**r, "date": r["date"].isoformat()} for r in live["rows"]]}, open(f"{out}/live_fetch.json", "w"), indent=1)
    entry = {"date": day, "folder": out, "files": {}}
    for f in FILES + ["live_fetch.json"]:
        p = f"{out}/{f}"
        h = hashlib.sha256(open(p, "rb").read()).hexdigest()
        info = {"sha256": h}
        if f.endswith(".csv"):
            rows = list(csv.reader(open(p)))[1:]
            info.update(rows=len(rows), last=rows[-1][0].strip('"'))
        else:
            info.update(rows=len(json.load(open(p))["rows"]), last=live["as_of"].isoformat())
        entry["files"][f] = info
    man = json.load(open("data/snapshot_manifest.json")) if os.path.exists("data/snapshot_manifest.json") else {"snapshots": []}
    man["snapshots"].append(entry)
    json.dump(man, open("data/snapshot_manifest.json", "w"), indent=1)
    print(json.dumps(entry, indent=1))


if __name__ == "__main__":
    main()
