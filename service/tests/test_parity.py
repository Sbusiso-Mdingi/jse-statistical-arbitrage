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
