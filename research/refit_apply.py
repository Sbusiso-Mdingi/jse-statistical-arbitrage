"""Set applies_from on refits in data/refits.json that a person is about to deploy (research/PROTOCOL.md, H17).

  python research/refit_apply.py            # run just before deploy/azure.sh

A refit is used from the first weekday after today (Johannesburg time), so no session the dashboard has already
shown changes its signal. Holidays need no care: the service applies a refit from the first session on or after
the date.
"""
import json
import datetime as dt

REFITS = "data/refits.json"
today = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=2)).date()
nxt = today + dt.timedelta(days=1)
while nxt.weekday() >= 5:
    nxt += dt.timedelta(days=1)
book = json.load(open(REFITS))
done = []
for e in book["refits"]:
    if e["applies_from"] is None:
        e["applies_from"] = nxt.isoformat(); done.append(e["train_end"])
json.dump(book, open(REFITS, "w"), indent=1)
print(f"applies from {nxt}: {', '.join(done)}" if done else "nothing to apply")
