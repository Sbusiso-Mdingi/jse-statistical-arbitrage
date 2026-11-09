"""Standard Bank against Nedbank on the score-driven Student t copula (H8; research/PROTOCOL.md, "Re-centring").

Margins are the walk-forward's yearly ARMA-GARCH fits, frozen on 31 March 2026. Every walk-forward day's h comes
from research/models/copulas_py.py; sessions after the freeze are filtered forward from the copula's state at the
freeze with the final fold's parameters (data/pair_gas.json). The rule and costs are in app.rule: open when
|h - 0.5| passes the level, long SBK / short NED when h > 0.5, hold five sessions, half of capital a side.
"""

from __future__ import annotations

from datetime import date

import numpy as np

from .model import gas_filter


class Pair:
    def __init__(self, walkforward: dict, final: dict, gas: dict) -> None:
        self.walkforward, self.final, self.gas = walkforward, final, gas
        if gas["latest"]["train_end"] != walkforward["freeze"]:
            raise ValueError("data/pair_gas.json does not match the walk-forward freeze; rerun research/models/export_pair_gas.py")
        h = walkforward["history"]
        gh = dict(zip(gas["history"]["date"], gas["history"]["h"]))
        missing = [d for d in h["date"] if d not in gh]
        if missing:
            raise ValueError(f"pair_gas.json lacks {len(missing)} walk-forward days, first {missing[0]}")
        self.history = {
            "date": [date.fromisoformat(d) for d in h["date"]],
            "fit": np.array(h["fold"], dtype=int),
            "u": np.array(h["u"], dtype=float),
            "v": np.array(h["v"], dtype=float),
            "h": np.array([gh[d] for d in h["date"]]),
            "r_sbk": np.expm1(np.array(h["r_sbk"], dtype=float)),
            "r_ned": np.expm1(np.array(h["r_ned"], dtype=float)),
        }
        self.live_rho: float | None = None

    def live(self, rows: dict) -> dict:
        """Post-freeze rows from app.main.live_rows (final fold margins) on the GAS copula."""
        h, rho, _ = gas_filter(self.gas["latest"], rows["u"], rows["v"])
        self.live_rho = float(rho[-1]) if len(rho) else None
        return {
            "date": list(rows["date"]),
            "fit": np.array(rows["fold"], dtype=int),
            "u": np.asarray(rows["u"]),
            "v": np.asarray(rows["v"]),
            "h": h,
            "r_sbk": np.expm1(rows["r_sbk"]),
            "r_ned": np.expm1(rows["r_ned"]),
        }

    def rows(self, live: dict) -> dict:
        return {k: (self.history[k] + live[k] if k == "date" else np.concatenate([self.history[k], live[k]])) for k in self.history}


def spec(s: dict) -> dict:
    return {k: s[k] for k in ("model", "arma", "dist", "vix", "bic")}


def model_summary(p: Pair, live: dict) -> dict:
    f = p.final
    g = p.gas["latest"]
    return {
        "fits": [{"train_end": x["train_end"], "sbk": spec(x["sbk"]), "ned": spec(x["ned"]), "copula": {k: x["copula"][k] for k in ("family", "name", "par", "par2", "tau")}} for x in p.walkforward["folds"]],
        "latest": {"train_end": f["train_end"], "sbk": spec(f["sbk"]), "ned": spec(f["ned"]), "copula": f["copula"], "pit_ks": f["pit_ks"]},
        "dependence": {"model": "gas_t", **{k: g[k] for k in ("omega", "beta", "alpha", "nu", "rho_train_end")}, "rho_live": p.live_rho},
        "pit": {
            "walkforward": {"u": p.history["u"], "v": p.history["v"]},
            "live": {"u": live["u"], "v": live["v"]},
        },
    }
