"""How much of the edge is the signal close itself? Fill timing on the hourly bars (to 2026-03-31 only)."""
import sys; sys.path.insert(0, "/tmp/jse-review/design")
from core import *
import pickle, collections
w = pickle.load(open("/tmp/jse-review/design/w126.pkl", "rb"))
gate = w["eg"] < -2.8

def raw(name):
    o = {}
    for r in csv.DictReader(open(f"data/raw/{name}.csv")):
        try: o[dt.date.fromisoformat(r["date"])] = float(r["close"])
        except ValueError: pass
    return o

def bars(name):
    b = collections.defaultdict(dict)
    for r in csv.DictReader(open(f"data/raw/{name}_60m.csv")):
        t = dt.datetime.utcfromtimestamp(int(r["time"]))
        if t.date() <= END: b[t.date()][t.hour] = float(r["close"])
    return b

def at_bar(name, logp, hour):
    """adjusted log price at the close of the bar opening `hour` UTC, anchored on that day's close."""
    rw, bb = raw(name), bars(name)
    out = np.full(n, np.nan)
    for i, t in enumerate(dates):
        if t in rw and hour in bb.get(t, {}):
            out[i] = logp[i] - math.log(rw[t] / bb[t][hour])
    return out

x16, y16 = at_bar("sbk", x, 13), at_bar("ned", y, 13)
x10, y10 = at_bar("sbk", x, 7), at_bar("ned", y, 7)
ok16 = ~np.isnan(x16) & ~np.isnan(y16)
print("sessions with 16:00 bars", ok16.sum(), "first", dates[int(np.argmax(ok16))])
# sanity: 16:00-to-close move size
m = ok16
print("sd of log(close/16:00) spread y-x (bps)", np.nanstd((y - y16) - (x - x16)) * 1e4)

# 16:00 statistics: the window to t-1 closes plus today's 16:00 price
L = 126
b16 = np.full(n, np.nan); z16 = np.full(n, np.nan); eg16 = np.full(n, np.nan)
for t in range(L, n):
    if not ok16[t]: continue
    xi = np.append(x[t - L + 1:t], x16[t]); yi = np.append(y[t - L + 1:t], y16[t])
    b16[t], z16[t], eg16[t] = sw.window_stats(xi, yi)
start = dt.date(2009, 6, 1)
sub = np.array([t >= start for t in dates])

def restrict(trs):
    return [tr for tr in trs if dates[tr["open"]] >= start]

base = restrict(sim(w["z"], w["b"], gate))
line("A close signal, close fill (from 2009-06)", base)
# B: 16:00 signal for entry and exit, fill at close of that day
g16 = eg16 < -2.8
zz = np.where(ok16, z16, np.nan)
B = restrict(sim(zz, b16, g16))
line("B 16:00 signal (z, b, gate), close fill", B)
# B2: 16:00 entry signal, exit on the closing z (exit after the close, at the next close is lag) -> exits at 16:00 too is B.
# C: close signal, fill at next session's 10:00 bar (entry and exit): adjust gross
def adjust(trs, fill_x, fill_y, mode):
    """mode: 'entry', 'exit' or 'both'. Replaces the fill at close o (or c) by the price at fill_* on the next session."""
    out = []
    for tr in trs:
        o, c = tr["open"], tr["close"]
        if c is None or c + 1 >= n: continue
        adj = 0.0
        if mode in ("entry", "both"):
            if np.isnan(fill_x[o + 1]) or np.isnan(fill_y[o + 1]): continue
            # position earns from fill price at o+1 instead of close o: lose the move close o -> fill o+1
            adj -= tr["w_sbk"] * (fill_x[o + 1] - x[o]) + tr["w_ned"] * (fill_y[o + 1] - y[o])
        if mode in ("exit", "both"):
            if np.isnan(fill_x[c + 1]) or np.isnan(fill_y[c + 1]): continue
            adj += tr["w_sbk"] * (fill_x[c + 1] - x[c]) + tr["w_ned"] * (fill_y[c + 1] - y[c])
        out.append((tr, adj))
    return out

_, rows, _ = score(base)
key = {(r["open"], r["close"]): r for r in rows}
for lbl, fx, fy in (("next 10:00 bar", x10, y10), ("next close", x, y)):
    for mode in ("entry", "exit", "both"):
        if lbl == "next close":
            fx_, fy_ = x, y  # fill_x[o+1] = x[o+1]
        else:
            fx_, fy_ = fx, fy
        v = []
        for tr, adj in adjust(base, fx_, fy_, mode):
            r = key[(tr["open"], tr["close"])]
            v.append((r["net"] + adj) * 1e4)   # log-approx adjustment; costs unchanged
        v = np.array(v)
        print(f"C fill at {lbl:15s} on {mode:5s}: n={len(v)} fut={v.mean():.1f} t={v.mean() / v.std(ddof=1) * math.sqrt(len(v)):.2f}")
# day-1 decomposition: overnight vs intraday of first held session
o1, i1 = [], []
for tr in base:
    o = tr["open"]
    if o + 1 < n and not np.isnan(x10[o + 1]):
        on = tr["w_sbk"] * (x10[o + 1] - x[o]) + tr["w_ned"] * (y10[o + 1] - y[o])
        rest = tr["w_sbk"] * (x[o + 1] - x10[o + 1]) + tr["w_ned"] * (y[o + 1] - y10[o + 1])
        o1.append(on * 1e4); i1.append(rest * 1e4)
print(f"first held session: close->10:00 {np.mean(o1):.1f} bps (se {np.std(o1)/math.sqrt(len(o1)):.1f}), 10:00->close {np.mean(i1):.1f} (se {np.std(i1)/math.sqrt(len(i1)):.1f}), n={len(o1)}")
# signal-close last-hour move: how much of entry z came in the auction / last 60 min
za = [(tr["z0"], z16[tr["sig"]]) for tr in base if not np.isnan(z16[tr["sig"]])]
print("entries whose 16:00 z was already past 1.5 on the same side:", sum(1 for a, b_ in za if abs(b_) > 1.5 and np.sign(a) == np.sign(b_)), "of", len(za))
pickle.dump({"x16": x16, "y16": y16, "x10": x10, "y10": y10, "z16": z16, "b16": b16, "eg16": eg16}, open("/tmp/jse-review/design/intraday.pkl", "wb"))
