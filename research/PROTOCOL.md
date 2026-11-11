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

## Re-centring on Standard Bank and Nedbank

Added 9 November 2026, before any of the new figures below was computed. The project began as Standard Bank against Nedbank, and that is what the write-up, the dashboard and every further optimisation are about from here. The basket instrument (H1, H3, H5, H9, H10 and the basket red team) stays in RESULTS.md as a record and leaves the page.

- Instrument: the pair's walk-forward margins (BIC-chosen ARMA-GARCH, refitted each December, frozen on 31 March 2026) with the score-driven Student t copula of H8, which passed its pre-registered forecast test (validation Diebold-Mariano t = 3.4). Signal h = P(NED ≤ v | SBK = u). The rule the measurement uses is the one H8 reported: open when |h − 0.5| > 0.45, long Standard Bank and short Nedbank when h > 0.5 and the reverse below, hold five sessions, a new signal restarts the count, half of capital a side. It is a fixed hold, not "until normal"; the hold-until-normal variant is reported once alongside, as for the basket.
- Already seen on the pair before this entry: the gross return per signal by period under the GAS h (H8: 22.8 bps in design, −19.6 in validation, −16.9 post-freeze on 8 signals); the lag attack's close-to-close and next-10:00 figures (26.9 and 11.0 bps, 2010 to 2019); the overlay at next-morning fills (2.8 bps at most, no interval excluding zero); the copula mixture (t = 1.25). These are not rerun for effect; they are restated.
- New, reporting only, each computed once: (1) gross per signal by year against the JSE round trip (`research/costs.py`, two single-name legs); (2) the rule's Sharpe by period at each cost tier; (3) red team on the pair: execution lag at the next close, causal cleaning on the two banks, leave-one-year-out, placebo with 10,000 random entry sets; (4) leg sizing (as H10: inverse volatility and minimum variance from the instrument's own forecasts, against 1:1). The validation years are spent for trading rules, so nothing here is a pass mark and no rule is changed by it.
- Expectations: about 20 to 25 bps a signal before 2020 and below zero since; placebo percentile above 95 before 2020 and near 50 since; no single year carries the design figure; a close of lag removes more than half of it; sizing changes little because the two banks' volatilities are close, and 1:1 stays.
- Live: the service runs the pair on the GAS copula from the final fold's fit, filtering every session after 31 March 2026 forward from the copula's state at the freeze. `research/models/export_pair_gas.py` writes that export, and a parity test checks it against the research filter.

## Amendment: trading the pair through derivatives (reporting only)

Added 9 November 2026, before any figure under these schedules was computed. The JSE cost schedule charges what trading the two shares costs. Securities transfer tax (25 bps on each purchase) and stock borrow on the short leg are about half of the 59 bps institutional round trip, and neither applies to a position held through JSE single stock futures or contracts for difference. `research/costs.py` adds two schedules for the same positions and the same gross returns:

- Single stock futures: the JSE equity derivatives exchange and clearing fees and broker commission (plus VAT) on each of the four executions, a half bid-ask spread wider than the cash market's, financing implicit in the futures basis charged as a funding spread over the benchmark on the long leg net of the short leg, and a roll cost when a hold crosses an expiry.
- Contracts for difference: commission per side (plus VAT), the provider's spread, and financing at benchmark plus the provider's margin on the long leg less benchmark minus the margin on the short leg, charged daily while held.

Fee and commission inputs come from published price lists dated November 2026, cited in `costs.py`. The half-spreads and funding spreads are assumptions and are varied. Interest earned on cash not posted as margin is ignored. Reported for each schedule: the round trip in bps of capital, the gross return per signal less the round trip by period, and the rule's Sharpe by period. Nothing is chosen on these figures, and the pre-registered verdicts at 10 bps a leg stand.

Expectation stated now: a round trip of 15 to 30 bps through either derivative. That would put 2010 to 2019 near breakeven, a few bps a signal either side of zero after a fill at the signal's close and below zero at the next close. The years since 2021 are negative before any cost (−6.5 bps a signal), so no schedule makes them positive.

## H11: a direct repair to the Nedbank margin, scored only on sessions after the freeze

Added 9 November 2026, before any edit was computed. Following the weight-editing result that H5 also followed (MIT, 2026: an edit to a fitted model's parameters removed one diagnosed fault and recovered ability the model already had; on a model without the fault it did nothing), this is a repair to one diagnosed fault in the pair's instrument. It is not a search for a better trading rule. The fault: Nedbank's walk-forward probability transforms fail a uniformity test at 5% in four of the 17 traded years (2010, 2012, 2015, 2019; RESULTS.md, "Margin calibration out of sample"), while Standard Bank's pass in all 17.

- Diagnosis, on design years (2010 to 2019) only, from the stored fits and data to each fold's year end: for each year, whether the Nedbank miss is in location (mean of the standardised residual), scale (its variance against one) or shape (tail frequencies against the fitted Student t).
- Candidate edits, each applied to the fitted coefficients of every fold without refitting, and each set from that fold's own training residuals so it stays walk-forward: (a) scale, multiplying Nedbank's conditional variance by the ratio of the training standardised residuals' variance to one; (b) shape, setting Nedbank's degrees of freedom from the training tail frequency beyond two standard deviations; (c) location, setting Nedbank's ARMA mean terms to zero. Standard Bank's margin and the copula's parameters are not changed.
- Choice, on design only: the edit that leaves the fewest design years failing the uniformity test, with ties broken by the design-period Nedbank log predictive density. It is kept only if that density is better than the unedited margin's by a Diebold-Mariano t above 2 (Newey-West, five lags). If none qualifies, H11 stops here and is reported as such.
- Check, on validation (2020 to March 2026): the edit must not worsen Nedbank's out-of-sample log density (Diebold-Mariano t above −1) or the joint copula log score. This is a forecast check, not a return test; no trading figure on 2020 to March 2026 is computed under the edit until after the freeze.
- Freeze and live score: if the edit passes both, it is frozen on 10 November 2026, and from 11 November 2026 the service runs the edited and the unedited instruments side by side on the same sessions. Reported live: the gross return per signal of each, and the net under the institutional and the cheaper derivative schedule. Verdict at 225 signals of the edited rule or on 31 December 2030, whichever comes first. Pass mark: the edited rule's net return per signal at the cheaper derivative schedule above zero with one-sided t above 1.65. At about 23 signals a year that is years away, and the page says so.
- Expectation stated now: the diagnosis finds a scale miss in the failing years, the scale edit fixes two or three of them, and the design log density improves only a little. Like H5, a correctly calibrated margin need not trade better. The prior is that it changes the record by less than its noise.
- Amendment to H11, 9 November 2026, before any edit was computed: the share of a unit-variance Student t beyond two standard deviations is not monotone in its degrees of freedom (it peaks at 4.98% near ν = 6.5), so edit (b) cannot be set from it. Edit (b) instead sets ν so that the share beyond three standard deviations matches the training residuals. That share is monotone for ν from 3.25 up, so ν is solved on [3.25, 500], capped at 3.25 if the training share is higher, and the fitted distribution is kept if the share is below the normal's.

## H12: a market volatility gauge in the pair's copula

Added 9 November 2026, before any H12 data was fetched or any score computed. The question: does a gauge of market volatility from outside the two banks tell the instrument when their joint tails will be heavier or their dependence stronger? The copula's correlation is driven today only by the pair's own recent returns, and its tail thickness is fixed within a fit. This is a test of the instrument, judged by forecast density, not a trading rule. Disclosed before registering: on design signals only (2010 to 2019), the gross five-day return per signal was split into thirds by the VIX before the session (21, 8 and 40 bps for calm, middle and volatile) and by the pair's own 20-session volatility (17, 10 and 37 bps), each third with a standard error of about 14. No other H12 figure has been seen.

- Gauges, each a number known before the session it is used for, logged and standardised on each fold's training years: (a) VIX, the last close before the session, as the margins already use it; (b) the rand, 20-session realised volatility of daily USDZAR log changes from Yahoo Finance (ZAR=X), to the last print dated before the session; (c) the JSE Top 40, 20-session realised volatility of the Satrix 40 ETF (STX40.JO, Yahoo Finance) to the previous close; (d) control, 20-session realised volatility of the equal-weighted SBK and NED return to the previous close. (d) asks whether any outside gauge adds to what the pair already shows. A gauge whose history does not cover 2005 to the present is dropped and reported as such.
- Model, for each gauge x: the H8 copula with both channels open, f_t = ω + β f_{t−1} + α s_{t−1} + γ x_t for the correlation ρ_t = tanh f_t, and ν_t = 2 + exp(η₀ + η₁ x_t) for the tail thickness. It nests H8 at γ = η₁ = 0. Fitted by maximum likelihood on each fold's training PITs at the walk-forward's yearly refits, starting from the fold's H8 fit, then filtered through the fold's trading year. Margins unchanged.
- Choice, on design only: the gauge with the highest mean design log copula score. It is kept only if it beats H8 on design by a Diebold-Mariano t above 2 (Newey-West, five lags). If none does, H12 stops and is reported as such.
- Pass mark, on validation (2020 to March 2026): Diebold-Mariano t of the chosen model's daily log copula score against H8 above 1.96. This is the second forecast comparison on these years (H8 was the first). That reuse is weaker than reusing them for a trading rule, and it is disclosed with the result.
- Reported, not tested: every gauge's design and validation scores; the fitted γ and η₁ by fold, which say which channel the gauge works through; calibration of h; post-freeze scores; the gross five-day return per signal under the new h and the net at the institutional cash and futures schedules, by period. The trading figures are measurements, not pass marks.
- If it passes: the chosen model becomes the instrument (`data/pair_gas.json`, the service, the dashboard and the page), as H8 did. Its trading record counts only from the live sessions after the change.
- Expectation stated now: VIX and the control both raise the design score, through the correlation channel more than the tail; an outside gauge adds little over the control; any validation gain is small. The gross edge since 2021 stays below zero, because a better forecast of dependence does not make the reversal return.

## Closing auction: can the signal's own close be caught? (reporting only)

Added 9 November 2026, before any figure was computed. The headline 23 bps a signal assumes a fill at the close that produced the signal, which cannot be known until that close. The realistic version: compute h from each bank's last trade by 16:00 (the close of the 15:00 to 16:00 hourly bar), then fill in the 16:50 to 17:00 closing auction at the official close.

- Pre-close signal: each margin's mean and volatility for the session are known before it opens, so the 16:00 return (16:00 price over the previous close, with that day's dividend adjustment) gives a 16:00 probability transform for each bank. The copula's correlation and degrees of freedom for the session are the H8 values already in use. The rule is unchanged: open when the 16:00 h is beyond 0.05 or 0.95, fill at the close, hold five sessions with half of capital a side.
- Reported: how often the 16:00 signal matches the close signal; the gross five-day return per signal filled at the close, against the close-signal figure; the net at the institutional cash and futures round trips. Design (2010 to 2019) is the headline. Validation and after are reported as measurements, as for the red team, because no rule is chosen. Hourly bars run from February 2009 to 2 June 2026, so later sessions are not covered.
- Expectation stated now: most close signals are already visible at 16:00, and the 16:00 signal filled at the close keeps between half and all of the 23 bps on design. It stays below the 59.6 bps cash round trip and near the 33.8 bps futures one.

## H13: two volatility variants scored only on live sessions

Added 9 November 2026, after H12 and the closing-auction check and before either variant was frozen. H12's control copula (the pair's own 20-session volatility as a gauge) lost on design and gained on validation, and the design split by VIX suggested the edge is larger in volatile markets. Neither can be chosen on the years already used, so both are scored only on sessions after 9 November 2026.

- A, the own-volatility copula: H12's model with gauge (d), fitted once on the final fold's training PITs (to 31 March 2026) by the H12 code and frozen with its gauge standardisation, then filtered forward from the freeze through the service's live margins. The rule is unchanged: open when |h − 0.5| > 0.45, hold five sessions, half of capital a side.
- B, the VIX gate: the H8 signal, opened only when the VIX before the session is above 17.10, the upper third of design signal days (the break disclosed under H12). Only gated signals restart the hold.
- Scored: every signal on a session from 10 November 2026, by its gross five-day return from the signal's close. Net at the institutional futures round trip (33.8 bps) and the institutional cash round trip (59.6 bps). The H8 rule's signals on the same sessions are reported alongside. Served at /api/shadow, kept off the dashboard and the page.
- Verdict for each at 225 of its signals or on 31 December 2030, whichever comes first. Pass mark: net per signal at the futures round trip above zero with one-sided t above 1.65. The close-signal fill is not tradeable (RESULTS.md, "Closing auction"), so a pass would be followed by the same 16:00 check before anything is claimed.
- Expectation stated now: neither passes. A generates about as many signals as H8, about 23 a year, so it is unlikely to have a verdict before 2030. B generates about eight a year, so its 2030 reading will rest on about 35 signals.

## H14: trade the spread while the long-run relationship holds, the copula when it breaks

Added 11 November 2026, before any H14 figure was computed. The user's idea, from the group poster (Mdingi and Makgopa, November 2026): Standard Bank and Nedbank are not cointegrated over the sample because the relationship breaks (six Bai-Perron breaks), but it holds in pieces (21% of two-year windows reject). So trade the spread the classic way while a cointegration relationship holds, and switch to the copula signal when a test says it is breaking. Already seen, and not rerun for effect: both halves have been scored on every period. H4b (the spread trade gated on Engle-Granger, 126 sessions, open past 1.5, close at 0) had a validation Sharpe of 0.45 on 10 trades. H8's rule (the score-driven copula, |h − 0.5| > 0.45, five-day hold) had a gross of −19.4 bps a signal in validation. The gate has been shut on every day since April 2026. A validation figure for the switch would recombine results already seen, so H14 is chosen on design, reported descriptively on validation, and judged only on live sessions.

- **The two methods, reused as they are.** Spread mode is H4b's trade: a rolling 126-session OLS of log NED on log SBK, z the last residual over the window's residual sd. Open past ±1.5, NED weight 1 / (1 + |b|) and SBK |b| / (1 + |b|) with b fixed at entry. Close when z is back to 0 on its own side, past ±4, or after 60 sessions. Copula mode is H8's rule on the instrument: open when |h − 0.5| > 0.45, long SBK and short NED when h > 0.5, hold five sessions, a new signal restarts the count, half of capital a side.
- **The switch.** Each close is in one mode. A spread spell starts at the first close on which the 126-session Engle-Granger statistic (H4b's: ADF on the window's residuals, one lagged difference, no constant) is below −3.34. It lasts until the detector below says the relationship has broken. Every other close is in copula mode. Only the current mode's method can open a position. On the close where the mode changes, the other method's open position is closed, and the new mode's method may open at that close. So there is at most one position at a time. A new spell needs a new rejection on a later close.
- **Detectors, declared now:**
  - E, H4b's gate: the spell ends on the first close the 126-session statistic is not below −3.34.
  - C, a CUSUM monitor (Chu, Stinchcombe and White, 1996). At the spell's first close t0, take the intercept and slope from the 126-session window ending at t0. The long-run residual sd is ω = σ_e / (1 − φ), from an AR(1) fit to that window's residuals. On each later close t0 + k, with S_k the sum of y − a − b x over t0 + 1 to t0 + k, the spell ends when |S_k| / (ω √126) > √((1 + k/126)(c² + ln(1 + k/126))).
  - B, Bai-Perron in real time: on each close s in a spell, the sup-F statistic for one break in intercept and slope on the anchored sample from t0 − 125 to s, with breaks searched over its middle 70%. The spell ends when sup-F > c.
- **Thresholds by simulation, calibrated on design data only (2010 to 2019).**
  - Calibration windows: every design close on which the 126-session test rejects.
  - From those windows, the median slope b and the medians of the residual AR(1) coefficient φ and innovation sd σ_e. SBK's log increments are resampled from its design daily log returns.
  - Stable DGP: y = b x + u with u an AR(1) at (φ, σ_e).
  - c for C and B is set so that a share α of stable spells end within 252 sessions of t0, for α in {0.05, 0.10}. Calibration and evaluation use separate seeds.
  - So there are five candidates: E, C05, C10, B05, B10.
- **Choosing the detector: how early it sees a break.** Each candidate is run on 1,000 simulated paths per scenario, each starting at a simulated spell's first close. Re-entries on new rejections are allowed throughout. Scenarios:
  - (s) stable for 252 sessions;
  - (h) the hedge ratio shifts by ±Δ 21 sessions after t0, with the line continuous at the break and Δ the median absolute slope change between adjacent Bai-Perron segments in `research/results/cointegration.json` (descriptive, already known);
  - (r) the residual becomes a random walk 21 sessions after t0 (cointegration lost);
  - (n) spurious onset: u is a random walk throughout, so the rejection that started the spell was chance.

  The score is the number of sessions in spread mode in the 252 after the break: from the break in (h) and (r), from t0 in (n). Eligible candidates keep spread mode on at least 90% of the 252 sessions in (s). The choice is the eligible candidate with the lowest mean of the three break-case scores. If none is eligible, E is used. Also reported: the median delay from the break to the first end of the spell.
- **Reported on design, for the chosen detector only:**
  - the share of sessions in spread mode by year;
  - the spread-mode sessions in the 252 after each Bai-Perron break that falls in design;
  - the switch's daily net returns, trades and Sharpe, with P&L by year split into spread-mode and copula-mode trades;
  - beside them, H8's rule alone and H4b alone, all under `research/costs.py`'s institutional cash schedule and `research/derivative_costs.py`'s institutional single stock futures schedule, extended to unequal legs. Each leg pays execution on its own change in exposure, STT on purchases (cash), borrow or funding on its own notional, and futures rolls at expiry.

  The same figures for 2020 to March 2026 are labelled "already seen" and are not a pass mark. The share of sessions in spread mode each year from 2010 to the latest session is reported for all five candidates.
- **Live score.** H14 is frozen on 11 November 2026 with the chosen detector and the H8 instrument as served. A trade is a position spell from open to close; a restart on the same side extends it, and a flip starts a new one. Scored: every trade opened on a session from 12 November 2026, at its net return under the institutional futures schedule (and, reported, cash). The H8 rule's trades on the same sessions, under the same definition, are reported beside it.
- **Verdict.** At 225 completed H14 trades or on 31 December 2030, whichever comes first. Pass mark: mean net return per trade at the institutional futures schedule above zero, with one-sided t above 1.65. The number of spread-mode trades is reported with the verdict. While no spell is running, H14 is H8, and a pass carried by copula-mode trades alone would be H8's result, not the switch's. If no spread-mode trade has been made by the verdict date, the verdict says there is no evidence on the switch.
- **Expectation stated now.**
  - C and B leave spread mode sooner than E after a break and stay longer in stable spells, so one of them is chosen.
  - On design, the switch is in spread mode on 10% to 25% of sessions, most in 2010 and 2011, and it does no better than H8's rule alone after real costs.
  - Today it is in copula mode, so live it is H8 and its verdict will take years.

## H15: will the gap close from here?

Added 11 November 2026, before any H15 label, forecast or return was computed. H14 stays frozen and is not changed. The user's brief: H14's gate says whether the relationship held over the last 126 sessions, which is too late to trade on; what a trade needs is whether it is holding now, a forecast. The only H15 figures seen before this was written are the step-4 decomposition below (descriptive) and the counts of available data.

**Change to the standing rule, for H15 only.** Every session to 31 March 2026, the old design years (2010 to 2019) and the old validation years (2020 to March 2026), is development data for H15. The validation years have already been seen through H4b, H8, H13 and H14, so holding them back would test nothing; the user's view is that the project's test was always the live record. No figure on data to 31 March 2026 is a test for H15. The only test is the live record from the session after the freeze. Development labels must resolve by 31 March 2026: a close is in development only if its 60-session horizon ends on or before that date.

**Step 4, reported before modelling (`research/h15_decompose.py`, descriptive).** Over the 126 sessions to 10 November 2026 the hedge ratio of log NED on log SBK is −0.0004 (below the 5th percentile of all windows since 2010), while daily-return correlation is still 0.65. Nedbank's own move net of the sector (mean of FirstRand and Absa, a reference only) is +9.8%, most of it in August; Standard Bank's is −1.5%. With Nedbank's own part removed the hedge ratio would be 0.62; with both removed, 0.94. The naira, shilling and cedi against the rand explain 4% of the variance of Standard Bank's own part.

- **The target, defined now.** On each close t, take the 126-session OLS of log NED on log SBK ending at t (H4b's window): intercept a_t, slope b_t, residual sd s_t, and z_t the residual at t over s_t. Hold a_t, b_t and s_t fixed and follow the frozen gap g_{t+k} = (y_{t+k} − a_t − b_t x_{t+k}) / s_t. The label Y_t is 1 if g reaches zero from z_t's side (g_{t+k} z_t ≤ 0) for some k in 1 to 60 before |g_{t+k}| exceeds 4, and 0 otherwise (stop first, or neither within 60). N = 60 is H4b's holding cap. Event closes are those with |z_t| > 1.5, the trade's entry, and only they are scored. Labels overlap for up to 60 sessions.
- **Sample.** Event closes from 3 January 2006 (the 126-session window and the 20-session features are full; prices from 2005) to the last close whose horizon ends by 31 March 2026.
- **Cross-validation, purged.** Five contiguous folds by date over the development closes. A fold's model is trained on the other folds, less every close within 60 sessions before the fold's first close (its label overlaps the fold) and within 60 sessions after its last (embargo). Every reported development score is out of fold.
- **Baseline, which must be beaten: Markov switching on a daily hedge ratio.** The hedge ratio is updated each close by recursive least squares of log NED on log SBK with intercept and forgetting factor 1 − 1/126 (memory matched to H4b, not tuned), started on 2005's first 126 sessions. The spread is e_t = y_t − a_t − b_t x_t on the estimates including t. Two states: reverting, e_t = φ e_{t−1} + σ_R ε; random walk, e_t = e_{t−1} + σ_W ε, ε standard normal, with a 2×2 transition matrix. Parameters by maximum likelihood on each training fold (the Hamilton filter runs over the whole record, so each filtered probability uses data to t only; the likelihood sums the training closes only). The forecast input is the filtered P(reverting | data to t).
- **Forecast models, each a logistic regression with standardised inputs and a fixed L2 penalty (C = 1, not tuned).**
  - Z: |z_t| only (reference).
  - G, H14's gate as a forecast: |z_t| and the 126-session Engle-Granger statistic.
  - M, the baseline: |z_t| and P(reverting).
  - X, the external model: M's inputs plus five, chosen on economic grounds now:
    1. Africa: the absolute 20-session log change of the rand against an equal-weight basket of the naira, Kenyan shilling and cedi (Yahoo; the kwanza has no history there). Standard Bank's Africa earnings move with these and Nedbank has none.
    2. Results ahead: sessions until the next 1 March or 1 August (both banks report finals in March and interims in August), divided by 60, capped at 1, and 0 during March and August. Known in advance.
    3. Dividend gap: the absolute difference between the two banks' dividend growth, each the log of its latest dividend over the one a year before, available from its ex-date (Yahoo dividend events).
    4. Rand volatility: the 20-session sd of daily log changes in USDZAR.
    5. Rate cycle: the six-month change in the OECD South African immediate rate (FRED IRSTCI01ZAM156N, monthly), each month's value used from two months after it.
  - XN, development only: X plus news imbalance, the absolute difference of log(1 + articles on Standard Bank only) and log(1 + articles on Nedbank only) over the last 20 sessions, from the GDELT counts already made for H2b. GDELT starts on 18 February 2015, so XN is scored against M refitted on the same closes from 1 April 2015. No live news feed exists without new BigQuery queries, so XN cannot be traded or frozen; it says only whether news would have helped.
  - That is five specifications, and no others will be fitted. Company events with a single instance, such as Old Mutual's 2018 unbundling of its Nedbank stake, are too few to learn from and are not features.
- **(a) Forecast skill, the gate to everything else.** Scores on event closes, out of fold: mean log score and Brier score for every model. Test: d_t = log score of X minus log score of M on each event close, mean d over its Newey-West standard error with 60 lags on the sequence of event closes. X beats the baseline if mean d > 0 and t > 1.65. If it does not, H15 stops there: no trading rule is chosen, nothing is frozen, and that is the result. XN against M, and M against Z and G, are reported the same way.
- **(b) Only if X beats the baseline: the trading rule.** Spread mode on each close where X's probability p_t > θ, copula mode otherwise. Spread mode runs H4b's trade unchanged (open past ±1.5, close at 0 on the rolling z, past ±4 or after 60 sessions, b fixed at entry); an open spread trade runs to its own exit when the mode ends, and the copula rule cannot open meanwhile. Copula mode is H8's rule, as in H14. θ is chosen from {0.50, 0.55, …, 0.80} on 2010 to March 2026 with X's out-of-fold probabilities, as the highest mean net per trade at the institutional single stock futures schedule among values with at least 20 spread trades; ties go to the lower θ. Costs are `service/app/switch.py`'s schedules (`research/costs.py`, `research/derivative_costs.py`). Reported beside it on the same sessions: H14's switch and the copula rule alone, at cash and futures, by year. All of these are development figures.
- **(c) Freeze and live score, only if (b) is reached.** X is refitted on every development close, θ is fixed, and the rule is frozen on a date written into this section before its first live session. Scored: every trade opened on a session after the freeze, at institutional futures (cash reported), beside H14 and the copula rule on the same sessions. Verdict at 225 completed trades or on 31 December 2030, whichever comes first: pass if mean net per trade at institutional futures is above zero with one-sided t above 1.65; the number of spread trades is reported with it, and if none has been made the verdict says there is no evidence on the forecast.
- **Overfitting, stated now.** The independent stretches where the relationship held are few (2011 to 2013, 2018, 2022, 2024), so overlapping event closes overstate the information: the Newey-West correction is the only allowance for it, and it may not be enough. Five specifications in total, plus θ's seven values if (b) is reached.
- **Expectation stated now.** M beats Z by a little. X does not beat M: the step-4 decomposition shows Africa FX explaining almost nothing of today's gap, and the other inputs are slow. If so, H15 stops at (a).

## H16: H4b's spread trade under a looser long-run gate, flat otherwise

**Registered after the exploration, on purpose.** `research/explore_gap.py` searched development data (every session to 31 March 2026, H15's rule) for a forward-looking spread rule: 54 specifications, all listed in `research/results/explore_gap.json`. This rule was chosen from them, so every development figure for it is selected and none is a test. The only test is the live record.

- **The rule, frozen 11 November 2026.** On each close, the 126-session OLS of log NED on log SBK and the Engle-Granger statistic of its residuals, as in `service/app/switch.py`. The gate is open while the statistic is below −2.8. While it is open, H4b's trade runs unchanged: open when the rolling z passes ±1.5; close when the rolling z returns to 0, passes ±4, or after 60 sessions; weights NED 1/(1+|b|) and SBK |b|/(1+|b|), with b fixed at entry. An open trade runs to its own exit when the gate shuts. While the gate is shut and no trade is open, the book is flat. There is no copula leg.
- **Why −2.8.** Cutoffs of −2.0, −2.4, −2.6, −2.8, −3.0, −3.34 and −3.6 were tried at the 126-session window. Every value from −2.4 to −3.6 gave t above 2.2 at futures. −2.8 was the highest (t 3.58), and it sits in the middle of that range. The window (126), entry, exit, stop and hold are H4b's, fixed in October 2026, and were not chosen here. The 63- and 252-session windows were weak and were not chosen.
- **Live scoring.** Every trade opened on a session from 12 November 2026, at the institutional single stock futures schedule (cash reported), from `service/app/switch.py`'s SCHEDULES. H14's switch and the copula rule alone are reported beside it on the same sessions.
- **Verdict.** At 40 completed trades or on 31 December 2036, whichever comes first. Pass if mean net per trade at futures is above zero with one-sided t above 1.65. 40 trades gives about 80% power if the true mean is the development 91 bps with sd 226 bps. Development opened about four trades a year, and none while the gate stays shut: on 9 October 2026 the statistic was −0.98, and it was last below −2.8 on 6 May 2026. Figures are reported each year until the verdict, with no verdict before it.
- **Expectation stated now.** Development figures overstate the rule: 54 specifications were tried, and the multiple-testing allowance alone takes the one-sided 5% bar to about t 2.9. A live mean nearer 40 to 60 bps per trade would not be a surprise.

## Amendment, 11 November 2026: one unseen date for H14 and H16

At the user's request, H14 and H16 are scored on every trade opened on a session from 1 April 2026, not from 12 November 2026. One date now marks unseen data for all three strategies on the dashboard, and the copula rule (H8) was already scored from 1 April. The freezes stand as recorded: H14 and H16 were frozen on 11 November 2026, and nothing in either rule changes. The verdict rules are unchanged. H14 still stops at 225 completed trades or 31 December 2030, and H16 at 40 or 31 December 2036. Trades opened from 1 April count towards those totals.

**What the earlier start costs.** Both rules were chosen using data only to 31 March 2026. But they were written in November, after April to November had happened, and parts of that period had been looked at. So April to November is unseen by the fitting and the selection, but not by the researcher. Checked before this amendment was written, on prices to 10 November 2026:

- **What was seen.**
  - H14's registration states that the gate had been shut on every day since April 2026.
  - H14's run reported its April to November figures after the detector was chosen. The detector was chosen by simulation on design data. The switch was in copula mode throughout, at −56.4 bps a trade at futures.
  - H15's step 4 described the 126-session hedge ratio to 10 November and Nedbank's own move net of the sector. The move was +9.8%, most of it in August.
  - H16's registration states that the statistic was last below −2.8 on 6 May 2026.
- **What H16 did in the window.** The gate was open on one session, 6 May 2026 (statistic −2.91), and the rolling z that day was −0.82. H16 opened no trade.
- **Could the window have steered −2.8?** The cutoff was chosen as the highest t at futures in `research/explore_gap.py`. That script scored only trades closed by 31 March 2026, and no cutoff's April to November trades were computed before the freeze. Computed now, the looser cutoffs would have traded in the window and lost:
  - −2.6: one trade, opened 21 April, −52.7 bps at futures.
  - −2.4: two trades, opened 10 April (−80.5 bps) and 28 August (still open, −203.5 bps).
  - −2.0: the 28 August trade.
  - −3.0 and below: no trades, the same as −2.8.

  So the window flatters the chosen cutoff against the looser ones. That was not the reason for the choice, but it cannot be ruled out entirely, because the gate's state in the window was known.
- **What H14 did in the window.** The statistic never went below −3.34, so the switch never entered spread mode. Its 7 trades from 1 April are the copula rule's own trades, so its record there adds nothing beyond the copula rule's.

For these reasons, any live result from April to 11 November 2026 is reported with this caveat. A verdict that hinges on those months should be read as weaker than one carried by trades opened after the freeze.

## H17: when the models refit

Added 11 November 2026, before any H17 refit or score was computed. The user's request: the models and the strategies should refit from time to time, with the data and events deciding when, and the procedure should be part of the strategy. The only H17 figures seen before this was written are timings (one ARMA-GARCH fit about 1.3 s, one GAS copula fit about 3 s on the Mac).

- **What has fitted parameters, and so what a refit touches.** The spread trade (H4b, H14's spread mode, H16) has none: its slope, z and Engle-Granger statistic are re-estimated on the trailing 126 sessions at every close, and its cutoffs (1.5, 0, 4, 60 sessions, −2.8, −3.34) are frozen rules, not estimates. A refit changes only the copula signal h, through two pieces: each bank's ARMA-GARCH margin, and the GAS t copula on their PITs. The copula rule's cutoffs (|h − 0.5| > 0.45, five-session hold) and H14's detector do not change. No procedure here re-chooses a trading rule.
- **What a refit does.** On the close of its date T, using sessions to T only: (1) each margin's parameters are re-estimated by `rugarch` (hybrid solver) under the specification in force; (2) PITs to T are filtered from the first session with those parameters (`research/h5_weights.py`'s `_filter_full`); (3) the GAS copula is refitted on those PITs (`research/models/copulas_py.py`'s `gas_fit`, started at the static t copula's correlation from the latest yearly selection); (4) `export_pair_gas.py`'s state step gives the first session after T. The new parameters apply from the session after T. If a margin fit does not converge, the previous parameters stay in force and this is recorded. The specification (model, ARMA order, distribution, VIX term) is reselected by BIC over `research/lib.R`'s 36-specification grid only at year ends, as in the walk-forward. Reselecting at every trigger would cost about 26 s a refit and is not tried locally.
- **Candidates, all checked only at month-end closes.** Every candidate keeps the year-end refit with reselection; the triggers add parameter refits between year ends.
  - Y, the baseline: year ends only (the current walk-forward, 2009 to 2025).
  - Q: Y plus every quarter end.
  - M: Y plus every month end.
  - K, drift: Y plus each month end where either margin's out-of-sample PITs since the refit in force (at least 63 sessions) fail a Kolmogorov-Smirnov test of uniformity at p < 0.05.
  - E, the relationship: Y plus each month end in whose month the 126-session Engle-Granger statistic crossed −2.8 or −3.34 in either direction.
  - R, results: Y plus the ends of March and August, after the banks' finals and interims.
  A real-time Bai-Perron trigger is not a candidate: H14's simulation already found the Engle-Granger gate a usable break signal on this pair, and E uses it.
- **History check, development data only.** Every price after 31 March 2026 is deleted before any fit. Refits happen at month ends from 31 December 2009 to 28 February 2026; scores run from the first session of 2010 to 31 March 2026. On each session, the score uses the parameters from the latest refit before it. Yearly refits reproduce `research/results/copulas_py.csv`'s gas_t h (parity, required before any comparison).
  - The measure: the joint out-of-sample log predictive density of the two returns each session, the two margins' log densities plus the GAS copula's log density. d_t is a candidate's minus Y's. The test is the mean of d over its Newey-West standard error with 21 lags.
  - A candidate beats Y if mean d > 0 and t > 2.33, a one-sided 1% bar (Bonferroni for five candidates). Also reported for every candidate: the margin and copula parts of d separately; the number of refits; the copula rule's trades and mean net per trade at the institutional futures and cash schedules (`service/app/switch.py`), alone and inside H14; and the KS p-values of h and both margins' PITs.
  - The choice: among candidates that beat Y and whose copula rule does not lose more per trade at futures than Y's, the one with the highest mean d; if none does, Y. A tie (means within one standard error of each other) goes to the candidate with fewer refits. Whatever is chosen, every candidate's figures are reported, including those that did worse.
- **Live.** The chosen procedure runs from the first session after the user switches it on, never retroactively, so the record from 1 April 2026 to that day stays on the fit of 31 March 2026. Each refit is written to a dated record with the data it used. The dashboard keeps serving the parameters in force until a person deploys the new ones.
- **Expectation stated now.** Most of the margin's day-to-day drift is already absorbed by GARCH and the copula's by the GAS recursion, so extra parameter refits help a little at most. Y or Q is chosen, and no trading figure moves by more than a few bps a trade.
