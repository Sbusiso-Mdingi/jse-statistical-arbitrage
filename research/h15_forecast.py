"""H15 (research/PROTOCOL.md): will the gap close from here? Step (a), forecast skill on development data.

  python research/h15_forecast.py      # needs data/raw/h15_*.csv from research/h15_data.py

Label, baseline, features, purged folds and the test are as registered. Writes research/results/h15.json,
h15_daily.csv (label, inputs and out-of-fold probabilities by date) and h15_events.csv (the event windows).
"""
import csv, json, math, sys
import datetime as dt
from collections import defaultdict
import numpy as np
from scipy.optimize import minimize
from sklearn.linear_model import LogisticRegression

sys.path.insert(0, "research"); sys.path.insert(0, "research/models"); sys.path.insert(0, "service")
from pairdata import load_pair  # noqa: E402
from app import switch as sw  # noqa: E402

N, ENTRY, STOP = 60, 1.5, 4.0
DEV_END = dt.date(2026, 3, 31)
START = dt.date(2006, 1, 3)
NEWS_START = dt.date(2015, 4, 1)
FOLDS, LAGS = 5, 60
LAM = 1 - 1 / sw.L


# ---------------------------------------------------------------- label and the 126-session window
def window(x, y):
    n = len(x)
    a = np.full(n, np.nan); b = np.full(n, np.nan); s = np.full(n, np.nan); z = np.full(n, np.nan); eg = np.full(n, np.nan)
    for t in range(sw.L - 1, n):
        xi, yi = x[t - sw.L + 1:t + 1], y[t - sw.L + 1:t + 1]
        b[t], z[t], eg[t] = sw.window_stats(xi, yi)
        a[t] = yi.mean() - b[t] * xi.mean()
        u = yi - a[t] - b[t] * xi
        s[t] = math.sqrt(u @ u / (len(u) - 2))
    return a, b, s, z, eg


def labels(x, y, a, b, s, z):
    """Y_t: the frozen gap reaches zero from z_t's side within N sessions before |gap| > 4. NaN if unresolved."""
    n = len(x)
    out = np.full(n, np.nan); days = np.full(n, np.nan)
    for t in range(n):
        if np.isnan(z[t]) or abs(z[t]) <= ENTRY:
            continue
        hit = None
        for k in range(1, N + 1):
            if t + k >= n:
                break
            g = (y[t + k] - a[t] - b[t] * x[t + k]) / s[t]
            if g * z[t] <= 0:
                hit = 1; break
            if abs(g) > STOP:
                hit = 0; break
        if hit is None and t + N < n:
            hit, k = 0, N
        if hit is not None:
            out[t] = hit; days[t] = k
    return out, days


# ---------------------------------------------------------------- baseline: RLS hedge ratio, Markov-switching spread
def rls(x, y):
    n = len(x)
    X0 = np.column_stack([np.ones(sw.L), x[:sw.L]])
    th = np.linalg.lstsq(X0, y[:sw.L], rcond=None)[0]
    P = np.linalg.inv(X0.T @ X0)
    e = np.full(n, np.nan); bb = np.full(n, np.nan)
    for t in range(sw.L, n):
        h = np.array([1.0, x[t]])
        k = P @ h / (LAM + h @ P @ h)
        th = th + k * (y[t] - h @ th)
        P = (P - np.outer(k, h @ P)) / LAM
        e[t] = y[t] - h @ th; bb[t] = th[1]
    return e, bb


def unpack(p):
    return math.tanh(p[0]), math.exp(p[1]), math.exp(p[2]), 1 / (1 + math.exp(-p[3])), 1 / (1 + math.exp(-p[4]))


def hamilton(p, e, use=None):
    """Filtered P(reverting | data to t) and the log likelihood summed over `use` (bool mask)."""
    phi, sr, sw_, p11, p22 = unpack(p)
    n = len(e)
    filt = np.full(n, np.nan)
    pr = (1 - p22) / (2 - p11 - p22)  # stationary start
    ll = 0.0
    c = -0.5 * math.log(2 * math.pi)
    for t in range(1, n):
        if np.isnan(e[t - 1]):
            continue
        pred = p11 * pr + (1 - p22) * (1 - pr)
        dR = e[t] - phi * e[t - 1]; dW = e[t] - e[t - 1]
        fR = math.exp(c - math.log(sr) - 0.5 * (dR / sr) ** 2)
        fW = math.exp(c - math.log(sw_) - 0.5 * (dW / sw_) ** 2)
        lik = pred * fR + (1 - pred) * fW
        if lik <= 0:
            lik = 1e-300
        pr = pred * fR / lik
        filt[t] = pr
        if use is None or use[t]:
            ll += math.log(lik)
    return filt, ll


def fit_ms(e, use):
    de = np.diff(e[~np.isnan(e)])
    x0 = [math.atanh(0.9), math.log(de.std() * 0.8), math.log(de.std() * 1.2), 3.0, 3.0]
    res = minimize(lambda p: -hamilton(p, e, use)[1], x0, method="Nelder-Mead", options={"maxiter": 1500, "xatol": 1e-4, "fatol": 1e-3})
    return res.x


# ---------------------------------------------------------------- external inputs
def read_csv_series(path, key, col):
    out = {}
    for r in csv.DictReader(open(path)):
        if r[col]:
            out[dt.date.fromisoformat(r[key])] = float(r[col])
    return out


def last_before(series, dates, strict=True):
    """Value of a dated series on the latest date before (strictly) each date, NaN if none."""
    ks = sorted(series); kn = np.array([k.toordinal() for k in ks]); vals = np.array([series[k] for k in ks])
    out = np.full(len(dates), np.nan)
    for i, d in enumerate(dates):
        j = np.searchsorted(kn, d.toordinal(), side="left" if strict else "right") - 1
        if j >= 0:
            out[i] = vals[j]
    return out


def features(dates):
    n = len(dates)
    f = {}
    px = "data/raw/h15_px.csv"
    zar = last_before(read_csv_series(px, "date", "usdzar"), dates)  # FX closes after the JSE: use the day before
    afr = []
    for k in ("usdngn", "usdkes", "usdghs"):
        afr.append(np.log(zar / last_before(read_csv_series(px, "date", k), dates)))  # rand per unit of the currency
    dlog = np.nanmean(np.column_stack([np.diff(a, prepend=np.nan) for a in afr]), axis=1)
    f["africa"] = np.array([abs(np.nansum(dlog[t - 19:t + 1])) if t >= 20 else np.nan for t in range(n)])
    dz = np.diff(np.log(zar), prepend=np.nan)
    f["zar_vol"] = np.array([np.nanstd(dz[t - 19:t + 1], ddof=1) if t >= 20 else np.nan for t in range(n)])
    # Results ahead: business days to the next 1 March or 1 August over 60, capped at 1, zero in March and August.
    ra = np.zeros(n)
    for i, d in enumerate(dates):
        if d.month in (3, 8):
            continue
        nxt = min(_next_month_start(d, m) for m in (3, 8))
        ra[i] = min(np.busday_count(d, nxt) / N, 1.0)
    f["results_ahead"] = ra
    # Dividend gap.
    divs = defaultdict(list)
    for r in csv.DictReader(open("data/raw/h15_div.csv")):
        divs[r["bank"]].append((dt.date.fromisoformat(r["ex_date"]), float(r["amount"])))
    growth = {}
    for bank, ev in divs.items():
        ev.sort()
        g = {}
        for j, (d, amt) in enumerate(ev):
            prior = [(dd, aa) for dd, aa in ev[:j] if 300 <= (d - dd).days <= 430]
            if not prior and j > 0:
                prior = [ev[j - 1]]  # a skipped dividend: compare with the one before
            if prior:
                g[d] = math.log(amt / prior[-1][1])
        growth[bank] = g
    f["div_gap"] = np.abs(last_before(growth["sbk"], dates, strict=False) - last_before(growth["ned"], dates, strict=False))
    # Rate cycle: month m usable from the first day of m + 2.
    rate = {}
    for r in csv.DictReader(open("data/raw/h15_rate.csv")):
        m = dt.date.fromisoformat(r["observation_date"])
        rate[m] = float(r["IRSTCI01ZAM156N"])
    chg = {}
    for m, v in rate.items():
        m6 = _add_months(m, -6)
        if m6 in rate:
            chg[_add_months(m, 2)] = v - rate[m6]
    f["rate_6m"] = last_before(chg, dates, strict=False)
    # News imbalance from the GDELT counts (development only).
    sb, nb = defaultdict(float), defaultdict(float)
    for r in csv.DictReader(open("data/raw/gdelt_banks.csv")):
        d = dt.date.fromisoformat(r["day"])
        usable = d if r["before_close"] == "true" else d + dt.timedelta(days=1)  # after-close news counts from the next day
        if r["sbk"] == "true" and r["ned"] == "false":
            sb[usable] += float(r["articles"])
        elif r["ned"] == "true" and r["sbk"] == "false":
            nb[usable] += float(r["articles"])
    news = np.full(n, np.nan)
    gstart = dt.date(2015, 2, 18)
    for t in range(20, n):
        lo, hi = dates[t - 20], dates[t]
        if lo < gstart:
            continue
        s_ = sum(v for d, v in sb.items() if lo < d <= hi); n_ = sum(v for d, v in nb.items() if lo < d <= hi)
        news[t] = abs(math.log1p(s_) - math.log1p(n_))
    f["news"] = news
    return f


def _next_month_start(d, m):
    y = d.year if d.month < m else d.year + 1
    return dt.date(y, m, 1)


def _add_months(d, k):
    y, m = divmod(d.month - 1 + k, 12)
    return dt.date(d.year + y, m + 1, 1)


# ---------------------------------------------------------------- scoring
def logscore(p, y):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return y * np.log(p) + (1 - y) * np.log(1 - p)


def nw_t(d, lags=LAGS):
    d = np.asarray(d, float); n = len(d); m = d.mean(); u = d - m
    v = u @ u / n
    for k in range(1, min(lags, n - 1) + 1):
        v += 2 * (1 - k / (lags + 1)) * (u[k:] @ u[:-k]) / n
    se = math.sqrt(v / n)
    return float(m), float(se), float(m / se) if se > 0 else None


def compare(a, b, y):
    """Model a against model b on the same event closes: mean log-score gain, Newey-West t, Brier both."""
    d = logscore(a, y) - logscore(b, y)
    m, se, t = nw_t(d)
    return {"mean_gain": round(m, 5), "se": round(se, 5), "t": round(t, 2) if t is not None else None, "events": int(len(y))}


def summary(p, y):
    return {"log_score": round(float(logscore(p, y).mean()), 4), "brier": round(float(((p - y) ** 2).mean()), 4), "events": int(len(y))}


SPECS = {
    "Z": ["absz"],
    "G": ["absz", "eg"],
    "M": ["absz", "p_rev"],
    "X": ["absz", "p_rev", "africa", "results_ahead", "div_gap", "zar_vol", "rate_6m"],
    "XN": ["absz", "p_rev", "africa", "results_ahead", "div_gap", "zar_vol", "rate_6m", "news"],
    "M_news_sample": ["absz", "p_rev"],
}


def main():
    d = load_pair()
    dates = d["date"]; n = len(dates)
    x, y = np.cumsum(d["r_sbk"]), np.cumsum(d["r_ned"])
    a, b, s, z, eg = window(x, y)
    lab, days = labels(x, y, a, b, s, z)
    e, b_rls = rls(x, y)
    feat = features(dates)
    feat["absz"] = np.abs(z); feat["eg"] = eg

    # Development closes: from START, horizon resolved by DEV_END.
    di = np.array([dt.date.toordinal(t) for t in dates])
    last_dev = max(i for i in range(n) if dates[i] <= DEV_END)
    dev = np.array([dates[i] >= START and i + N <= last_dev for i in range(n)])
    dev_idx = np.flatnonzero(dev)
    folds = np.array_split(dev_idx, FOLDS)
    event = dev & ~np.isnan(lab)
    print("development closes", dev.sum(), "event closes", event.sum(), dates[dev_idx[0]], dates[dev_idx[-1]])

    oof = {k: np.full(n, np.nan) for k in SPECS}
    p_rev_oof = np.full(n, np.nan)
    ms_params = []
    for fi, test in enumerate(folds):
        lo, hi = test[0], test[-1]
        train = dev.copy()
        train[max(lo - N, 0):min(hi + N + 1, n)] = False
        ms = fit_ms(e, train)
        filt, _ = hamilton(ms, e)
        ms_params.append(dict(zip(["phi", "sigma_R", "sigma_W", "p_RR", "p_WW"], [round(v, 5) for v in unpack(ms)])))
        p_rev_oof[test] = filt[test]
        feat_f = dict(feat, p_rev=filt)
        for k, cols in SPECS.items():
            rows_tr = train & ~np.isnan(lab)
            rows_te = np.zeros(n, bool); rows_te[test] = True; rows_te &= ~np.isnan(lab)
            if k in ("XN", "M_news_sample"):
                news_ok = np.array([t >= NEWS_START for t in dates])
                rows_tr &= news_ok; rows_te &= news_ok
            Xall = np.column_stack([feat_f[c] for c in cols])
            ok = ~np.isnan(Xall).any(1)
            tr, te = rows_tr & ok, rows_te & ok
            mu, sd = Xall[tr].mean(0), Xall[tr].std(0)
            sd[sd == 0] = 1
            m = LogisticRegression(C=1.0, max_iter=1000).fit((Xall[tr] - mu) / sd, lab[tr])
            if te.any():
                oof[k][te] = m.predict_proba((Xall[te] - mu) / sd)[:, 1]
        print("fold", fi, dates[lo], dates[hi], ms_params[-1])

    ev = event & ~np.isnan(oof["X"]) & ~np.isnan(oof["M"])
    yv = lab[ev]
    out = {"protocol": "research/PROTOCOL.md, H15", "computed": dt.date.today().isoformat(),
           "development": {"first": dates[dev_idx[0]].isoformat(), "last": dates[dev_idx[-1]].isoformat(), "closes": int(dev.sum()),
                           "event_closes": int(event.sum()), "scored_events": int(ev.sum()), "base_rate": round(float(yv.mean()), 4),
                           "median_days_to_close": float(np.nanmedian(days[ev & (lab == 1)]))},
           "folds": [{"first": dates[f[0]].isoformat(), "last": dates[f[-1]].isoformat(), "markov": p} for f, p in zip(folds, ms_params)],
           "scores": {k: summary(oof[k][ev], yv) for k in ("Z", "G", "M", "X")},
           "tests": {"X_vs_M": compare(oof["X"][ev], oof["M"][ev], yv), "M_vs_Z": compare(oof["M"][ev], oof["Z"][ev], yv),
                     "M_vs_G": compare(oof["M"][ev], oof["G"][ev], yv), "G_vs_Z": compare(oof["G"][ev], oof["Z"][ev], yv)},
           "specifications_fitted": list(SPECS)}
    evn = event & ~np.isnan(oof["XN"]) & ~np.isnan(oof["M_news_sample"])
    out["news"] = {"from": NEWS_START.isoformat(), "scores": {"M": summary(oof["M_news_sample"][evn], lab[evn]), "XN": summary(oof["XN"][evn], lab[evn])},
                   "XN_vs_M": compare(oof["XN"][evn], oof["M_news_sample"][evn], lab[evn])}
    t = out["tests"]["X_vs_M"]
    out["gate_passed"] = bool(t["mean_gain"] > 0 and t["t"] is not None and t["t"] > 1.65)
    # Event rate by year, for the record.
    out["by_year"] = []
    for yr in sorted({dd.year for dd in np.array(dates)[ev]}):
        m = ev & np.array([dd.year == yr for dd in dates])
        out["by_year"].append({"year": yr, "events": int(m.sum()), "closed": round(float(lab[m].mean()), 3),
                               "mean_p_M": round(float(oof["M"][m].mean()), 3), "mean_p_X": round(float(oof["X"][m].mean()), 3)})
    json.dump(out, open("research/results/h15.json", "w"), indent=1)

    cols = ["absz", "eg", "africa", "results_ahead", "div_gap", "zar_vol", "rate_6m", "news"]
    with open("research/results/h15_daily.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "development", "z126", "hedge_ratio126", "hedge_ratio_rls", "label", "days_to_close", "p_reverting_oof", *cols[1:],
                    *[f"p_{k}_oof" for k in SPECS]])
        for i in range(n):
            fm = lambda v, k=4: "" if v is None or (isinstance(v, float) and np.isnan(v)) else f"{v:.{k}f}"
            w.writerow([dates[i].isoformat(), int(dev[i]), fm(z[i]), fm(b[i]), fm(b_rls[i]), fm(lab[i], 0), fm(days[i], 0), fm(p_rev_oof[i]),
                        *[fm(feat[c][i], 5) for c in cols[1:]], *[fm(oof[k][i]) for k in SPECS]])
    with open("research/results/h15_events.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["kind", "bank", "date", "amount", "window_from", "window_to"])
        for r in csv.DictReader(open("data/raw/h15_div.csv")):
            w.writerow(["ex_dividend", r["bank"], r["ex_date"], r["amount"], "", ""])
        for yr in range(2005, 2027):
            for m in (3, 8):
                w.writerow(["results_month", "both", "", "", dt.date(yr, m, 1).isoformat(), (_add_months(dt.date(yr, m, 1), 1) - dt.timedelta(days=1)).isoformat()])
    print(json.dumps({k: out[k] for k in ("development", "scores", "tests", "news", "gate_passed")}, indent=1))
    print("by year", out["by_year"])


if __name__ == "__main__":
    main()
