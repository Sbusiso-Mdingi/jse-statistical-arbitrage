"""A JSE cost schedule for the pairs position, in place of the protocol's flat 10 bps a leg.

Each change of position trades two legs, each at half of capital. Per execution: brokerage (plus 15%
VAT), a half bid-ask spread, Strate settlement and the investor protection levy (about a basis point
together); on every PURCHASE, securities transfer tax of 0.25% of value. A round trip of the pairs
position has two purchases: the long leg to open and the short leg to cover. Short borrow is charged
daily on the short leg's notional. Writes research/results/costs.json. Reporting only: the pre-registered
verdicts were set at 10 bps a leg and stand.

Sources: SARS, securities transfer tax 0.25% on transfers of listed securities (sars.gov.za); EasyEquities
commission 0.25% (easyequities.co.za/pricing); Standard Bank AutoShare Invest brokerage 0.15%
(standardbank.co.za). VAT 15% by statute. Strate and the levy are taken from broker fee schedules
as about 1 bp per execution at retail size and less at institutional size. The half-spread and the borrow
fee are assumptions and are varied below.
"""
import csv, json, math, sys
import numpy as np
sys.path.insert(0, "research")
from h5_weights import load, positions, PERIODS, BASKET  # noqa: E402

STT = 25.0  # bps of value, on purchases
VAT = 0.15
TIERS = {
    "protocol": dict(label="Protocol: 10 bps a leg, flat", brokerage=10.0, vat=False, spread=0.0, strate=0.0, stt=0.0, borrow=0.0),
    "institutional": dict(label="JSE, institutional", brokerage=10.0, vat=True, spread=5.0, strate=0.3, stt=STT, borrow=100.0),
    "retail": dict(label="JSE, retail brokerage", brokerage=25.0, vat=True, spread=5.0, strate=1.0, stt=STT, borrow=100.0),
}


def round_trip(t):
    """Cost of opening and closing the pairs position once, in bps of capital."""
    b = t["brokerage"] * (1 + VAT if t["vat"] else 1)
    per_exec = b + t["spread"] + t["strate"]
    # four executions at half of capital each; STT on the two purchases
    return 4 * 0.5 * per_exec + 2 * 0.5 * t["stt"]


def costs(pos, t, hold_days=None):
    """Daily cost series for a position path. Position +1 = long SBK, short basket; each leg half of capital."""
    b = t["brokerage"] * (1 + VAT if t["vat"] else 1) / 1e4
    per_exec = b + (t["spread"] + t["strate"]) / 1e4
    stt = t["stt"] / 1e4
    prev = np.concatenate([[0.0], pos[:-1]])
    d = pos - prev  # change in the SBK leg's signed exposure (units of capital); the basket leg is -d
    sbk_notional = 0.5 * np.abs(d)
    bsk_notional = 0.5 * np.abs(d)
    # purchases: SBK leg bought when exposure rises; basket leg bought when its (negative) exposure rises, i.e. when d < 0
    sbk_buy = 0.5 * np.maximum(d, 0)
    bsk_buy = 0.5 * np.maximum(-d, 0)
    exec_cost = (sbk_notional + bsk_notional) * per_exec + (sbk_buy + bsk_buy) * stt
    borrow = 0.5 * np.abs(prev) * (t["borrow"] / 1e4) / 252  # one leg is always short while a position is held
    return exec_cost + borrow


def stats(net, dates, a, b):
    m = np.array([a <= x.isoformat() < b for x in dates])
    x = net[m]
    eq = np.cumprod(1 + x); sd = x.std(ddof=1); yrs = len(x) / 252
    return dict(sharpe=round(float(x.mean() / sd * math.sqrt(252)), 2), cagr=round(float(eq[-1] ** (1 / yrs) - 1), 4),
                mdd=round(float((eq / np.maximum.accumulate(eq) - 1).min()), 4))


if __name__ == "__main__":
    d = load()
    g = json.load(open("data/basket_gas.json"))["history"]
    gh = dict(zip(g["date"], g["h"]))
    idx = [i for i, x in enumerate(d["date"]) if x.isoformat() in gh]
    dates = [d["date"][i] for i in idx]
    h = np.array([gh[x.isoformat()] for x in dates])
    rs = d["simple"]["sbk"][idx]; rb = np.mean([d["simple"][k] for k in BASKET], axis=0)[idx]
    pos = positions(h)
    held = np.concatenate([[0.0], pos[:-1]])
    gross = held * 0.5 * (rs - rb)
    out = {"stt_bps": STT, "vat": VAT, "tiers": {}}
    print(f"{'tier':16s} round trip   design SR   validation SR   full SR   full CAGR")
    for k, t in TIERS.items():
        net = gross - costs(pos, t)
        rec = {"label": t["label"], "round_trip_bps": round(round_trip(t), 1), "assumptions": {kk: v for kk, v in t.items() if kk != "label"},
               "design": stats(net, dates, *PERIODS["design"]), "validation": stats(net, dates, *PERIODS["validation"]), "full": stats(net, dates, "2010-01-01", "2026-04-01")}
        out["tiers"][k] = rec
        print(f"{k:16s} {rec['round_trip_bps']:6.1f} bps   {rec['design']['sharpe']:6.2f}      {rec['validation']['sharpe']:6.2f}       {rec['full']['sharpe']:6.2f}    {rec['full']['cagr']*100:5.1f}%")
    # Sensitivity of the institutional round trip to the two assumptions
    sens = []
    for spread in (2.0, 5.0, 10.0):
        for borrow in (50.0, 100.0, 300.0):
            t = dict(TIERS["institutional"], spread=spread, borrow=borrow)
            net = gross - costs(pos, t)
            sens.append({"spread": spread, "borrow_bps_year": borrow, "round_trip_bps": round(round_trip(t), 1), "full_sharpe": stats(net, dates, "2010-01-01", "2026-04-01")["sharpe"]})
    out["sensitivity"] = sens
    print("institutional round trip across assumptions:", sorted({s["round_trip_bps"] for s in sens}))
    # Costs by component, institutional, per round trip
    t = TIERS["institutional"]
    out["components_institutional"] = {"brokerage_incl_vat": round(4 * 0.5 * t["brokerage"] * (1 + VAT), 1), "stt": round(2 * 0.5 * STT, 1), "spread": round(4 * 0.5 * t["spread"], 1), "strate_levy": round(4 * 0.5 * t["strate"], 1), "borrow_per_5_days": round(0.5 * t["borrow"] * 5 / 252, 2)}
    print("components:", out["components_institutional"])
    # Reported, not tested: the original report's exit (close when the signal is back inside the 50th percentile,
    # |h - 0.5| < 0.25) on the basket instrument, instead of the five-day hold.
    def positions_revert(h, open_level=0.45, close_level=0.25):
        pos = np.zeros(len(h)); cur = 0.0
        for t in range(len(h)):
            s = abs(h[t] - 0.5)
            if s > open_level:
                cur = 1.0 if h[t] > 0.5 else -1.0
            elif cur != 0 and s < close_level:
                cur = 0.0
            pos[t] = cur
        return pos
    pos_r = positions_revert(h)
    held_r = np.concatenate([[0.0], pos_r[:-1]])
    gross_r = held_r * 0.5 * (rs - rb)
    hold_lengths = []
    run_len = 0
    for x in pos_r:
        if x != 0: run_len += 1
        elif run_len: hold_lengths.append(run_len); run_len = 0
    out["hold_until_normal"] = {"avg_days_held": round(float(np.mean(hold_lengths)), 1), "trades": len(hold_lengths),
                                "in_market": round(float((pos_r != 0).mean()), 3), "tiers": {}}
    print("\nhold until the signal is back inside the 50th percentile (reported): avg hold %.1f days, %d trades, in market %.0f%%" % (np.mean(hold_lengths), len(hold_lengths), 100 * (pos_r != 0).mean()))
    for k, t in TIERS.items():
        net = gross_r - costs(pos_r, t)
        rec = {"design": stats(net, dates, *PERIODS["design"]), "validation": stats(net, dates, *PERIODS["validation"]), "full": stats(net, dates, "2010-01-01", "2026-04-01")}
        out["hold_until_normal"]["tiers"][k] = rec
        print(f"  {k:16s} design SR {rec['design']['sharpe']:6.2f}  validation SR {rec['validation']['sharpe']:6.2f}  full SR {rec['full']['sharpe']:6.2f}")
    json.dump(out, open("research/results/costs.json", "w"), indent=1)
