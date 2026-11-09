"""H5 harness: re-filter the H1 signal from the stored monthly fits with edited coefficients.

The analogue of "weight-space programming" (Takehi, Teoh, Zhang and Khattab, 2026) for a
copula-GARCH model: the fitted parameters in data/basket.json are read as text, a flaw is
identified, and the coefficients are edited directly. Nothing is re-estimated. Every
walk-forward month is re-filtered with its own fit, edited, so the record stays out of
sample. Every performance evaluation is appended to research/results/h5_log.json with the
period it used, so the number of looks at the data is on the record.
"""
import csv, json, math, os, sys
from datetime import date, timedelta
import numpy as np

sys.path.insert(0, "service")
from app.model import MarginalState, filter_marginal, h_func  # noqa: E402

BASKET = ["fsr", "abg", "ned", "cpi"]
COST = 10 / 1e4
Q, HOLD = 0.90, 5
PERIODS = {
    "design": ("2010-01-01", "2020-01-01"),
    "validation": ("2020-01-01", "2026-04-01"),
    "post-freeze": ("2026-04-01", "2100-01-01"),
}
LOG = "research/results/h5_log.json"


# ---------- data, as in research/02_basket.R ----------

def _read_px(name):
    rows = []
    for r in csv.DictReader(open(f"data/raw/{name}.csv")):
        try:
            a = float(r["adjusted"])
        except ValueError:
            continue
        if a > 0:
            rows.append((date.fromisoformat(r["date"]), a))
    return _drop_bad_prints(rows)


def _drop_bad_prints(rows, jump=0.4):
    while True:
        p = np.log([a for _, a in rows])
        r = np.diff(p)
        n = len(r)
        lj = math.log(1 + jump)
        bad = np.flatnonzero((np.abs(r[:-1]) > lj) & (np.sign(r[:-1]) != np.sign(r[1:])) & (np.abs(r[:-1] + r[1:]) < lj / 4)) + 1
        if not len(bad):
            return rows
        rows = [x for i, x in enumerate(rows) if i not in set(bad.tolist())]


def load():
    px = {k: dict(_read_px(k)) for k in ["sbk"] + BASKET}
    dates = sorted(set.intersection(*[set(v) for v in px.values()]))
    vix = {}
    for r in csv.DictReader(open("data/raw/vix.csv")):
        try:
            vix[date.fromisoformat(r["date"].strip('"'))] = float(r["vix"])
        except ValueError:
            pass
    vdates = sorted(vix)
    vnum = np.array([d.toordinal() for d in vdates])
    out_d, out_v = [], []
    for d in dates:
        i = np.searchsorted(vnum, d.toordinal() - 1, side="right") - 1
        if i >= 0:
            out_d.append(d)
            out_v.append(vix[vdates[i]] / 100)
    dates = out_d
    px_m = {k: np.array([px[k][d] for d in dates]) for k in px}
    simple = {k: px_m[k][1:] / px_m[k][:-1] - 1 for k in px_m}
    d = {
        "date": dates[1:],
        "vix": np.array(out_v[1:]),
        "simple": simple,
        "r_sbk": np.log1p(simple["sbk"]),
        "r_bsk": np.log1p(np.mean([simple[k] for k in BASKET], axis=0)),
    }
    return d


def month_ends(dates, first=date(2009, 12, 31)):
    m = [x.strftime("%Y-%m") for x in dates]
    ends = [dates[i] for i in range(len(dates) - 1) if m[i] != m[i + 1]]
    return [e for e in ends if e >= first]


# ---------- filtering with (edited) coefficients ----------

def _filter_full(spec, r, vix, n_train):
    """Filter from the first observation, initialising at the training sample's moments."""
    c = spec["coef"]
    s0 = float(np.std(r[:n_train] - c.get("mu", 0.0)))
    state = MarginalState(r=c.get("mu", 0.0), mu=c.get("mu", 0.0), sigma=s0, z=0.0)
    return filter_marginal(spec, state, r, vix)


def edit_spec(spec, edit):
    """Return a copy of a margin spec with coefficients changed by edit(coef) -> coef."""
    s = json.loads(json.dumps(spec))
    s["coef"] = edit(s["coef"])
    return s


def signals(d, fits, edit_sbk=None, edit_bsk=None, edit_cop=None):
    """h for every walk-forward day, each month filtered with its own (edited) fit."""
    dates = d["date"]
    ends = month_ends(dates)
    by_end = {f["train_end"]: f for f in fits}
    n = len(dates)
    out = {"date": [], "u": [], "v": [], "h": [], "mu_sbk": [], "mu_bsk": [], "sig_sbk": [], "sig_bsk": []}
    for k, te in enumerate(ends):
        f = by_end.get(te.isoformat())
        if f is None:
            continue
        n_train = sum(1 for x in dates if x <= te)
        n_all = sum(1 for x in dates if x <= ends[k + 1]) if k + 1 < len(ends) else n
        if n_all <= n_train:
            continue
        sbk = edit_spec(f["sbk"], edit_sbk) if edit_sbk else f["sbk"]
        bsk = edit_spec(f["bsk"], edit_bsk) if edit_bsk else f["bsk"]
        fs = _filter_full(sbk, d["r_sbk"][:n_all], d["vix"][:n_all], n_train)
        fb = _filter_full(bsk, d["r_bsk"][:n_all], d["vix"][:n_all], n_train)
        # A copula edit sees the copula and the training-period PITs under this fit, nothing later.
        cop = edit_cop(dict(f["copula"]), fs["u"][:n_train], fb["u"][:n_train]) if edit_cop else f["copula"]
        sl = slice(n_train, n_all)
        h = h_func(cop["family"], fs["u"][sl], fb["u"][sl], cop["par"], cop.get("par2", 0.0))
        out["date"] += dates[sl]
        out["u"].append(fs["u"][sl]); out["v"].append(fb["u"][sl]); out["h"].append(h)
        out["mu_sbk"].append(fs["mu"][sl]); out["mu_bsk"].append(fb["mu"][sl])
        out["sig_sbk"].append(fs["sigma"][sl]); out["sig_bsk"].append(fb["sigma"][sl])
        out.setdefault("par", []).append(np.full(n_all - n_train, cop["par"]))
    for key in list(out):
        if key not in ("date",):
            out[key] = np.concatenate(out[key])
    idx = {x: i for i, x in enumerate(dates)}
    pos = [idx[x] for x in out["date"]]
    out["rs"] = d["simple"]["sbk"][pos]
    out["rb"] = np.mean([d["simple"][k] for k in BASKET], axis=0)[pos]
    return out


# ---------- the H1 rule and its evaluation, as in research/h1_evaluate.py ----------

def positions(h, q=Q, hold=HOLD):
    pos = np.zeros(len(h))
    cur, left = 0.0, 0
    for t in range(len(h)):
        if abs(h[t] - 0.5) > q / 2:
            cur, left = (1.0 if h[t] > 0.5 else -1.0), hold
        elif left > 0:
            left -= 1
        if left == 0:
            cur = 0.0
        pos[t] = cur
    return pos


def net_returns(pos, rs, rb, cost=COST):
    held = np.concatenate([[0.0], pos[:-1]]) * 0.5
    return held * (rs - rb) - np.abs(np.diff(np.concatenate([[0.0], pos]))) * cost


def stats(net, pos, dates, start, end, prev_pos):
    m = np.array([start <= x.isoformat() < end for x in dates])
    if not m.any():
        return None
    net, p = net[m], pos[m]
    eq = np.cumprod(1 + net)
    yrs = len(net) / 252
    sd = net.std(ddof=1)
    down = math.sqrt(np.mean(np.minimum(net, 0) ** 2))
    return dict(
        start=dates[int(np.argmax(m))].isoformat(), end=dates[len(m) - 1 - int(np.argmax(m[::-1]))].isoformat(),
        sharpe=round(float(net.mean() / sd * math.sqrt(252)), 2) if sd > 0 else 0.0,
        sortino=round(float(net.mean() / down * math.sqrt(252)), 2) if down > 0 else 0.0,
        cagr=round(float(eq[-1] ** (1 / yrs) - 1), 4), total=round(float(eq[-1] - 1), 4),
        mdd=round(float((eq / np.maximum.accumulate(eq) - 1).min()), 4),
        in_market=round(float((p != 0).mean()), 3),
        entries=int(((p != 0) & (prev_pos[m] != p)).sum()),
        days=int(len(net)),
    )


def evaluate(sig, label, periods, note="", q=Q, hold=HOLD, log=True):
    """Performance of the H1 rule on the given signal for the named periods. Logged."""
    pos = positions(sig["h"], q, hold)
    prev = np.concatenate([[0.0], pos[:-1]])
    res = {}
    for name in periods:
        s, e = PERIODS[name]
        res[name] = {
            "after_costs": stats(net_returns(pos, sig["rs"], sig["rb"]), pos, sig["date"], s, e, prev),
            "before_costs": stats(net_returns(pos, sig["rs"], sig["rb"], 0.0), pos, sig["date"], s, e, prev),
            "signal_share": round(float(np.mean([abs(x - 0.5) > q / 2 for x, dd in zip(sig["h"], sig["date"]) if s <= dd.isoformat() < e])), 4),
        }
    if log:
        entries = json.load(open(LOG)) if os.path.exists(LOG) else []
        entries.append({"n": len(entries) + 1, "when": date.today().isoformat(), "label": label, "periods": list(periods), "note": note,
                        "result": {p: {"sharpe": r["after_costs"]["sharpe"], "before_costs_sharpe": r["before_costs"]["sharpe"], "entries": r["after_costs"]["entries"]} for p, r in res.items()}})
        json.dump(entries, open(LOG, "w"), indent=1)
    return res


def paired_t(net_a, net_b):
    """Annualised edge of a over b in bps a year and its paired t-statistic."""
    diff = net_a - net_b
    t = float(diff.mean() / (diff.std(ddof=1) / math.sqrt(len(diff)))) if diff.std(ddof=1) > 0 else 0.0
    return {"bps_per_year": round(float(diff.mean() * 252 * 1e4), 1), "t_stat": round(t, 2)}


def show(res, label):
    for name, r in res.items():
        a, b = r["after_costs"], r["before_costs"]
        print(f"{label:28s} {name:12s} SR {a['sharpe']:6.2f} (gross {b['sharpe']:5.2f})  Sortino {a['sortino']:5.2f}  CAGR {a['cagr']*100:5.1f}%  MDD {a['mdd']*100:6.1f}%  entries {a['entries']:3d}  fires {r['signal_share']*100:4.1f}%")


if __name__ == "__main__":
    # Parity check only: does the harness reproduce data/h1_daily.csv from the stored fits?
    d = load()
    fits = json.load(open("data/basket.json"))["fits"]
    sig = signals(d, fits)
    ref = list(csv.DictReader(open("data/h1_daily.csv")))
    ref_h = {r["date"]: (float(r["u"]), float(r["v"]), float(r["h"])) for r in ref}
    common = [i for i, x in enumerate(sig["date"]) if x.isoformat() in ref_h]
    du = max(abs(sig["u"][i] - ref_h[sig["date"][i].isoformat()][0]) for i in common)
    dv = max(abs(sig["v"][i] - ref_h[sig["date"][i].isoformat()][1]) for i in common)
    dh = max(abs(sig["h"][i] - ref_h[sig["date"][i].isoformat()][2]) for i in common)
    print(f"days: harness {len(sig['date'])}, record {len(ref)}, common {len(common)}")
    print(f"max |du| {du:.2e}  max |dv| {dv:.2e}  max |dh| {dh:.2e}")
    missing = [r['date'] for r in ref if date.fromisoformat(r['date']) not in set(sig['date'])]
    print("record days not in harness:", len(missing), missing[:5])
