"""Sizing, copula as timer / size modifier, window ensemble, drawdown rule, power."""
import sys; sys.path.insert(0, "/tmp/jse-review/design")
from core import *
import pickle
w = pickle.load(open("/tmp/jse-review/design/w126.pkl", "rb"))
eg, z, b = w["eg"], w["z"], w["b"]
gate = eg < -2.8
specs = 0
def Lf(name, trs):
    global specs; specs += 1
    return line(name, trs)
base = sim(z, b, gate)
Lf("BASE", base)

# ---- sizing
k = np.abs(b)
hedged = (-(k / (1 + k)))[:-1] * rs[1:] + (1 / (1 + k))[:-1] * rn[1:]   # return of a long-NED unit set at close t-1
hedged = np.concatenate([[np.nan], hedged])
sig = np.full(n, np.nan)
for t in range(200, n):
    sig[t] = np.nanstd(hedged[t - 59:t + 1])
med = np.full(n, np.nan)
for t in range(200, n):
    med[t] = np.nanmedian(sig[200:t + 1])
size_vol = np.clip(med / sig, 0.5, 2.0)
Lf("vol-scaled size (expanding-median target / 60d spread sd, 0.5-2)", sim(z, b, gate, size=np.nan_to_num(size_vol, nan=1.0)))
Lf("size by |z|/1.5, cap 2", sim(z, b, gate, size=np.clip(np.abs(np.nan_to_num(z)) / 1.5, 1, 2)))
Lf("size by EG strength 1+(-2.8-eg), 0.5-2", sim(z, b, gate, size=np.clip(1 + (-2.8 - np.nan_to_num(eg)), 0.5, 2)))
# per-trade risk: spread sd at entry vs |net|
_, rows, _ = score(base)
td = [t for t in base if t["close"] is not None]
sv = np.array([sig[t["open"]] for t in td]); nv = np.array([r["net"] for r in rows]) * 1e4
print("corr(entry spread vol, |net|)", np.corrcoef(sv, np.abs(nv))[0, 1].round(2), "corr(entry spread vol, net)", np.corrcoef(sv, nv)[0, 1].round(2))

# drawdown brake: after the closed-trade equity is 800 bps below its peak, half size until a new peak
def dd_brake(trs, lim=800):
    out = []; eq = 0; pk = 0
    _, rr, _ = score(trs)
    m = {(r["open"], r["close"]): r["net"] * 1e4 for r in rr}
    for tr in trs:
        f = 0.5 if pk - eq > lim else 1.0
        t2 = dict(tr, w_sbk=tr["w_sbk"] * f, w_ned=tr["w_ned"] * f); out.append(t2)
        if tr["close"] is not None:
            eq += m[(tr["open"], tr["close"])] * f; pk = max(pk, eq)
    return out
Lf("drawdown brake: half size while 800 bps below peak", dd_brake(base))

# ---- copula
h = h_series()
s2010 = [t for t in base if dates[t["open"]] >= dt.date(2010, 1, 1)]
Lf("BASE from 2010 (h available)", s2010)
_, rows10, _ = score(s2010)
td10 = [t for t in s2010 if t["close"] is not None]
agree = np.array([np.sign(t["w_sbk"]) == np.sign(h[t["open"]] - 0.5) for t in td10])
mag = np.array([abs(h[t["open"]] - 0.5) for t in td10])
nv10 = np.array([r["net"] for r in rows10]) * 1e4
print(f"copula at spread entry: agree n={agree.sum()} mean {nv10[agree].mean():.1f}; disagree n={(~agree).sum()} mean {nv10[~agree].mean():.1f}")
fires = mag > 0.45
print(f"copula fires (|h-.5|>.45) at entry: agree&fire n={(agree & fires).sum()} mean {nv10[agree & fires].mean() if (agree & fires).any() else float('nan'):.1f}; "
      f"disagree&fire n={(~agree & fires).sum()}")
side_h = np.sign(h - 0.5)
# z>0 -> w_sbk>0 (long SBK); agreement: sign(z) == sign(h-.5)
ok_agree = (np.sign(np.nan_to_num(z)) == side_h)
s = sim(z, b, gate, enter_ok=ok_agree)
Lf("copula timer: enter only when h agrees (waits while |z|>1.5)", [t for t in s if dates[t["open"]] >= dt.date(2010, 1, 1)])
ok_strong = ok_agree & (np.abs(h - 0.5) > 0.25)
s = sim(z, b, gate, enter_ok=ok_strong)
Lf("copula timer: h agrees and |h-.5|>0.25", [t for t in s if dates[t["open"]] >= dt.date(2010, 1, 1)])
fire_recent = np.zeros(n, bool)
for t in range(5, n):
    fire_recent[t] = np.any((np.abs(h[t - 4:t + 1] - 0.5) > 0.45) & (side_h[t - 4:t + 1] == np.sign(np.nan_to_num(z[t]))))
s = sim(z, b, gate, size=np.where(fire_recent, 1.5, 1.0))
Lf("copula size: 1.5x if copula fired same side in last 5", [t for t in s if dates[t["open"]] >= dt.date(2010, 1, 1)])

# ---- frequency: window ensemble books, 1/3 capital each
books = []
for LL in (110, 126, 140):
    ww = w if LL == 126 else wstats(x, y, LL)
    books += sim(ww["z"], ww["b"], ww["eg"] < -2.8, size=np.full(n, 1 / 3))
r, done, tot = score(books); specs += 1
v = np.array([q["net"] for q in done]) * 1e4
print(f"window ensemble 110/126/140 (1/3 each): sub-trades {len(v)}, mean per sub-trade {v.mean():.1f} bps of 1/3 capital => {3*v.mean():.1f} per full unit, sum {v.sum():.0f}, SR {r['sharpe']}, mdd {r['mdd']}")
br, _, tb = score(base)
print(f"   BASE SR {br['sharpe']} mdd {br['mdd']}; daily corr between 110 and 140 books:", end=" ")
b110 = score(sim(wstats(x, y, 110)["z"], wstats(x, y, 110)["b"], wstats(x, y, 110)["eg"] < -2.8))[2]
b140w = wstats(x, y, 140); b140 = score(sim(b140w["z"], b140w["b"], b140w["eg"] < -2.8))[2]
print(np.corrcoef(b110[dev], b140[dev])[0, 1].round(2), " 126 vs 110:", np.corrcoef(tb[dev], b110[dev])[0, 1].round(2))
# power
sd = 226
for mu in (91, 60, 40):
    nn = ((1.645 + 0.842) * sd / mu) ** 2
    print(f"trades for 80% power at one-sided 5%, true mean {mu}, sd {sd}: {nn:.0f} (~{nn/3.9:.0f} years at 3.9 a year)")
print("SPECS", specs)
