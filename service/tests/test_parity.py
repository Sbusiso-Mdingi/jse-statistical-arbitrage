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


def test_basket_live_filter_matches_r():
    from app.basket import Basket

    b = Basket(json.loads((ROOT / "data" / "basket.json").read_text()))
    par = b.latest["parity"]
    rows = b.live_rows(b.snapshot_rows())
    np.testing.assert_allclose(rows["u"], par["u"], atol=1e-8)
    np.testing.assert_allclose(rows["v"], par["v"], atol=1e-8)
    np.testing.assert_allclose(rows["h"], par["h"], atol=1e-7)
