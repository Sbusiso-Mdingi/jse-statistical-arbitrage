"""H3: a learned exit for the H1 bank-basket trade (research/PROTOCOL.md).

Entries are H1's. On each close where a position has been held one to four days, H3a (logistic
classifier) or H3b (fitted Q-iteration) decides whether to keep holding over the next session.
Models are refitted at each year end on decision points whose outcome is known by then.
"""
import csv, json, math
from bisect import bisect_left, bisect_right
import numpy as np
from sklearn.linear_model import LogisticRegression, Ridge

COST = 10 / 1e4
Q, HOLD, WINDOW = 0.90, 5, 60
BASKET = ["fsr", "abg", "ned", "cpi"]
NEWS_FROM = "2015-05-13"  # first session with 60 sessions of GDELT history (as in H2b)
PERIODS = {
    "design": ("2017-01-01", "2020-01-01"),
    "validation": ("2020-01-01", "2026-04-01"),
    "post-freeze": ("2026-04-01", "2100-01-01"),
}

rows = list(csv.DictReader(open("data/h1_daily.csv")))
dates = [r["date"] for r in rows]
n = len(dates)
h = np.array([float(r["h"]) for r in rows])
rs = np.array([float(r["sbk"]) for r in rows])
rb = np.array([[float(r[k]) for k in BASKET] for r in rows]).mean(axis=1)
spread = 0.5 * (rs - rb)  # held return of a long-SBK position per unit of capital


# ---- features known at each close ----------------------------------------------------------

def trailing(x, fn):
    """fn over the previous WINDOW sessions with data, excluding today; NaN until there are enough."""
    out = np.full(n, np.nan)
    seen: list[float] = []
    for t in range(n):
        if len(seen) >= WINDOW:
            out[t] = fn(seen[-WINDOW:])
        if not np.isnan(x[t]):
            seen.append(x[t])
    return out


def gdelt(path, names):
    counts = {b: np.zeros(n) for b in names}
    tone_sum = {b: np.zeros(n) for b in names}
    for r in csv.DictReader(open(path)):
        # Before 15:00 UTC counts towards that day's session, otherwise the next one.
        t = (bisect_left if r["before_close"] == "true" else bisect_right)(dates, r["day"])
        if t >= n:
            continue
        a, tone = int(r["articles"]), float(r["tone"] or 0)
        for b in names:
            if r[b] == "true":
                counts[b][t] += a
                tone_sum[b][t] += a * tone
    return counts, tone_sum


c1, s1 = gdelt("data/raw/gdelt_banks.csv", ["sbk", "ned"])
c2, s2 = gdelt("data/raw/gdelt_basket.csv", ["fsr", "abg", "cpi"])
first = bisect_left(dates, "2015-02-18")
cnt_sbk = c1["sbk"].copy()
cnt_bsk = c1["ned"] + c2["fsr"] + c2["abg"] + c2["cpi"]
ton_bsk_sum = s1["ned"] + s2["fsr"] + s2["abg"] + s2["cpi"]


def news_level(c):
    x = c.copy()
    x[:first] = np.nan
    return np.log((1 + x) / (1 + trailing(x, np.median)))


def tone_dev(c, s):
    tone = np.where(c > 0, s / np.maximum(c, 1), np.nan)
    tone[:first] = np.nan
    dev = tone - trailing(tone, np.mean)
    return np.where(c > 0, dev, 0.0)


news_sbk, news_bsk = news_level(cnt_sbk), news_level(cnt_bsk)
tone_rel = tone_dev(cnt_sbk, s1["sbk"]) - tone_dev(cnt_bsk, ton_bsk_sum)


def volume(name):
    vol = {r["date"]: float(r["volume"]) for r in csv.DictReader(open(f"data/raw/{name}_volume.csv"))
           if r["volume"] not in ("", "None") and float(r["volume"]) > 0}
    x = np.array([vol.get(d, np.nan) for d in dates])
    return np.log(x / trailing(x, np.median))


vol_sbk = volume("sbk")
vol_bsk = np.nanmean(np.vstack([volume(b) for b in BASKET]), axis=0)
vol_sbk = np.nan_to_num(vol_sbk)  # missing print: treat as an ordinary day
vol_bsk = np.nan_to_num(vol_bsk)

vix_rows = [(r["date"], float(r["vix"])) for r in csv.DictReader(open("data/raw/vix.csv")) if r["vix"] not in ("", "NA")]
vix_d = [d for d, _ in vix_rows]
vix = np.array([vix_rows[max(bisect_left(vix_d, d) - 1, 0)][1] for d in dates])  # last US close before the day
rv = np.array([np.std(rs[max(0, t - 19):t + 1] - rb[max(0, t - 19):t + 1]) for t in range(n)])

# ---- H1 trades and decision points ---------------------------------------------------------

signal = np.abs(h - 0.5) > Q / 2
side = np.where(h > 0.5, 1.0, -1.0)
start = np.full(n, -1)  # latest signal day still within its hold, for every day
s = -10**9
for t in range(n):
    if signal[t]:
        s = t
    if t - s < HOLD:
        start[t] = s
decision = np.array([start[t] >= 0 and 1 <= t - start[t] <= HOLD - 1 and t + 1 < n for t in range(n)])

NEWS = ["news_sbk", "news_bsk", "tone_rel", "vol_sbk", "vol_bsk"]
NAMES = ["days_held", "signal_now", "signal_entry", "pnl", "today", "rv20", "vix"] + NEWS


def features(t):
    s0 = start[t]
    d = side[s0]
    return {
        "days_held": t - s0,
        "signal_now": d * (h[t] - 0.5),
        "signal_entry": abs(h[s0] - 0.5),
        "pnl": d * spread[s0 + 1:t + 1].sum(),
        "today": d * spread[t],
        "rv20": rv[t],
        "vix": vix[t],
        "news_sbk": news_sbk[t],
        "news_bsk": news_bsk[t],
        "tone_rel": d * tone_rel[t],
        "vol_sbk": vol_sbk[t],
        "vol_bsk": vol_bsk[t],
    }


pts = [t for t in range(n) if decision[t] and dates[t] >= NEWS_FROM]
X_all = np.array([[features(t)[k] for k in NAMES] for t in pts])
assert not np.isnan(X_all).any(), "missing feature"
reward = np.array([side[start[t]] * spread[t + 1] for t in pts])  # held return if we keep holding
idx = {t: i for i, t in enumerate(pts)}
nxt = np.array([idx.get(t + 1, -1) if decision[t + 1] and start[t + 1] == start[t] else -1 for t in pts])
pt_dates = [dates[t] for t in pts]
out_dates = [dates[t + 1] for t in pts]


def fit_predict(kind, reg, cols, train, test):
    X = X_all[:, cols]
    mu, sd = X[train].mean(0), X[train].std(0) + 1e-12
    Z = (X - mu) / sd
    if kind == "logit":
        m = LogisticRegression(C=reg, max_iter=2000).fit(Z[train], reward[train] > 0)
        return m.predict_proba(Z[test])[:, 1] >= 0.5
    # Fitted Q-iteration: value of holding = next return + max(0, value at the next decision).
    q = np.zeros(len(pts))
    for _ in range(HOLD - 1):
        cont = np.where(nxt >= 0, np.maximum(0.0, q[np.maximum(nxt, 0)]), 0.0)
        m = Ridge(alpha=reg).fit(Z[train], (reward + cont)[train] * 1e4)
        q = m.predict(Z) / 1e4
    return q[test] >= 0


def walk_forward(kind, reg, cols):
    hold = np.ones(len(pts), dtype=bool)
    years = sorted({d[:4] for d in pt_dates})
    for y in years:
        if int(y) < 2017:
            continue
        cut = f"{int(y) - 1}-12-31"
        train = np.array([o <= cut for o in out_dates])
        test = np.array([d[:4] == y for d in pt_dates])
        if test.any():
            hold[test] = fit_predict(kind, reg, cols, train, test)
    return hold


def positions(hold=None):
    pos = np.zeros(n)
    exited = False
    for t in range(n):
        if signal[t]:
            exited = False
        elif t in idx and hold is not None and not hold[idx[t]]:
            exited = True
        pos[t] = side[start[t]] if start[t] >= 0 and not exited else 0.0
    return pos


def evaluate(pos, a, b):
    held = np.concatenate([[0.0], pos[:-1]])
    net_all = held * spread - np.abs(np.diff(np.concatenate([[0.0], pos]))) * COST
    m = np.array([a <= d < b for d in dates])
    net, p = net_all[m], pos[m]
    eq = np.cumprod(1 + net)
    sd = net.std(ddof=1)
    return dict(
        start=dates[int(np.argmax(m))], end=dates[n - 1 - int(np.argmax(m[::-1]))],
        sharpe=round(net.mean() / sd * math.sqrt(252), 2),
        sortino=round(net.mean() / math.sqrt(np.mean(np.minimum(net, 0) ** 2)) * math.sqrt(252), 2),
        cagr=round(eq[-1] ** (252 / len(net)) - 1, 4),
        mdd=round(float((eq / np.maximum.accumulate(eq) - 1).min()), 4),
        in_market=round(float((p != 0).mean()), 3),
    )


def report(pos, hold=None):
    out = {k: evaluate(pos, a, b) for k, (a, b) in PERIODS.items()}
    if hold is not None:
        for k, (a, b) in PERIODS.items():
            m = np.array([a <= d < b for d in pt_dates])
            out[k]["exit_share"] = round(float((~hold[m]).mean()), 3) if m.any() else None
    return out


base = positions()
assert np.array_equal(base != 0, np.array([start[t] >= 0 for t in range(n)]))
results = {"h1": report(base), "decision_points": len(pts), "features": NAMES}
all_cols = list(range(len(NAMES)))
no_news = [i for i, k in enumerate(NAMES) if k not in NEWS]
for name, kind, grid in [("h3a", "logit", [0.01, 0.1, 1]), ("h3b", "fqi", [1, 10, 100])]:
    # Regularisation chosen once, by design-period Sharpe only.
    design = {reg: evaluate(positions(walk_forward(kind, reg, all_cols)), *PERIODS["design"])["sharpe"] for reg in grid}
    reg = max(grid, key=lambda r: design[r])
    hold = walk_forward(kind, reg, all_cols)
    results[name] = {"reg": reg, "design_grid": design, **report(positions(hold), hold)}
    results[name]["passed"] = bool(results[name]["validation"]["sharpe"] > max(0.0, 0.06))
    if kind == "logit":
        hold_nn = walk_forward(kind, reg, no_news)
        results["h3a_no_news"] = {"reg": reg, **report(positions(hold_nn), hold_nn)}

json.dump(results, open("research/results/h3.json", "w"), indent=1)
print(json.dumps(results, indent=1))


def net_returns(pos):
    held = np.concatenate([[0.0], pos[:-1]])
    return held * spread - np.abs(np.diff(np.concatenate([[0.0], pos]))) * COST


# How far each model's validation edge over H1 is from noise: paired daily differences.
mval = np.array([PERIODS["validation"][0] <= d < PERIODS["validation"][1] for d in dates])
for name, kind in [("h3a", "logit"), ("h3b", "fqi")]:
    diff = (net_returns(positions(walk_forward(kind, results[name]["reg"], all_cols))) - net_returns(base))[mval]
    results[name]["vs_h1_validation"] = {
        "bps_per_year": round(float(diff.mean() * 252 * 1e4), 1),
        "t_stat": round(float(diff.mean() / (diff.std(ddof=1) / math.sqrt(len(diff)))), 2),
    }
json.dump(results, open("research/results/h3.json", "w"), indent=1)
print({k: results[k]["vs_h1_validation"] for k in ("h3a", "h3b")})
