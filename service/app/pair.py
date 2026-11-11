"""Standard Bank against Nedbank on the score-driven Student t copula (H8; research/PROTOCOL.md, "Re-centring").

Margins are the walk-forward's yearly ARMA-GARCH fits, frozen on 31 March 2026. Every walk-forward day's h comes
from research/models/copulas_py.py; sessions after the freeze are filtered forward from the copula's state at the
freeze with the final fold's parameters (data/pair_gas.json). Later refits (H17, data/refits.json) take over from
the session they apply from; before it, the sessions after a refit's date are filtered with its parameters only
to carry its state forward. The rule and costs are in app.rule: open when
|h - 0.5| passes the level, long SBK / short NED when h > 0.5, hold five sessions, half of capital a side.
"""

from __future__ import annotations

from datetime import date

import numpy as np

from .model import MarginalState, filter_marginal, gas_filter


class Pair:
    def __init__(self, walkforward: dict, final: dict, gas: dict, refits: list[dict]) -> None:
        self.walkforward, self.final, self.gas = walkforward, final, gas
        base = refits[0]
        if base["train_end"] != walkforward["freeze"] or gas["latest"]["train_end"] != walkforward["freeze"]:
            raise ValueError("data/pair_gas.json and data/refits.json must start at the walk-forward freeze")
        if any(abs(base["gas"][k] - gas["latest"][k]) > 1e-12 for k in ("omega", "beta", "alpha", "nu", "f_next")):
            raise ValueError("data/refits.json's first entry does not match data/pair_gas.json")
        # Refits in force: deployed ones (applies_from set), in date order.
        self.refits = [r for r in refits if r["applies_from"]]
        if [r["train_end"] for r in self.refits] != sorted(r["train_end"] for r in self.refits):
            raise ValueError("data/refits.json is not in date order")
        self.pending = [r["train_end"] for r in refits if not r["applies_from"]]
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
            "h0": np.array([gh[d] for d in h["date"]]),
            "r_sbk": np.expm1(np.array(h["r_sbk"], dtype=float)),
            "r_ned": np.expm1(np.array(h["r_ned"], dtype=float)),
        }
        self.live_rho: float | None = None

    def refit_segment(self, k: int, rows: dict) -> dict:
        """Refit k's margins and copula on the rows after its date, from its state at that date."""
        e = self.refits[k]
        after = np.array([d.isoformat() > e["train_end"] for d in rows["date"]])
        out = {}
        for b, uk in (("sbk", "u"), ("ned", "v")):
            s = e["state"][b]
            f = filter_marginal(e[b], MarginalState(r=s["r"], mu=s["mu"], sigma=s["sigma"], z=s["z"]), rows[f"r_{b}"][after], rows["vix"][after])
            out[uk], out[f"sigma_{b}"] = f["u"], f["sigma"]
        out["h"], out["rho"], _ = gas_filter(e["gas"], out["u"], out["v"])
        out["after"] = after
        return out

    def live(self, rows: dict) -> dict:
        """Post-freeze rows from app.main.live_rows (31 March margins) on the GAS copula; each refit in force
        replaces u, v and h from the session it applies from."""
        h0, rho, _ = gas_filter(self.gas["latest"], rows["u"], rows["v"])
        u, v, h, rho = np.array(rows["u"], dtype=float), np.array(rows["v"], dtype=float), h0.copy(), rho.copy()
        fit = np.array(rows["fold"], dtype=int)
        ds = [d.isoformat() for d in rows["date"]]
        for k in range(1, len(self.refits)):
            nxt = self.refits[k + 1]["applies_from"] if k + 1 < len(self.refits) else "9999-12-31"
            use = np.array([self.refits[k]["applies_from"] <= d < nxt for d in ds])
            if not use.any():
                continue
            seg = self.refit_segment(k, rows)
            m = use[seg["after"]]
            for a, b in ((u, seg["u"]), (v, seg["v"]), (h, seg["h"]), (rho, seg["rho"])):
                a[use] = b[m]
            fit[use] = fit[use] + k
        self.live_rho = float(rho[-1]) if len(rho) else None
        return {
            "date": list(rows["date"]),
            "fit": fit,
            "u": u,
            "v": v,
            "h": h,
            "h0": h0,
            "r_sbk": np.expm1(rows["r_sbk"]),
            "r_ned": np.expm1(rows["r_ned"]),
        }

    def in_force(self, as_of: date) -> dict:
        return [r for r in self.refits if r["applies_from"] <= as_of.isoformat()][-1]

    def rows(self, live: dict) -> dict:
        return {k: (self.history[k] + live[k] if k == "date" else np.concatenate([self.history[k], live[k]])) for k in self.history}


def spec(s: dict) -> dict:
    return {k: s[k] for k in ("model", "arma", "dist", "vix", "bic")}


def model_summary(p: Pair, live: dict) -> dict:
    f = p.final
    now = p.in_force(live["date"][-1]) if live["date"] else p.refits[0]
    g = now["gas"]
    return {
        "fits": [{"train_end": x["train_end"], "sbk": spec(x["sbk"]), "ned": spec(x["ned"]), "copula": {k: x["copula"][k] for k in ("family", "name", "par", "par2", "tau")}} for x in p.walkforward["folds"]],
        "latest": {"train_end": f["train_end"], "sbk": spec(f["sbk"]), "ned": spec(f["ned"]), "copula": f["copula"], "pit_ks": f["pit_ks"]},
        "refits": [{k: r[k] for k in ("train_end", "kind", "reselected", "applies_from", "data_to")} | {"sbk": spec(r["sbk"]), "ned": spec(r["ned"]), "gas": r["gas"]}
                   for r in p.refits],
        "pending_refits": p.pending,
        "in_force": now["train_end"],
        "dependence": {"model": "gas_t", **{k: g[k] for k in ("omega", "beta", "alpha", "nu", "rho_train_end")}, "rho_live": p.live_rho},
        "pit": {
            "walkforward": {"u": p.history["u"], "v": p.history["v"]},
            "live": {"u": live["u"], "v": live["v"]},
        },
    }
