"""The live filter must reproduce rugarch/VineCopula on the post-freeze window."""

import json
from pathlib import Path

import numpy as np

from app.model import MarginalState, conditional_probabilities, filter_marginal

ROOT = Path(__file__).resolve().parents[2]
final = json.loads((ROOT / "data" / "model_final.json").read_text())
p = {k: np.array(v) for k, v in final["parity"].items() if k != "date"}


def state(key):
    s = final["state"][key]
    return MarginalState(r=s["r"], mu=s["mu"], sigma=s["sigma"], z=s["z"])


def test_marginals_and_copula_match_r():
    fs = filter_marginal(final["sbk"], state("sbk"), p["r_sbk"], p["vix"])
    fn = filter_marginal(final["ned"], state("ned"), p["r_ned"], p["vix"])
    np.testing.assert_allclose(fs["sigma"], p["sigma_sbk"], rtol=1e-8)
    np.testing.assert_allclose(fn["sigma"], p["sigma_ned"], rtol=1e-8)
    np.testing.assert_allclose(fs["mu"], p["mu_sbk"], atol=1e-10)
    np.testing.assert_allclose(fn["mu"], p["mu_ned"], atol=1e-10)
    np.testing.assert_allclose(fs["u"], p["u"], atol=1e-8)
    np.testing.assert_allclose(fn["u"], p["v"], atol=1e-8)
    h_ns, h_sn = conditional_probabilities(final["copula"], fs["u"], fn["u"])
    np.testing.assert_allclose(h_ns, p["h_ns"], atol=1e-7)
    np.testing.assert_allclose(h_sn, p["h_sn"], atol=1e-7)


def test_pair_gas_matches_research():
    """The service's pair h on post-freeze sessions must equal the research GAS filter (copulas_py.csv)."""
    import csv

    from app.main import PAIR, live_rows, snapshot_rows

    rows = PAIR.live(live_rows(snapshot_rows()))
    ref = {r["date"]: float(r["h"]) for r in csv.DictReader(open(ROOT / "research" / "results" / "copulas_py.csv")) if r["model"] == "gas_t"}
    got = [(h, ref[d.isoformat()]) for d, h in zip(rows["date"], rows["h"]) if d.isoformat() in ref]
    assert len(got) > 100
    a = np.array(got)
    np.testing.assert_allclose(a[:, 0], a[:, 1], atol=1e-7)
    hist = PAIR.history
    assert hist["date"][-1].isoformat() == final["train_end"]


def test_rule_and_costs_match_research():
    """The service's rule and JSE cost schedule reproduce research/pair.py's Sharpe ratios by period and tier."""
    from datetime import date

    from app import rule
    from app.main import PAIR, live_rows, snapshot_rows

    rows = PAIR.rows(PAIR.live(live_rows(snapshot_rows())))
    ref = json.loads((ROOT / "research" / "results" / "pair.json").read_text())["costs"]["tiers"]
    periods = {"design": (date(2010, 1, 1), date(2020, 1, 1)), "validation": (date(2020, 1, 1), date(2026, 4, 1))}
    for tier in ("protocol", "institutional", "retail"):
        out = rule.run(rows, rule.Params(costs=tier), "all")
        eq = np.asarray(out["series"]["equity"], dtype=float)
        daily = np.concatenate([[eq[0] - 1.0], eq[1:] / eq[:-1] - 1.0])
        dates = out["series"]["date"]
        for name, (a, b) in periods.items():
            m = np.array([a <= d < b for d in dates])
            x = daily[m]
            sharpe = x.mean() / x.std(ddof=1) * np.sqrt(252)
            assert abs(sharpe - ref[tier][name]["sharpe"]) < 0.015, (tier, name, sharpe, ref[tier][name]["sharpe"])


def test_shadow_own_vol_matches_research():
    """H13 variant A: the service's live filter reproduces research/models/export_shadow.py after the freeze."""
    from app import shadow
    from app.main import SHADOW, live_rows, snapshot_rows, walkforward

    rows = live_rows(snapshot_rows())
    hist = walkforward["history"]
    h = shadow.own_vol_live(SHADOW["own_vol"], (np.array(hist["r_sbk"]), np.array(hist["r_ned"])),
                            {"u": rows["u"], "v": rows["v"], "r_sbk_log": rows["r_sbk"], "r_ned_log": rows["r_ned"]})
    ref = dict(zip(SHADOW["reference"]["date"], SHADOW["reference"]["h"]))
    common = [(i, ref[d.isoformat()]) for i, d in enumerate(rows["date"]) if d.isoformat() in ref]
    assert len(common) > 50
    assert max(abs(h[i] - r) for i, r in common) < 1e-6


def test_switch_gate_matches_research():
    """H14: the service's rolling statistic and method reproduce research/results/h14_daily.csv once the
    126-session window is full (the service's record starts in 2010, the research one in 2005)."""
    import csv

    from app import switch
    from app.main import PAIR, live_rows, snapshot_rows, switch_state

    body = switch_state(PAIR.rows(PAIR.live(live_rows(snapshot_rows()))))
    ref = {r["date"]: r for r in csv.DictReader(open(Path(__file__).resolve().parents[2] / "research/results/h14_daily.csv"))}
    s = body["series"]
    rows = [(d.isoformat(), e, m) for d, e, m in zip(s["date"][switch.L:], s["eg"][switch.L:], s["mode"][switch.L:])]
    common = [(e, m, ref[d]) for d, e, m in rows if d in ref]
    assert len(common) > 3900
    assert max(abs(e - float(r["eg126"])) for e, m, r in common) < 6e-5  # the csv keeps four decimals
    assert all(("spread" if m else "copula") == r["mode"] for e, m, r in common)
    # Scored from 1 April 2026 (PROTOCOL.md, amendment of 11 November 2026): every live trade opened on or after it.
    assert body["score_from"] == body["spread_gate"]["score_from"] == "2026-04-01"
    for k in ("switch", "copula_alone"):
        assert all(t["opened"].isoformat() >= "2026-04-01" for t in body[k]["trades"])
    assert body["switch"]["complete"] == body["copula_alone"]["complete"]  # no spread mode since April
    g = body["spread_gate"]
    assert all(bool(m) == (e is not None and e < switch.GATE_CRIT) for e, m in zip(s["eg"], s["gate"]))
    assert g["complete"] == 0 and g["development"]["trades"] == 79


def test_refits_history():
    """data/refits.json (H17): the first entry is the fit of 31 March 2026; each later refit, once it applies,
    reproduces research/refit_export.py's filter on the sessions after its date and leaves earlier sessions alone."""
    import copy
    from datetime import date

    from app import pair as pr
    from app.main import PAIR, live_rows, snapshot_rows

    book = json.loads((ROOT / "data" / "refits.json").read_text())["refits"]
    base = book[0]
    assert base["train_end"] == final["train_end"] and base["applies_from"] == final["trade_start"]
    for b in ("sbk", "ned"):
        assert base[b]["coef"] == final[b]["coef"]
        assert all(base["state"][b][k] == final["state"][b][k] for k in ("r", "mu", "sigma", "z"))
    assert [e["train_end"] for e in book] == sorted({e["train_end"] for e in book})
    rows = live_rows(snapshot_rows())
    frozen = PAIR.live(rows)
    snap = {d.isoformat() for d in rows["date"]}
    for k, e in enumerate(book[1:], 1):
        ref = e.get("reference")
        if not ref:
            continue
        # Each refit as if deployed on its first reference session.
        trial = copy.deepcopy(book[: k + 1])
        for x in trial[1:]:
            x["applies_from"] = x["applies_from"] or (x.get("reference") or ref)["date"][0]
        p = pr.Pair(PAIR.walkforward, PAIR.final, PAIR.gas, trial)
        # The refit's own filter on the sessions after its date.
        seg_rows = {"date": [date.fromisoformat(d) for d in ref["date"]], **{c: np.array(ref[c]) for c in ("r_sbk", "r_ned", "vix")}}
        seg = p.refit_segment(k, seg_rows)
        for c in ("u", "v", "h"):
            np.testing.assert_allclose(seg[c], ref[c], atol=1e-8, err_msg=c)
        # Stitched into the live record: earlier sessions untouched, later ones from the refit.
        if sum(d in snap for d in ref["date"]) < 10:
            continue
        out = p.live(rows)
        ds = [d.isoformat() for d in out["date"]]
        frm = trial[k]["applies_from"]
        got = dict(zip(ds, out["h"]))
        both = [i for i, d in enumerate(ref["date"]) if d in got and d >= frm]
        np.testing.assert_allclose([got[ref["date"][i]] for i in both], [ref["h"][i] for i in both], atol=1e-8)
        before = [i for i, d in enumerate(ds) if d < frm]
        np.testing.assert_array_equal(out["h"][before], frozen["h"][before])
        np.testing.assert_array_equal(out["h0"], frozen["h0"])
        assert (out["fit"][[i for i, d in enumerate(ds) if d >= frm]] == final["id"] + k).all()
        assert p.in_force(date.fromisoformat(ds[-1]))["train_end"] == e["train_end"]
