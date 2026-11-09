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


def test_gas_copula_matches_research():
    """The service's score-driven copula, run forward from the exported state, reproduces the research h."""
    import csv, json
    from pathlib import Path
    import numpy as np
    from app import basket as bk
    root = Path(__file__).resolve().parents[2]
    gas_path = root / "data" / "basket_gas.json"
    if not gas_path.exists():
        return
    b = bk.Basket(json.loads((root / "data" / "basket.json").read_text()), json.loads(gas_path.read_text()))
    live = b.live_rows(b.snapshot_rows())
    research = {r["date"]: float(r["h"]) for r in csv.DictReader(open(root / "research" / "results" / "copulas_basket.csv")) if r["model"] == "gas_t"}
    pairs = [(h, research[d.isoformat()]) for d, h in zip(live["date"], live["h"]) if d.isoformat() in research]
    assert len(pairs) >= 5
    assert max(abs(a - b_) for a, b_ in pairs) < 1e-6
