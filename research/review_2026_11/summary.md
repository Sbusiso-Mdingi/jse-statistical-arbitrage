# SBK/NED strategy review, 12 Nov 2026 (development data to 31 Mar 2026 only)

Four independent reviews: overfitting, execution and costs, design, copula. All reproduced H16 exactly (79 trades, +91.1 bps futures, t 3.58). Scratch scripts in /tmp/jse-review/{overfit,execution,design,copula}/.

## Headline
The spread gate's +91 bps is not search noise (time-shifted gate placebo: mean 11 bps, P(>=91) 0.002), but three things stand between it and money:
1. Fill at the signal's own close: 35 of 145 bps gross is earned on day 1. Next-close fill -> 49 bps (t 1.93). A 16:00 signal filled in the closing auction keeps ~80-87 bps.
2. Selection: CSCV on the 50 searched specs gives 44 bps out of sample (PBO 0.53). Window 126 is a narrow peak (105: 53, 147: 75, 189: -7); the -2.8 cutoff is a real plateau.
3. Dividend data bug: Yahoo "adjusted" closes carry ~1/100 of each dividend (cents vs rand). Checked: SBK ex 10 Apr 2024, 733c (~4%), adjusted fell 3.4% like the raw close. On properly adjusted prices H16 earns +59 bps (t 1.76). Copula signals fire on 44% of ex-dates vs 10% expected.

Expected live: ~45 bps a trade as scored (range 25-60), ~0-20 bps on a next-close fill. Verdict test passes only ~40-54% of the time at a 45-60 bps true mean (9% false-pass at 0 because of left skew); verdict ~2036.

## Copula
Retire as a trading signal. The pair's own reversal is gone (lag-1 autocorrelation of relative return -0.18 in 2010-14 -> -0.03 since 2021). The old edge was model misspecification (no cross-bank mean term) plus auction-print bounce (~half). No leak in the code. Adds nothing to the spread trade as timer or veto.

## Proposed new live-only hypotheses (nothing frozen changes)
- H16-T: 16:00 signal, closing-auction fill (needs a live intraday feed; none exists).
- H16-TR: same rule on dividend-correct prices (dev +59, stated in advance).
- Window ensemble 105/110-126-140/147.
- Reporting: fill-lag figures, fixed-contract P&L (-5 bps), dividend-inclusive P&L, observed SSF quotes, ex-date flags on copula records, episode-clustered / skew-corrected verdict test.
- Copula: results-month exclusion check, add-on to open H16 trades, revival watch.

## Rejected (dev data)
Exit on gate shut (19 bps), tighter stops (43-53), Kalman/TLS/1:1/reverse spreads, half-life/VR/hysteresis/CUSUM gates, |z| or gate-strength sizing, drawdown brake, copula timer/veto, cumulative mispricing indices.
