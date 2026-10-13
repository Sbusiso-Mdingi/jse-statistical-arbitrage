"""H2: the SBK/NED five-day hold rule, skipping entries on news days (research/PROTOCOL.md).

H2a flags a news day from trading volume, H2b from GDELT article counts. A signal on a
news day for either bank is ignored: it neither opens, restarts nor flips a position.
"""
import csv, json, math, sys
from datetime import date
from bisect import bisect_left, bisect_right
import numpy as np

COST = 10 / 1e4
Q, HOLD, WINDOW = 0.90, 5, 60
PERIODS = {
    "design": ("2010-01-01", "2020-01-01"),
    "validation": ("2020-01-01", "2026-04-01"),
    "post-freeze": ("2026-04-01", "2100-01-01"),
}

# The service's full record: walk-forward history plus post-freeze days filtered live.
sys.path.insert(0, "service")
from app.main import _rows  # noqa: E402

h = _rows("all")
dates = [d.isoformat() for d in h["date"]]
rs = np.expm1(np.array(h["r_sbk"]))
rn = np.expm1(np.array(h["r_ned"]))
hn = np.array(h["h_ns"])
n = len(dates)


def spikes(x, k):
    """x[t] > k * median of the previous WINDOW sessions with data; NaN where unknown."""
    out = np.full(n, np.nan)
    seen: list[float] = []
    for t in range(n):
        if len(seen) >= WINDOW and not np.isnan(x[t]):
            out[t] = float(x[t] > k * np.median(seen[-WINDOW:]))
        if not np.isnan(x[t]):
            seen.append(x[t])
    return out


def volume_news(path):
    vol = {r["date"]: float(r["volume"]) for r in csv.DictReader(open(path)) if r["volume"] not in ("", "None")}
    # Zero volume is a holiday or a missing print, not a quiet day.
    x = np.array([vol.get(d, np.nan) or np.nan for d in dates])
    return spikes(x, 1.5)


def gdelt_news():
    counts = {"sbk": np.zeros(n), "ned": np.zeros(n)}
    for r in csv.DictReader(open("data/raw/gdelt_banks.csv")):
        # Before 15:00 UTC counts towards that day's session, otherwise the next one.
        find = bisect_left if r["before_close"] == "true" else bisect_right
        t = find(dates, r["day"])
        if t >= n:
            continue
        for b in ("sbk", "ned"):
            if r[b] == "true":
                counts[b][t] += int(r["articles"])
    first = bisect_left(dates, "2015-02-18")
    out = {}
    for b, x in counts.items():
        x[:first] = np.nan
        out[b] = spikes(x, 2.0)
    return out, counts


def positions(skip):
    pos = np.zeros(n)
    cur, left = 0.0, 0
    for t in range(n):
        if abs(hn[t] - 0.5) > Q / 2 and not skip[t]:
            cur, left = (1.0 if hn[t] > 0.5 else -1.0), HOLD
        elif left > 0:
            left -= 1
        if left == 0:
            cur = 0.0
        pos[t] = cur
    return pos


def evaluate(pos, start, end):
    # Net returns on the full record, then sliced, so positions carry across period boundaries.
    held_all = np.concatenate([[0.0], pos[:-1]]) * 0.5
    turn_all = np.abs(np.diff(np.concatenate([[0.0], pos])))
    net_all = held_all * (rs - rn) - turn_all * COST
    m = np.array([start <= d < end for d in dates])
    net, p = net_all[m], pos[m]
    eq = np.cumprod(1 + net)
    yrs = len(net) / 252
    sd = net.std(ddof=1)
    prev = np.concatenate([[0.0], pos[:-1]])[m]
    return dict(
        start=dates[np.argmax(m)], end=dates[len(m) - 1 - np.argmax(m[::-1])],
        sharpe=round(net.mean() / sd * math.sqrt(252), 2) if sd > 0 else 0.0,
        cagr=round(eq[-1] ** (1 / yrs) - 1, 4), total=round(eq[-1] - 1, 4),
        mdd=round(float((eq / np.maximum.accumulate(eq) - 1).min()), 4),
        in_market=round(float((p != 0).mean()), 3), entries=int(((p != 0) & (prev != p)).sum()),
    )


if __name__ == "__main__":
    va, vb = volume_news("data/raw/sbk_volume.csv"), volume_news("data/raw/ned_volume.csv")
    news_a = (np.nan_to_num(va) == 1) | (np.nan_to_num(vb) == 1)
    g, counts = gdelt_news()
    news_b = (np.nan_to_num(g["sbk"]) == 1) | (np.nan_to_num(g["ned"]) == 1)
    gdelt_ok = ~np.isnan(g["sbk"]) & ~np.isnan(g["ned"])
    b_start = dates[int(np.argmax(gdelt_ok))]

    base = positions(np.zeros(n, bool))
    rules = {"unfiltered": base, "H2a volume": positions(news_a), "H2b GDELT": positions(news_b)}
    windows = dict(PERIODS, **{"H2b design": (b_start, "2020-01-01")})
    out = {"news_day_share": {}, "results": {}, "h2b_design_start": b_start}
    for name, (s, e) in windows.items():
        m = np.array([s <= d < e for d in dates])
        out["news_day_share"][name] = {"H2a volume": round(float(news_a[m].mean()), 3),
                                       "H2b GDELT": round(float(news_b[m].mean()), 3)}
        out["results"][name] = {k: evaluate(p, s, e) for k, p in rules.items()}
    for name, res in out["results"].items():
        print(f"\n{name}  news-day share {out['news_day_share'][name]}")
        for k, r in res.items():
            print(f"  {k:12s} SR {r['sharpe']:5.2f}  CAGR {r['cagr']*100:5.1f}%  MDD {r['mdd']*100:6.1f}%  entries {r['entries']:3d}  in mkt {r['in_market']*100:3.0f}%  {r['start']} to {r['end']}")
    json.dump(out, open("research/results/h2.json", "w"), indent=1)
