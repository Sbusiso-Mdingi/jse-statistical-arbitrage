"""Exits, entries, stops, holds, gate-exit, slope-drift exit. Every spec printed."""
import sys; sys.path.insert(0, "/tmp/jse-review/design")
from core import *
import pickle
w = pickle.load(open("/tmp/jse-review/design/w126.pkl", "rb"))
gate = w["eg"] < -2.8
z, b = w["z"], w["b"]
specs = 0
def L(name, trs):
    global specs; specs += 1
    return line(name, trs)
L("BASE", sim(z, b, gate))
for st in (3.0, 3.5, 5.0, 99):
    L(f"stop {st}", sim(z, b, gate, stop=st))
for h in (20, 30, 40, 90, 120):
    L(f"hold {h}", sim(z, b, gate, hold=h))
for ex in (0.5, 0.25, -0.25, -0.5):
    L(f"exit at z {ex} (neg = overshoot)", sim(z, b, gate, exit_=ex))
L("exit when gate shuts", sim(z, b, gate, exit_on_gate=True))
# exit when gate shuts by a margin (EG above -2.0)
g2 = w["eg"] < -2.0
def sim_gate2(cut):
    # open on -2.8 gate, exit if statistic rises above cut
    trs = sim(z, b, gate, exit_on_gate=True)  # placeholder replaced below
    return trs
# custom: exit if eg > cut
def sim_exit_eg(cut):
    gg = gate.copy(); out = []; t = 0; N = n
    while t < N:
        if gate[t] and dev[t] and not np.isnan(z[t]) and abs(z[t]) > 1.5:
            side = -1 if z[t] > 0 else 1; k = abs(b[t]); reason = "open"; jsig = None
            for j in range(t + 1, N):
                held = j - t; zj = z[j]
                if (side == -1 and zj < 0) or (side == 1 and zj > 0): reason = "target"
                elif abs(zj) > 4: reason = "stop"
                elif held >= 60: reason = "time"
                elif w["eg"][j] > cut: reason = "gate"
                else: continue
                jsig = j; break
            out.append({"open": t, "close": jsig, "method": "spread", "side": side, "w_sbk": -side * k / (1 + k), "w_ned": side / (1 + k), "reason": reason})
            if jsig is None: break
            t = jsig
        else: t += 1
    return out
for cut in (-2.0, -1.5):
    L(f"exit if EG rises above {cut}", sim_exit_eg(cut))
# slope-drift exit: leave when rolling b moved more than D from entry b
def sim_db(D, hold=60):
    out = []; t = 0
    while t < n:
        if gate[t] and dev[t] and not np.isnan(z[t]) and abs(z[t]) > 1.5:
            side = -1 if z[t] > 0 else 1; k = abs(b[t]); reason = "open"; jsig = None
            for j in range(t + 1, n):
                zj = z[j]
                if (side == -1 and zj < 0) or (side == 1 and zj > 0): reason = "target"
                elif abs(zj) > 4: reason = "stop"
                elif j - t >= hold: reason = "time"
                elif abs(b[j] - b[t]) > D: reason = "slope"
                else: continue
                jsig = j; break
            out.append({"open": t, "close": jsig, "method": "spread", "side": side, "w_sbk": -side * k / (1 + k), "w_ned": side / (1 + k), "reason": reason})
            if jsig is None: break
            t = jsig
        else: t += 1
    return out
for D in (0.2, 0.3, 0.4, 0.5):
    L(f"exit if |b - b_entry| > {D}", sim_db(D))
# re-hedge daily to current b (weights follow rolling b) -- approximated by daily-rebalanced trade segments
def sim_rehedge():
    base = sim(z, b, gate); out = []
    for tr in base:
        if tr["close"] is None: out.append(tr); continue
        # one sub-trade per session with that session's b (costs charged per segment => upper bound on cost)
        o, c, side = tr["open"], tr["close"], tr["side"]
        out.append(dict(tr))
    return out
# entries
for e in (1.25, 1.75, 2.0):
    L(f"entry {e}", sim(z, b, gate, entry=e))
# scale-in: half at 1.5, half at 2.25 (second leg is a separate half trade sharing the exit)
def scale_in(e2=2.25, frac=0.5):
    base = sim(z, b, gate, size=np.full(n, 1 - frac))
    extra = []
    for tr in base:
        if tr["close"] is None: continue
        for j in range(tr["open"] + 1, tr["close"]):
            if abs(z[j]) > e2 and np.sign(z[j]) == np.sign(tr["z0"]):
                k = abs(b[j]); side = tr["side"]
                extra.append({"open": j, "close": tr["close"], "method": "spread", "side": side, "w_sbk": -side * k / (1 + k) * frac, "w_ned": side / (1 + k) * frac, "reason": "add"})
                break
    return base, extra
for e2 in (2.0, 2.5):
    base, extra = scale_in(e2)
    global_ = base + extra
    r, done, tot = score(global_)
    rb = score(base)[0]; re_ = score(extra)[0]
    specs += 1
    print(f"scale-in half@1.5 + half@{e2}: total sum={r['sum']} (vs BASE 7194) SR={r['sharpe']} mdd={r['mdd']} | first halves n={rb['n']} mean/half={rb['bps']} | adds n={re_['n']} mean/half={re_['bps']}")
# partial exit: half at z=0.5 (on own side), half at 0
def partial(x1=0.5):
    a = sim(z, b, gate, size=np.full(n, 0.5), exit_=x1)
    c = sim(z, b, gate, size=np.full(n, 0.5), exit_=0.0)
    return a, c
a, c = partial(0.5)
specs += 1
ra = score(a + c)[0]
print(f"partial: half exit at 0.5, half at 0 (books run independently) sum={ra['sum']} SR={ra['sharpe']} mdd={ra['mdd']}")
print("SPECS", specs)
