# Research protocol

Written 13 October 2026, before any of the tests below were run. Results are reported whatever they show.

## Periods

| Period | Dates (trading days) | Use |
| --- | --- | --- |
| Design | 2010-01-01 to 2019-12-31 | Every choice of rule or setting |
| Validation | 2020-01-01 to 2026-03-31 | Run once per hypothesis, after its rules are fixed |
| Post-freeze | 2026-04-01 onward | Reported only, never used to choose anything |

All model fits use only data before the day they trade. Costs are 10 bps per unit of notional traded on every leg. A position set at the close of day t earns day t + 1.

## What was already known when this was written

Honesty about prior looks at the data:

- v1 (the group report's rule, 90/50 percentiles, volatility filter at 80, daily signal) has been run on every period, including post-freeze.
- On design data only: the SBK/NED reversal builds over about five days for extreme signals, and extreme divergences on quiet-volume days reverted far more the next day than on busy days.
- The best design-period variant from a 78-rule grid (hold five days after the signal passes the 90th percentile) was validated once and failed: Sharpe 0.40 in design, -0.58 in validation.
- Lag-1 autocorrelation of daily return spreads for all 15 pairs of SBK, NED, FSR, ABG, CPI and INL was computed for 2010-15, 2015-20, 2020-23 and 2023-26. Reversal was strong early and close to zero since 2020. That makes the hypotheses below unlikely to pass validation; they are tested anyway because they are the best-motivated remaining ideas.

## H1: Standard Bank against a bank basket, refitted monthly

Rationale: a single partner bank brings its own news into the spread. An equal-weight basket of FirstRand, Absa, Nedbank and Capitec is closer to "the sector", so SBK's deviation from it is more likely to be noise that reverses.

- Basket return: equal-weight average of the four simple daily returns, rebalanced daily.
- Margins: the same 36-model ARMA-GARCH grid for SBK and for the basket, chosen by BIC once a year on all data to that year end; parameters re-estimated at each month end with the chosen specification.
- Copula: family chosen by AIC at each month end (families 1, 2, 3, 4, 5, 13, 14).
- Signal: h = P(basket <= v | SBK = u). Open when |h - 0.5| > 0.45 (the 90th percentile of |h - 0.5| under the model, the same threshold as the SBK/NED five-day rule; amended from a mistyped 0.40 before any H1 result was computed), long SBK / short basket when h > 0.5 and the reverse below. Hold five trading days; a new signal restarts the count and can flip the side.
- Sizing: half of capital in SBK, half spread equally across the four basket names.
- Pass mark: validation Sharpe after costs above zero and above the v1 validation Sharpe (-0.70).

## H2: trade only divergences without news

Rationale: price moves on news tend to continue; moves without news tend to reverse (Chan, 2003). Applied to the SBK/NED pair with the five-day hold rule above.

- H2a, trading-volume proxy (design 2010-19, validation 2020 to March 2026). A news day for a bank is one where its volume is more than 1.5 times the median of the previous 60 sessions. No new position is opened on a day that is a news day for either bank. Existing positions are unaffected.
- H2b, GDELT news coverage (design 18 February 2015 to 2019, validation 2020 to March 2026). Amended before any H2b result was computed: the data now comes from the full GDELT 2.0 knowledge graph on BigQuery, which starts in February 2015, rather than the DOC API, which starts in 2017. An article counts for a bank when the bank appears in the GKG organisation list. A news day is one where the number of GDELT articles mentioning the bank is more than twice its median over the previous 60 days. Articles count towards the first JSE session whose close (15:00 UTC) is at or after their timestamp, so the count for day t uses only articles published before that day's close. Same entry rule as H2a.
- Pass mark: validation Sharpe after costs above zero and above the unfiltered five-day rule in validation (-0.58).

## Decay study

For every pair of the six banks, the one-year rolling lag-1 autocorrelation of the daily log-return spread, plotted through time, with the SBK/NED copula signal's next-day reversal (bps) by year. Descriptive only; nothing is selected from it.

## H3: a learned exit for the bank-basket trade

Added 13 October 2026, after the H1, H2 and decay results above were known and before any H3 result was computed. Rationale: H1's signal holds up before costs, so the remaining question is whether news and market state can tell, day by day, when a reversal trade has gone stale.

- Entries are exactly H1's. Every close on which an H1 position has been held for one to four days is a decision point: keep holding over the next session, or exit at this close. A signal day is never a decision point, because the signal itself restarts the hold. After an exit the position stays flat until the next H1 signal.
- Exiting early does not add a cost (the exit is paid either way), so the value of exiting is zero and the value of holding is the next session's held return plus, for H3b, the value of the following decision.
- Features at close t, all known by then: days held; the current signal in the trade's direction, d(h - 0.5); the entry signal's strength; the trade's gross return so far; today's held return; 20-session realised volatility of the SBK minus basket return; the last VIX close before the session; GDELT article counts for SBK and for the four basket banks combined, each as log((1 + count) / (1 + median of the previous 60 sessions)); the trade-direction relative tone, d((SBK tone - its 60-session mean) - (basket tone - its 60-session mean)), zero on days without articles; and log volume relative to the 60-session median for SBK and, averaged, for the basket. Articles are mapped to sessions as in H2b. Features are standardised on each training set.
- H3a, classifier: L2 logistic regression for "the next held return is positive"; exit when the predicted probability is below 0.5.
- H3b, reinforcement learning by fitted Q-iteration (optimal stopping): ridge regression for the value of holding, with target the next held return plus max(0, predicted value at the next decision point) when there is one, iterated four times. Exit when the predicted value of holding is below zero.
- Fitting: walk-forward, refitted at each year end from 2016 on all decision points whose outcome is known by then; the first fit uses 13 May 2015 to 2016. Design therefore covers 2017 to 2019. The regularisation strength is chosen once, by the design-period Sharpe, from C in {0.01, 0.1, 1} for H3a and alpha in {1, 10, 100} for H3b.
- Pass mark, for each of H3a and H3b separately: validation Sharpe after costs above zero and above H1's (0.06). Two tests on the same validation data: a pass by one of them is weaker evidence than it looks, and is reported as such.
- Reported but not tested: H3a without the news features, to show what GDELT adds; H1 over the same 2017 to 2019 design window, for comparison.
