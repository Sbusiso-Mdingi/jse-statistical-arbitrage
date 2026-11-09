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

## H4: the classic cointegration trade

Added 25 October 2026, after the H1 to H3 results and the descriptive cointegration tests (`research/04_cointegration.R`) were known, and before any H4 result was computed. Rationale: the group report set the classic approach aside because SBK and NED are not cointegrated over the sample. This measures what the classic trade would have earned anyway, under the same periods and costs, so the copula strategies are compared with the method they replaced.

- Pair: SBK and NED adjusted closes, bad prints removed as elsewhere, in logs.
- At each close t, an OLS regression of log NED on log SBK over the last L sessions to t gives the intercept, the hedge ratio b and the residual standard deviation; z is today's residual divided by that standard deviation.
- Open when |z| > e: above e, short NED and long SBK; below -e, the reverse. NED carries weight 1 / (1 + |b|) and SBK |b| / (1 + |b|), with b fixed at entry, so gross exposure is 1 as in H1. Close when z comes back inside x on its own side (z < x for a short spread, z > -x for a long one), when |z| exceeds 4, or after 60 sessions, whichever comes first. A close and a new open can happen on the same day.
- H4a trades whenever the rule says so. H4b opens only when the Engle-Granger test on the same L sessions rejects no cointegration at 5%: an ADF regression on the residuals with one lagged difference and no constant, against MacKinnon's -3.34. The gate never closes an open position.
- Grid, on design data only: L in {126, 252, 504}, e in {1.5, 2, 2.5}, x in {0, 0.5}, giving 18 rules each for H4a and H4b. The best of each by design Sharpe after costs is validated once.
- Costs: 10 bps per unit of notional traded on each leg, paid on entry and exit. A position set at the close of day t earns day t + 1.
- Pass mark, for each of H4a and H4b: validation Sharpe after costs above zero. Two tests on the same validation data, reported as such. H1's validation Sharpe (0.06) is shown alongside for comparison but is not a pass mark.

## Amendment: Sortino ratios

Added 25 October 2026. Every rule also reports a Sortino ratio: the annualised mean daily net return divided by the annualised downside deviation, the square root of the mean of min(r, 0) squared over all days in the period. Reporting only; no pass mark uses it.

## H5: a copula correlation that tracks recent dependence (a direct edit to the fitted parameters)

Added 9 November 2026, after the H1 to H4 results were known and before any H5 validation result was computed. The method follows the "weight-space programming" idea of Takehi, Teoh, Zhang and Khattab (MIT, 2026), who had a language model read a network's weights, find a mechanism behind a flaw and edit the weights directly instead of retraining. Here the fitted parameters in `data/basket.json` (202 monthly fits: two ARMA-GARCH margins and a copula each) were read as text by a language model (Claude Fable 5.1) together with the design-period record and a fixed budget of looks at returns. Nothing is re-estimated; one coefficient per fit is replaced. The harness is `research/h5_weights.py`, which reproduces `data/h1_daily.csv` from the stored fits to within 1e-9 before any edit.

- Inspection, design period only (`research/h5_inspect.py`, `h5_inspect2.py`, `h5_inspect3.py`; `research/results/h5_inspection*.json`). The margins are calibrated out of sample (Kolmogorov-Smirnov p = 0.49 for SBK and 0.06 for the basket) but the conditional probability h is not (p < 0.001): its decile densities run from 0.76 to 1.27 against 1, and the rule fires on 7.5% of design days against the 10% the model implies, falling to 2.8% in 2019. Realised Kendall's tau of the out-of-sample PITs rose from 0.45 to 0.56 in 2010 to 2015 to 0.67 to 0.71 in 2016 to 2019, while the copula correlation, fitted on an expanding window from 2005, moved only from 0.727 to 0.751. The dependence parameter lags the data. A constant shift to the correlation, or any change to the degrees of freedom, does not calibrate h (p ≤ 0.003 for every candidate), because the error is time-varying. The first candidate edit, removing the near-cancelling ARMA(1,1) in the SBK margin (ar1 ≈ 0.80 and ma1 ≈ −0.85 in every fit), was rejected on design data: the term forecasts the next return (slope 0.74 on its own deviation) and without it the design Sharpe fell from 0.08 to 0.00.
- Edit. In each monthly fit the Student t copula keeps its family and degrees of freedom, and its correlation is replaced by sin(πτ/2), where τ is Kendall's tau of the last 252 training-day PITs under that month's fit (data available at the fit date). Everything else is H1's: the margins and their coefficients, the h-function, the 0.45 threshold, the five-day hold, the sizing and the costs. The window was chosen from {126, 252, 504} by the KS distance of h from uniform on design (0.0438, 0.0417, 0.0432), not by returns.
- Budget, logged in `research/results/h5_log.json`: three design-period return evaluations (H1 as fitted, the ARMA edit, this edit) and one validation run. On design the edit's Sharpe after costs is 0.15 (0.90 before costs) against H1's 0.08 (0.74), ahead by 37 bps a year with t = 0.49, and the rule fires on 9.3% of days, between 6.9% and 12.5% in every year.
- Pass mark: validation Sharpe after costs above zero and above H1's (0.06). The paired t-statistic against H1 on validation days is reported, as for H3 and H4, and so is the post-freeze record. One test on the validation data, but it is the fifth hypothesis family scored on it, and is read with that in mind.
- Reported but not tested: the calibration of h in validation under the fitted and the edited correlation, the firing rate by year, and the path of the edited correlation. The live service keeps the fitted correlation until this result is known.

## H6: a learned exit trained on every day, not only on trades

Added 9 November 2026, after the H5 result was known and before any H6 result was computed. Rationale: H3's exit models had 592 decision points because only days inside a real H1 trade counted. But the exit question ("is holding this spread one more day worth anything?") has an observable answer on every day for either direction, so the training set is flipped from traded days to all days, about thirty times more. News features are dropped (H3 found they added nothing), so training can start in 2010. The H5 edit comes along as a state variable: the calibrated conditional probability is a second reading of the same signal.

- Entries, hold, sizing and costs are exactly H1's; decision points, exits and the flat period after an exit are exactly H3's. The policy is only ever applied at real H1 decision points (held days one to four).
- Training episodes: every close t0 is a virtual entry in the direction sign(h(t0) − 0.5), held five sessions, with decision points at t0 + 1 to t0 + 4 whose outcomes are known by the training cut. Nothing selects which days become episodes.
- Features at close t, standardised on each training set: days held; the current fitted signal in the trade's direction, d(h − 0.5); the entry signal's strength |h(t0) − 0.5|; the same two for the H5 calibrated signal; the trade's gross return so far; today's held return; 20-session realised volatility of the SBK minus basket return; the last VIX close before the session.
- Model: fitted Q-iteration as in H3b, with a small network (two hidden layers of 16 units, ReLU, Adam, fixed seed) in place of ridge regression. Target: next held return plus max(0, predicted value at the next decision point), iterated four times. Exit when the predicted value of holding is below zero.
- Fitting: walk-forward, refitted at each year end from 2012 on all episodes whose outcomes are known by then; the first fit uses 2010 to 2012. Design is therefore 2013 to 2019. The L2 penalty is chosen once from {0.001, 0.01, 0.1} by the design-period Sharpe after costs.
- Pass mark: validation Sharpe after costs above zero and above H1's (0.06). Paired t-statistics against H1 and against H3b (0.14) on validation days are reported. This is the sixth hypothesis family scored on the same validation data.
- Reported but not tested: the same model without the two H5 features, to show what the edit adds; H1 and H3b over 2013 to 2019 for comparison; the share of decision points where the policy exits.

## Hourly study (descriptive)

Added 9 November 2026. 60-minute bars for SBK and NED from February 2009 to 2 June 2026 (a TradingView export kept in `data/raw/*_60m.csv`, not redistributed, and not refreshable, so nothing built on it can run live). `research/hourly_study.py` reports, on design data only: the realised intraday correlation by month against the yearly copula correlation; its persistence and distribution; and what the SBK minus NED spread does over the rest of the day and the next day after a large move in the first one to four hours. Descriptive, like the decay study; nothing is selected from it until a hypothesis is written below.

## H7: the intraday reversal of the SBK and NED spread

Added 9 November 2026, after the hourly study above and before any H7 return was computed. Rationale: on design data the spread's move over the first two trading hours after the 10:00 bar reverses by about 30 bps over the rest of the day when it is in its top decile (t ≈ −4.6), and the effect grew in 2015 to 2019 while the daily reversal faded. With half of capital on each leg that is about 16 bps a trade against a 20 bps round trip, so the threshold is left to design data.

- Data: the 60-minute bars (`data/raw/sbk_60m.csv`, `ned_60m.csv`; TradingView, bar `time` is the opening time, eight bars a day closing 10:00 to 17:00 SAST). Only days with all eight bars for both names are traded. The data ends 2 June 2026, so post-freeze is 1 April to 2 June 2026 and the rule cannot run live.
- Signal at the 12:00 close: the divergence D = log(SBK 12:00 / SBK 10:00) − log(NED 12:00 / NED 10:00). Open when |D| exceeds the q-th percentile of |D| over the previous 250 traded days (no same-day data). Direction: short SBK / long NED when D > 0, the reverse when D < 0. Half of capital on each leg. Close at the 17:00 bar close the same day. No overnight positions.
- Costs: 10 bps per unit of notional traded on each leg, so 20 bps of capital per round trip. The daily net return is the position's return from 12:00 to 17:00 less costs, zero on days without a trade. Sharpe and Sortino are annualised over all trading days, as elsewhere.
- Grid, on design data (2010 to 2019) only: q in {90, 95, 97.5}. The best by design Sharpe after costs is validated once (2020 to March 2026). Three design evaluations, logged in `research/results/h7_log.json`.
- Pass mark: validation Sharpe after costs above zero. The paired t-statistic against H1 on validation days is reported, as for H4, and is not a pass mark.
- Reported but not tested: figures before costs and at 5 bps per leg; the other two grid points in validation; results by year; the number of trades. Bar closes carry bid-ask bounce, which reverses mechanically, so part of the measured reversal is not tradeable; this is read as a limitation, not estimated.

## Model comparison on the SBK and NED pair (design only, then H8)

Added 9 November 2026. The validation years have now scored seven hypothesis families of trading rules, so no further trading rule is chosen on them. This exercise asks a different question of the same pair: which model of the two banks' joint daily returns forecasts best out of sample, and does a better instrument measure a different edge. Models are compared on design data (2010 to 2019, yearly refits at each December as in the pair's walk-forward) by the one-step-ahead log predictive density, which factors into two margin scores and one copula score, so margins and dependence models are compared separately. Calibration of the margins' PITs and of the conditional probability h is reported alongside. Candidates, declared before any score is computed:

- Margins: (a) the walk-forward's BIC-chosen ARMA-GARCH, the baseline; (b) Beta-t-EGARCH with leverage (a score-driven volatility model); (c) Realized GARCH on the daily realised variance from the 60-minute bars (available from February 2009, so compared from 2012); (d) two-regime Markov-switching GJR-GARCH with Student t errors.
- Dependence, on the baseline margins' PITs: (a) the static Student t copula refitted yearly, the baseline; (b) a Student t copula refitted on a rolling 252-day window at each month end; (c) a score-driven (GAS) Student t copula with time-varying correlation; (d) a two-state Markov-switching Student t copula.
- Scores: mean log predictive density per day over the design period; Diebold-Mariano tests against the baseline on daily score differences; KS tests of PIT and h uniformity. Nothing about trading is computed in this phase.

H8 is then written below, naming the best margin and best copula by design log score, before any validation score is computed: pass mark, a Diebold-Mariano improvement in the joint log score over the baseline at 5% in validation (2020 to March 2026). The H1-style rule's gross return per signal on the pair under the new instrument is reported alongside and is not a pass mark. Compute runs on this machine unless a model needs more; nothing here needs a cloud VM.

## H8: a score-driven Student t copula for the pair

Added 9 November 2026, after the design-period model comparison and before any validation score was computed. Design results (`research/results/copulas_design.json`, `margins_py.csv`, `margins_r.csv`): no margin model beat the baseline (all Diebold-Mariano |t| < 1.6), so the margins stay as they are. Among dependence models the GAS Student t copula had the highest design log score (+17.3 × 10⁻³ a day over the static copula, DM t = 6.5), just ahead of the two-state Markov-switching copula (+17.1 × 10⁻³, t = 6.1) and the rolling 252-day refit (+14.8 × 10⁻³, t = 3.0).

- Model: Student t copula on the baseline margins' PITs with correlation ρ_t = tanh(f_t), f_{t+1} = ω + β f_t + α s_t, where s_t is the score of the copula log density with respect to f_t (identity scaling). Degrees of freedom constant within a fit. Fitted by maximum likelihood on each fold's training PITs at the walk-forward's yearly refits, then filtered through the fold's trading year.
- Pass mark: Diebold-Mariano test of the daily log copula score against the static copula over validation (2020 to March 2026), Newey-West with five lags, significant at 5% in favour of the GAS copula.
- Reported, not tested: the Markov-switching and rolling copulas' validation scores (already computed by the same script, read once with the pass mark); calibration of h under each; post-freeze scores; and the gross five-day return per signal on the pair (|h − 0.5| > 0.45, half of capital a side, before costs) under the static and the GAS h, by period. The trading figure is a measurement, and it is not a pass mark because the validation years have already scored trading rules.

## H9: the score-driven copula on the basket instrument

Added 9 November 2026, after the H8 result and before any H9 score was computed. H8 showed the pair's dependence is better forecast by a GAS Student t copula. The instrument the write-up rests on is Standard Bank against the bank basket (H1), whose static copula H5 showed to be miscalibrated. H9 asks whether the same copula improves that instrument.

- Model: as H8, on the basket model's monthly fits (`data/basket.json`): the fold's margins unchanged, a GAS Student t copula fitted by maximum likelihood on each month's training PITs and filtered through the month it trades. 202 fits.
- Pass mark: Diebold-Mariano test of the daily log copula score against the static copula over validation (2020 to March 2026), Newey-West with five lags, significant at 5% in favour of the GAS copula.
- Reported, not tested: the Markov-switching copula's scores; h calibration under each; post-freeze; and the gross five-day return per signal (the write-up's headline measurement) under the GAS h by year. If H9 passes, the GAS copula becomes the instrument the write-up and the live service use, and the headline chart is re-measured with it; the trading rule itself does not change.

## Amendment: a JSE cost schedule (reporting only)

Added 9 November 2026. Every pre-registered verdict above was set at a flat 10 bps a leg (20 bps of capital a round trip) and stands. `research/costs.py` reports the same positions under a schedule of what trading the position on the JSE costs: brokerage plus 15% VAT, a half bid-ask spread, Strate settlement and the investor protection levy on each of the four executions in a round trip, and securities transfer tax of 0.25% of value on the two purchases (the long leg to open, the short leg to cover), with borrow on the short leg charged daily. Two tiers: institutional (10 bps brokerage, 5 bps half-spread, 1% a year borrow) and retail (25 bps brokerage, as EasyEquities charges). The half-spread and the borrow fee are assumptions and are varied. Also reported under each tier: the original report's exit, closing when the signal is back inside the 50th percentile, on the basket instrument. Nothing is chosen on these figures.

## H10: what each leg gets

Added 9 November 2026, before any H10 figure was computed. The rule sizes the two legs 1:1 by rand. The instrument already produces, every day, a volatility for each leg (the GARCH margins) and a correlation between them (the score-driven copula), so a sizing that minimises the variance of the position's return is arithmetic on numbers it already has. Three sizings, each fixed at entry for the life of the trade (a restart on a new signal re-sizes) and each with gross exposure one so costs compare:

- 1:1, half of capital a leg (the rule as registered);
- inverse volatility, each leg's weight proportional to one over its GARCH volatility on the entry day;
- minimum-variance hedge, basket weight to Standard Bank weight in the ratio ρ_t σ_SBK / σ_basket on the entry day, with ρ_t the score-driven correlation.

Pass mark: the minimum-variance hedge gives a lower realised variance of the position's daily gross return than 1:1 in validation (2020 to March 2026), by a Diebold-Mariano test on the daily squared-return differences (Newey-West, five lags) at 5%. This is a hedge-quality test, not a return test; the validation years are spent for return tests.

Reported, not tested: the inverse-volatility sizing; the position's beta to the equal-weight bank return under each sizing; gross return per signal over the five-day hold and the rule's Sharpe under each sizing at the three cost schedules, by period. Expectation stated now: sizing changes the risk of a trade, not its edge, and cannot carry a 21 bps signal over a 59 bps round trip. If H10 passes, the minimum-variance hedge becomes the instrument's sizing in the service and the headline chart, as the copula did after H9.

## Red team (reporting only, run once each)

Added 9 November 2026, before any of these figures was computed. A battery of attacks on the instrument's one result, each run once on an Azure VM and reported whatever it shows. Nothing is selected on them. Expectations are written here first.

1. Execution lag. The record assumes a fill at the close that produced the signal. Re-measure with the position taken at the next close (both instruments) and, for the pair, at the next 10:00 bar from the hourly data. Expected: the gross edge per signal falls by a third to a half, since the design-period edge is front-loaded on the first held day.
2. Causal cleaning. The bad-print rule drops a day if it reverses the next day, which the service cannot know at the close. Replace it with a rule that treats any one-day move beyond 40% as a bad print at once and carries the previous price. Expected: only the April 2025 print is affected and no figure moves.
3. Leave-one-year-out and leave-2020-out averages of the gross return per signal. Expected: the 2010 to 2019 figure survives at about 15 bps without its best year; the 2020 onward figure does not survive without 2020.
4. Placebo. 10,000 random entry sets with the same number of signals in each year and the same five-day hold; the percentile of the actual gross return per signal in that distribution, by period. Expected: above the 95th percentile before 2020, inside the distribution after.
5. Full basket costs. The basket leg is four shares rebalanced daily; charge that turnover at the institutional schedule, STT on the purchases. Expected: another 5 to 10 bps a round trip.
6. The overlay. For someone who must trade these banks anyway, the signal's value is the gross edge with no incremental cost: block-bootstrap confidence intervals by period and a sign test. Expected: positive and significant before 2020, not after.
7. Copula combination. The equal-weight mixture of the score-driven and Markov-switching copula densities, scored by out-of-sample log density against the score-driven copula alone, pair and basket. Expected: a gain of under 2 thousandths of a log point a day.

Untestable here and stated: Yahoo Finance adjusted closes are revised after the fact for dividends, so the series the model saw in any earlier year is not the one downloaded now. Point-in-time prices would be needed to measure it.

## Overlay (reporting only)

Added 9 November 2026, before any figure. The red team left one use standing: timing trades that someone has to do anyway, so the signal's value is collected at no incremental cost. Measured here at fills a real order can have.

- Setting: on every session t a manager must complete a relative trade between Standard Bank and the basket (half of each direction, so the measurement is symmetric) within a deadline of W sessions, W in {5, 10}. Baseline: fill at the close of t + 1. Overlay: fill at the close of the first session s in t + 2 to t + W whose previous close gave a signal in the trade's favour (h > 0.95 for buying Standard Bank against the basket, h < 0.05 for the reverse); if none, fill at the close of t + W. Placebo: fill at a uniformly random session in t + 1 to t + W.
- Value: the relative price improvement of the overlay fill against the baseline fill, in bps of the trade's notional, averaged by year and by period. The same for the pair (Standard Bank against Nedbank, the score-driven h) with fills at the 10:00 bar of the chosen session from the hourly data, which is the earliest a real order can act on a close.
- Expectation: a few bps a trade before 2020 and nothing since, bounded above by the lagged edge the red team measured (about 6 bps a signal on the basket, 11 on the pair at the next morning's price). Reporting only; nothing is chosen on it.
- Amendment, 9 November 2026, after the first run and before any figure was reported: the placebo, which carries no information, showed 2 to 7 bps of "improvement". That is Jensen's inequality in simple price ratios (x + 1/x ≥ 2 across the two directions), not timing. Improvement is measured in log prices instead, which is exactly antisymmetric and has expectation zero without information. Each session's value is the mean of its buy and sell trade; intervals are moving-block bootstraps (blocks of 20 sessions, 10,000 draws) because windows overlap. The value conditional on a signal arriving inside the window is also reported.
