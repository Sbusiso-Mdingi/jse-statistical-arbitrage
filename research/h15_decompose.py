"""H15 step 4 (descriptive): why the 126-session hedge ratio of log NED on log SBK is about zero.

  python research/h15_decompose.py

Splits each bank's daily log return into a sector part (beta on the mean of FirstRand and Absa, a reference, never
traded) and its own part, then recomputes the hedge ratio with either bank's own part removed. Standard Bank's own
part is regressed on the rand against the naira, Kenyan shilling and cedi. Writes research/results/h15_decompose.json.
"""
import csv, json, sys
import numpy as np

sys.path.insert(0, "service")
from app import switch as sw  # noqa: E402

END = "2026-11-10"


def load():
    rows = [r for r in csv.DictReader(open("data/raw/h15_px.csv")) if r["date"] <= END]
    keys = ["sbk", "ned", "fsr", "abg"]
    rows = [r for r in rows if all(r[k] for k in keys)]
    d = [r["date"] for r in rows]
    px = {k: np.array([float(r[k]) for r in rows]) for k in keys}
    fx = {}
    for k in ("ngn", "kes", "ghs"):  # rand per unit of the African currency: usdzar / usdX
        v = []
        last = {"usdzar": None, "usd" + k: None}
        for r in rows:
            for kk in last:
                if r[kk]:
                    last[kk] = float(r[kk])
            v.append(last["usdzar"] / last["usd" + k] if all(last.values()) else np.nan)
        fx[k] = np.array(v)
    return d, px, fx


def slope(x, y):
    dx = x - x.mean()
    return float(dx @ (y - y.mean()) / (dx @ dx))


def main():
    d, px, fx = load()
    lg = {k: np.log(v) for k, v in px.items()}
    r = {k: np.diff(v) for k, v in lg.items()}
    rfx = {k: np.diff(np.log(v)) for k, v in fx.items()}
    rd = d[1:]
    sector = (r["fsr"] + r["abg"]) / 2
    L = sw.L
    w = slice(len(rd) - L, len(rd))  # the last 126 daily returns; levels over the same 127 closes
    out = {"end": rd[-1], "start": rd[w.start], "sessions": L}
    xs, ys = lg["sbk"][-L:], lg["ned"][-L:]
    out["hedge_ratio"] = slope(xs, ys)
    out["eg"] = sw.window_stats(xs, ys)[2]
    out["return_corr_window"] = float(np.corrcoef(r["sbk"][w], r["ned"][w])[0, 1])
    # History: daily-return correlation and hedge ratio over every 126-session window from 2010.
    b, _, eg = sw.rolling(lg["sbk"], lg["ned"])
    first = next(i for i, x in enumerate(d) if x >= "2010-07-01")
    out["hedge_ratio_history_pct"] = {q: float(np.nanpercentile(b[first:-1], q)) for q in (5, 25, 50, 75, 95)}
    cw = np.array([np.corrcoef(r["sbk"][i - L:i], r["ned"][i - L:i])[0, 1] for i in range(first, len(rd) + 1)])
    out["return_corr_history_pct"] = {q: float(np.percentile(cw, q)) for q in (5, 50, 95)}
    out["cum_log_return"] = {k: float(r[k][w].sum()) for k in ("sbk", "ned", "fsr", "abg")} | {"sector": float(sector[w].sum())}
    own, parts = {}, {}
    for k in ("sbk", "ned"):
        f = sector[w]; y = r[k][w]
        beta = float(np.cov(f, y)[0, 1] / f.var(ddof=1)); a = float(y.mean() - beta * f.mean())
        e = y - beta * f
        own[k] = e
        parts[k] = {"beta": beta, "r2": float(1 - (y - a - beta * f).var() / y.var()), "sector_part": float(beta * f.sum()),
                    "own_part": float(e.sum()), "own_sd_daily": float(e.std(ddof=1)), "sector_part_sd_daily": float((beta * f).std(ddof=1))}
    out["split"] = parts
    out["corr_own_parts"] = float(np.corrcoef(own["sbk"], own["ned"])[0, 1])

    def level(k, drop_own):
        rr = r[k][w] - (own[k] if drop_own else 0)
        return np.concatenate([[0.0], np.cumsum(rr)])

    out["hedge_ratio_if"] = {f"{'no' if a else 'with'}_sbk_own_{'no' if b_ else 'with'}_ned_own":
                             slope(level("sbk", a), level("ned", b_)) for a in (False, True) for b_ in (False, True)}
    # Standard Bank's own part on the African currencies (rand per unit; positive = the currency strengthened).
    X = np.column_stack([rfx[k][w] for k in ("ngn", "kes", "ghs")])
    ok = ~np.isnan(X).any(1)
    Xc = np.column_stack([np.ones(ok.sum()), X[ok]])
    for k in ("sbk", "ned"):
        coef, *_ = np.linalg.lstsq(Xc, own[k][ok], rcond=None)
        fit = Xc @ coef
        out.setdefault("africa_fx", {})[k] = {"coef_ngn_kes_ghs": [float(c) for c in coef[1:]],
                                              "r2": float(1 - ((own[k][ok] - fit) ** 2).sum() / ((own[k][ok] - own[k][ok].mean()) ** 2).sum()),
                                              "fx_part": float((Xc[:, 1:] @ coef[1:]).sum())}
    out["africa_fx_cum"] = {k: float(np.nansum(rfx[k][w])) for k in ("ngn", "kes", "ghs")}
    # Where the own parts accumulated: by month.
    months = sorted({x[:7] for x in rd[w]})
    out["own_by_month"] = {m: {k: float(own[k][[x[:7] == m for x in rd[w]]].sum()) for k in ("sbk", "ned")} for m in months}
    json.dump(out, open("research/results/h15_decompose.json", "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
