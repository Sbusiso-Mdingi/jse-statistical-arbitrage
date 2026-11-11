# Results

Results of the tests in `PROTOCOL.md`, computed 13 October 2026 (H3 the same day, after its protocol entry; H4 on 25 October, H5, H6 and H7 on 9 November, each after its protocol entry). All figures are annualised, after 10 bps per leg unless stated, from `data/research.json`. Post-freeze runs from 1 April 2026 and is reported only: to 9 October for v1, H1, H3, H5 and H6, to 23 October for the five-day hold, H2 and H4, which read the price cache directly, and to 2 June for H7, where the hourly data ends.

## Standard Bank against Nedbank: the instrument from 9 November

The project is about Standard Bank and Nedbank, and from 9 November 2026 so is the write-up (PROTOCOL.md, "Re-centring"). The instrument is the pair's yearly walk-forward margins, frozen on 31 March 2026, with the score-driven Student t copula that passed H8. Everything here was computed once by `research/pair.py` into `research/results/pair.json`, after the protocol entry. It is reporting only; nothing is a pass mark. The basket sections below stay as the record.

**Margin calibration out of sample.** Computed once on 9 November 2026 for the write-up, from the stored walk-forward history (`data/walkforward.json`): a Kolmogorov-Smirnov test of each traded year's probability transforms against uniform. Standard Bank passes at 5% in all 17 traded years. Nedbank passes in 13 and fails in 2010, 2012, 2015 and 2019 (p 0.022, 0.018, 0.008, 0.023), so it is the weaker margin. Over the validation years together Nedbank passes (p 0.16) and Standard Bank is borderline (p 0.047). The per-fold `pit_ks` in the export is in-sample and is not this test.

**What a signal was worth.** Over a five-day hold, half of capital a side, before costs:

| | Signals | Gross per signal | Standard error | Next session alone |
| --- | --- | --- | --- | --- |
| 2010 to 2019 | 225 | 22.8 bps | 8.2 | 14.9 bps |
| 2020 to 2026 | 141 | -19.4 | 16.5 | -3.2 |
| 2021 to 2026 | 122 | -6.5 | 15.6 | 3.2 |

On the fixed copula the same figures are 28.4 and -11.7 bps. A round trip costs 20 bps at the protocol's brokerage, 58.6 at the institutional JSE schedule and 94.5 at retail. The edge before 2020 was about a third of the real cost. Since then it has been below zero, and 2020 was the worst year, −102.8 bps a signal on 19 signals: the pair's reversal broke in the crash, where the basket's paid.

**The rule at each cost.** Sharpe ratios, five-day hold:

| | Before costs | 10 bps a leg | Institutional | Retail |
| --- | --- | --- | --- | --- |
| Design, 2010 to 2019 | 0.82 | 0.18 | -1.16 | -2.32 |
| Validation, 2020 to March 2026 | -0.21 | -0.69 | -1.68 | -2.55 |
| Post-freeze, to 2026-10-09 | -0.5 | -0.96 | -1.88 | -2.65 |

At institutional costs the walk-forward returns -8.1% a year; holding half of each bank returned 6.4%. Holding until the signal is back inside its 50th percentile, instead of five days, averages 2.0 days over 303 trades. It is better before costs in design (Sharpe 1.14) and worse after them everywhere (institutional walk-forward Sharpe -2.32).

**Red team on the pair.**

1. **Execution lag.** Filled at the next close, the 2010 to 2019 figure falls from 22.8 to 10.6 bps, and two closes late to 7.8. At the next morning's 10:00 bar it is 11.0 (restated from the red team). Expectation was more than half; it was a little over half.
2. **Causal cleaning.** The causal rule flags the same Standard Bank print (2025-04-25) the current rule removes, and nothing on Nedbank. As expected.
3. **Leave-one-year-out.** Without 2015, the best design year, the 2010 to 2019 figure is 20.0 bps. Without 2020, the 2020 onward figure is -6.5 bps. As expected.
4. **Placebo.** Against 10,000 random entry sets with the same signals per year, 2010 to 2019 sits at the 99.9th percentile (placebo sd 7.3 bps), 2020 onward at the 8.4th and 2021 onward at the 30.0th. As expected: real before 2020, nothing since.
5. **Overlay.** Restated from the overlay section: timed at the next morning's price, at most about 3 bps a trade, with no interval excluding zero.

**Leg sizing.** On validation, against 1:1:

| Sizing | Mean Standard Bank weight | Position variance against 1:1 | DM t |
| --- | --- | --- | --- |
| Inverse volatility | 0.505 | 1.041 | -1.22 |
| Minimum variance per unit of Standard Bank | 0.589 | 1.177 | -2.12 |
| Minimum variance per unit of gross | 0.506 | 1.058 | -1.51 |

Every alternative makes the position more variable, not less, because the two banks' volatilities are close. 1:1 stays, as expected.

Verdict. On Standard Bank against Nedbank the instrument measures the same story as on the basket, more sharply. A reversal worth about 23 bps a signal existed before 2020 and was real against placebo. It was always below the 59 bps an institutional round trip costs, half of it disappears with a realistic fill, and since 2020 it has been negative.

## Every rule tested

| Rule | Design Sharpe | Validation Sharpe | Validation Sortino | Validation CAGR | Validation max drawdown | Post-freeze Sharpe | Pass mark | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| v1, report rule (SBK/NED) | 0.11 | −0.70 | −0.91 | −2.8% | −20.6% | −1.71 | | Baseline |
| Five-day hold at q90 (SBK/NED) | 0.40 | −0.58 | −0.77 | −3.8% | −22.8% | −2.39 | > 0 | Failed (validated before this protocol) |
| H1, SBK against bank basket | 0.08 | 0.06 | 0.10 | 0.2% | −15.1% | −2.31 | > 0 and > −0.70 | Passed, narrowly |
| H2a, skip busy volume days | 0.50 | −0.04 | −0.06 | −0.3% | −7.9% | −1.84 | > 0 and > −0.58 | Failed |
| H2b, skip GDELT news days | −0.10 | −0.13 | −0.19 | −0.8% | −10.4% | −1.56 | > 0 and > −0.58 | Failed |
| H3a, learned exit, classifier | −0.28 | 0.08 | 0.13 | 0.3% | −14.8% | −2.14 | > 0 and > 0.06 | Passed, within noise |
| H3b, learned exit, fitted Q-iteration | −0.14 | 0.14 | 0.22 | 0.6% | −13.2% | −2.00 | > 0 and > 0.06 | Passed, within noise |
| H4a, classic z-score trade (NED/SBK) | 0.63 | 0.07 | 0.10 | 0.2% | −24.4% | no trades | > 0 | Passed, within noise |
| H4b, classic trade, cointegrated windows only | 0.40 | 0.45 | 0.67 | 2.3% | −7.9% | no trades | > 0 | Passed, within noise |
| H5, copula correlation edited to track recent dependence | 0.15 | −0.23 | −0.35 | −1.8% | −20.7% | −1.59 | > 0 and > 0.06 | Failed |
| H6, network exit trained on every day | 0.23 | 0.21 | 0.35 | 1.0% | −10.5% | −1.08 | > 0 and > 0.06 | Passed, within noise |
| H7, intraday reversal on hourly bars (SBK/NED) | −0.31 | −0.60 | −0.80 | −2.0% | −16.9% | 1 trade | > 0 | Failed |

Sortino ratios (added by amendment 5) use the downside deviation over all days. H1 over the full walk-forward: Sortino 0.11.

H1 before costs: Sharpe 0.74 in design and 0.64 in validation (CAGR 3.4% and 3.6%). The signal holds up out of sample but the edge is about the size of the costs. Over the full walk-forward, 2010 to March 2026, H1 returned 0.3% a year (Sharpe 0.08, max drawdown −15.1%, 262 trades, average hold 4.8 days); holding SBK and the basket returned 10.5% a year. All 202 monthly copula fits chose the Student t, with Kendall's tau between 0.50 and 0.57.

Both news filters cut losses in validation mainly by trading less. Neither cleared zero.

## H3: learned exits

H3 design is 2017 to 2019, where plain H1 had a Sharpe of 0.07; both exit models did worse there. 592 decision points from May 2015, of which the models exited at 4% (H3a) and 13% (H3b) in validation. Regularisation chosen on design: C = 0.01 for H3a, alpha = 10 for H3b.

Both clear the pre-registered mark in validation, but the gain over H1 is 10 bps a year for H3a (paired t = 0.24) and 40 bps a year for H3b (t = 0.68), nowhere near distinguishable from chance, and two models were tried on the same validation data. The classifier without the news features did better in validation (Sharpe 0.12) than with them (0.08), so the GDELT and volume features added nothing measurable. Read as: no evidence that news or sentiment tells you when to leave these trades.

## Cointegration and H4: the classic trade

`research/04_cointegration.R` repeats the group report's tests on data to March 2026. SBK and NED are each integrated of order one (ADF on levels −0.03 and −1.99, on differences −26.1 and −32.1). They are not cointegrated: Engle-Granger −1.77 in price levels and −2.61 in logs, against −3.34 at 5%; Johansen trace 8.66 and maximum eigenvalue 6.82 in levels, far below their 5% values of 19.96 and 15.67; the design period alone gives the same answer. The one near miss is Phillips-Ouliaris in logs on the full sample, 33.55, which rejects at 10% (27.85) but not at 5% (33.71). The report's own figures (Engle-Granger −1.65, trace 8.57) differ slightly, most likely from the lag choice in the residual ADF.

The relationship holds only in pieces. Two-year windows stepped monthly reject at 5% in 21% of 234 windows, mostly in 2009 and 2010 and none from 2015 to 2019. Allowing one break does not rescue it (Gregory-Hansen −3.71 with a level shift, −3.98 with a regime shift, against −4.61 and −4.95). Bai-Perron finds six breaks in the log regression, with the hedge ratio moving between 0.49 and 1.61. This is why the project models daily dependence with a copula instead.

H4 trades the classic way anyway, so the copula has a fair comparison. Chosen on design: H4a a 126-session window, open past 2.5, close inside 0.5; H4b a 126-session window, open past 1.5, close at 0. Both clear their pre-registered mark. H4b's validation figures are the best of any rule here (Sharpe 0.45 after costs, 0.51 before, CAGR 2.3%, max drawdown −7.9%, in the market 10% of days), but they rest on 10 trades, 8 of them winners.

Read it as within noise, for four reasons. Against H1 on paired daily returns, H4b is ahead by 202 bps a year with t = 0.62 (H4a: 19 bps, t = 0.05). Across all 18 H4b rules the median validation Sharpe is 0.03, half are positive (−0.74 to 0.83), and the design ranking does not predict the validation ranking (correlation −0.01; H4a 0.07). H4a and H4b were both validated on the same data. And since April the Engle-Granger gate has been open on no day at any window length, so neither rule has traded post-freeze. The honest summary: the classic method, gated on cointegration, did no worse than the copula rules in validation and possibly better, but it trades rarely and only while the relationship briefly holds.

## H5: editing the fitted parameters directly

The idea comes from Takehi, Teoh, Zhang and Khattab (MIT, 2026), who had a language model read a small network's weights, find the mechanism behind a flaw and edit about 0.016% of the weights by hand, with no retraining, and saw its maths scores rise sixfold. The analogue here: the 202 monthly fits in `data/basket.json` were read as text by a language model with the design-period record and a budget of looks at returns, logged in `research/results/h5_log.json` (three design evaluations, one validation run). `research/h5_weights.py` re-filters every walk-forward month from the stored coefficients and reproduces `data/h1_daily.csv` to within 1e-9, so an edit changes exactly one thing.

Two mechanisms were found on design data. The first was a false lead: every SBK margin carries an ARMA(1,1) with ar1 ≈ 0.80 and ma1 ≈ −0.85, roots that nearly cancel, which usually means an over-parameterised mean. But the term is a slow reversal forecast (half-life 2.7 days) that does predict the next return (slope 0.74), and zeroing it cut the design Sharpe from 0.08 to 0.00. The second held up: the margins are calibrated out of sample (KS p = 0.49 for SBK, 0.06 for the basket) but the conditional probability h is not (p < 0.001). Too many values sit near 0.5 and too few in the tails, so the rule fired on 7.5% of design days against the 10% the model implies, and on only 2.8% of days in 2019. Realised Kendall's tau between the out-of-sample PITs rose from about 0.5 in 2010 to 2015 to about 0.7 in 2016 to 2019, while the copula correlation, estimated on an expanding window from 2005, moved from 0.727 to 0.751. The one dependence weight lags the data. No constant shift and no change to the degrees of freedom calibrates h, because the error grows through time.

The edit replaces the correlation in each fit with the value implied by Kendall's tau of that fit's last 252 training-day PITs, keeping everything else. On design it does what it was meant to: the rule fires on 9.3% of days, between 6.9% and 12.5% in every year, and the Sharpe after costs rises from 0.08 to 0.15 (0.74 to 0.90 before costs, max drawdown −12.7% to −8.7%), 37 bps a year ahead of H1 with t = 0.49.

In validation it fails. The mechanism is still there, and the edit still corrects it: the edited correlation runs 0.79 to 0.91 against the fitted 0.76 to 0.78, h is closer to uniform (KS p from 0.000 to 0.010), and the rule fires on 12.4% of days. Before costs the Sharpe is 0.48, positive but below H1's 0.64. After costs it is −0.23 against H1's 0.06, 191 bps a year behind with t = −1.17, with 151 entries against 104 and a −20.7% drawdown. Post-freeze it is −1.59 against H1's −2.31, on ten trades. Read as: the fitted correlation was wrong, and correcting it made the model honest and the strategy poorer. The extra signals the corrected model admits are moderate divergences that revert by less than a round trip costs, so the under-dispersed h was working as an accidental higher threshold. This is consistent with the MIT result's own caveat: a direct edit can remove an identifiable flaw, but it cannot put in an edge that is not there. The live service keeps the fitted correlation.

## H6: a learned exit trained on every day

H3's exit models had 592 decision points, because only days inside a real trade counted. H6 flips the training set: every close is a virtual entry in the direction of that day's signal, held five sessions, so the value of holding one more day is observed on every day. That gives 17,082 decision points from 2010, of which 976 are real H1 decision points. News features are dropped, a two-layer network (16 and 16 units) replaces ridge regression inside the same fitted Q-iteration, and the H5 calibrated signal joins the fitted one as a state variable. Refitted each year end from 2012; design is 2013 to 2019, where plain H1 had a Sharpe of 0.26. The L2 penalty 0.01 was chosen on design from {0.001, 0.01, 0.1} (0.21, 0.23, 0.20).

H6 clears the pre-registered mark: validation Sharpe 0.21 after costs (Sortino 0.35, CAGR 1.0%, max drawdown −10.5%) against H1's 0.06 and H3b's 0.14, exiting at 19% of real decision points and in the market 24% of days against H1's 31%. Post-freeze it is −1.08 against H1's −2.31. It is 76 bps a year ahead of H1 on paired validation days with t = 0.95, and it was 30 bps a year behind H1 in design (t = −0.33), so read it as within noise, and as the sixth hypothesis family scored on the same validation data. The ablation is the interesting part: without the two H5 features the same model scores 0.19 in validation but 0.00 in design. The calibrated signal that failed as a trading rule in H5 is the state variable that made the exit policy coherent across both periods. The policy's exits are not costless in the H1 sense once a position is re-opened by a later signal, and that cost is charged.

## Hourly study and H7: the reversal moved inside the day, and costs ate it

The 60-minute bars (TradingView, February 2009 to 2 June 2026, eight bars a day, not redistributed and not refreshable) answer two questions the daily data cannot. First, dependence drifts rather than switches: the realised intraday correlation between SBK and NED by month runs from about 0.3 to 0.8 with a month-to-month autocorrelation of 0.65 and a one-humped distribution, and its yearly mean climbs from 0.48 in 2010 to 0.68 in 2019, the same rise H5 found in the copula's residuals. A two-state regime model is the wrong shape for this; a time-varying correlation is the right one. Half of the daily spread variance (47%) is overnight, so a close-to-close copula averages two different processes. Second, the reversal the daily rules were built on is alive inside the day: on design data, when the spread's move over the two hours after 10:00 is in its top decile it reverses by about 31 bps by the close (t = −4.6), and the effect grew from −20 bps in 2010 to 2014 to −44 bps in 2015 to 2019 while the daily reversal faded.

H7 trades it: open at 12:00 against a two-hour divergence beyond a trailing 250-day percentile, close at 17:00, half of capital a leg, 10 bps a leg. Design chose the 95th percentile from {90, 95, 97.5} (after-cost Sharpe −0.37, −0.31, −0.31; before costs 1.54, 0.89, 0.56). The chosen rule fails validation: Sharpe −0.60 after costs, 0.33 before, −0.13 at 5 bps a leg, 93 trades with a 31% hit rate and a gross of 7 bps a trade against 15 bps in design. The other two grid points score −1.26 and −0.04 in validation. Against H1 on common validation days it is 240 bps a year behind (t = −0.95). Post-freeze is one trade. Read as: the intraday reversal is real and statistically strong before costs, it has shrunk by half since 2020 like everything else here, and at any plausible cost it is not tradeable from hourly bars. Part of the measured move is bid-ask bounce on bar closes, which reverses mechanically and cannot be earned; that was flagged before the run and is not estimated.

## Model comparison on the pair, and H8: a score-driven copula

With the validation years spent for trading rules, the pair's models were compared on a different target: the one-step-ahead log predictive density, which factors into two margin scores and a copula score. Yearly refits as in the pair's walk-forward; design 2010 to 2019; Diebold-Mariano tests on daily score differences with Newey-West (five lags). Scripts in `research/models/` and `research/08_margins_r.R`.

**Margins.** Nothing beats the walk-forward's BIC-chosen ARMA-GARCH. Per day, relative to it, on design: Beta-t-EGARCH −2.8 × 10⁻³ (SBK) and +2.9 × 10⁻³ (NED); Realized GARCH on the hourly-bar realised variance (from 2012) −4.4 and +4.2; two-regime Markov-switching GJR-GARCH −4.5 and −2.8. Every |t| is below 1.6. The margins were never the problem.

**Dependence.** Every time-varying copula beats the static Student t on design, by 14.8 × 10⁻³ a day for a rolling 252-day refit (t = 3.0), 17.1 for a two-state Markov-switching t copula (t = 6.1) and 17.3 for a score-driven (GAS) t copula (t = 6.5). The Markov-switching fit is the regime story: two correlation states near 0.62 and 0.83, with staying probabilities above 0.98 in recent fits, so regimes last for hundreds of days. The GAS copula, best by a hair on design, was registered as H8.

| Copula, pair | Design log score vs static (×10⁻³/day) | Validation (×10⁻³/day) | Validation DM t | h KS p, validation | Signals fire |
| --- | --- | --- | --- | --- | --- |
| Static Student t (baseline) | 0 | 0 | | 0.025 | 7.0% |
| Rolling 252-day Student t | +14.8 | +10.6 | 1.43 | 0.494 | 10.2% |
| GAS Student t (H8) | +17.3 | +19.7 | **3.43** | 0.313 | 8.5% |
| Markov-switching Student t | +17.1 | +20.9 | 3.74 | 0.462 | 8.4% |

H8 passes its pre-registered mark. Post-freeze (131 days) shows no difference between any of them, as expected on that little data. The reported trading measurement, the gross five-day return per signal on the pair before costs: 28 bps on design and −27 in validation under the static copula; 23 and −20 under the GAS copula (standard errors 8 and 17). A better-calibrated instrument reads the same thing the basket instrument reads: the reversal between the two banks has been absent since 2020.

## H9: the score-driven copula becomes the instrument

The same comparison on the basket instrument's 202 monthly fits (`research/models/h9_basket_gas.py`, results in `copulas_basket_*.json`). On design the GAS copula scores +23.8 × 10⁻³ a day over the static one (DM t = 6.9) and the Markov-switching copula +21.5 (t = 6.8). In validation, the one test: GAS +26.4 × 10⁻³ a day, DM t = 3.97, pass; Markov-switching +24.8 (t = 4.03), reported. The conditional probability is calibrated under the GAS copula in validation (KS p = 0.14; static 0.000) and fires on 9.5% of days against the model's 10%. Post-freeze (131 days) separates nothing.

As the protocol said it would, the GAS copula is now the instrument: `research/models/export_gas.py` writes `data/basket_gas.json` (the GAS h for every walk-forward day and the latest fit's parameters and state), the service filters new sessions through it (`service/app/model.py`, `gas_filter`; parity test against the research record in `service/tests/test_parity.py`), and the headline measurement is re-made with it. Latest fit, to 30 September 2026: ω 0.020, β 0.981, α 0.032, ν 7.8, ρ 0.757 at the training end.

Re-measured: a signal was worth 21.0 bps over the five-day hold from 2010 to 2019 (213 signals, standard error 7.5) and 1.6 bps since 2021 (135 signals, standard error 9.2), against the 17.8 and 1.0 read by the static copula. Same answer, more signals, tighter errors. The H1 rule run on the GAS h, reported and not a pass mark: Sharpe after costs 0.06 in design, 0.15 in validation (0.77 before costs), −1.42 post-freeze; against the same rule on the static h it is 55 bps a year ahead in validation with t = 0.36. The rule was validated on the static instrument (0.06); the figure on the new instrument is a measurement.

## What it costs to trade on the JSE

The protocol's 10 bps a leg is brokerage and nothing else. A round trip of the pairs position is four executions at half of capital each, and two of them are purchases, which pay securities transfer tax of 0.25% of value. With brokerage at 10 bps plus VAT, a 5 bps half-spread, Strate and the levy, and 1% a year of borrow on the short leg, the institutional round trip is 58.6 bps of capital: brokerage 23.0, STT 25.0, spread 10.0, Strate and levy 0.6, borrow about 0.99 over a five-day hold. At retail brokerage of 25 bps it is 94.5 bps. Varying the half-spread between 2 and 10 bps and the borrow between 0.5% and 3% a year moves the institutional figure between 52.6 and 68.6 bps. STT alone, 25 bps, is more than the 21 bps a signal was worth before costs from 2010 to 2019.

| Costs | Round trip | Sharpe, design | Sharpe, validation | Sharpe, 2010 to Mar 2026 | Return a year |
| --- | --- | --- | --- | --- | --- |
| Protocol: 10 bps a leg, flat | 20.0 bps | 0.06 | 0.15 | 0.1 | 0.4% |
| JSE, institutional | 58.6 bps | -1.41 | -1.16 | -1.3 | -6.7% |
| JSE, retail brokerage | 94.5 bps | -2.62 | -2.33 | -2.49 | -12.7% |

The rule on the score-driven instrument, reported. The original report's exit, closing when the signal is back inside the 50th percentile instead of after five sessions, holds for 2.0 days on average over 314 trades and does worse at every cost: Sharpe -0.72 at the protocol's costs and -2.85 at institutional costs over the full walk-forward. More trades, more round trips.

Sources: SARS for the STT rate; EasyEquities for the 0.25% retail commission; Standard Bank's AutoShare Invest for a 0.15% brokerage reference. Strate and the levy are taken from broker fee schedules as about a basis point per execution at retail size and less at institutional size. The half-spread and borrow fee could not be sourced for these two shares and are stated assumptions.

## H10: what each leg gets

The rule sizes the legs 1:1 by rand. H10 asked whether the instrument's own volatilities and correlation give a better sizing, judged on what sizing is for: the realised variance of the position. It fails. The registered minimum-variance hedge (basket to Standard Bank in the ratio ρσ_SBK/σ_basket, scaled to gross one) puts slightly more into Standard Bank (mean weight 0.516) and raises the position's validation variance by 11.5% (Diebold-Mariano t = -2.24, the wrong way at 5%); on design it raised it by 8.2% (t = -4.28). Inverse-volatility sizing (reported) changes the variance by +2.7% (t = -0.74). A post-hoc variant, not registered, that minimises variance subject to gross exposure one rather than per unit of Standard Bank, changes it by +3.5% (t = -0.87). The 1:1 position already has a beta of 0.024 to the equal-weight bank return in validation; there is nothing left for a hedge ratio to remove.

Returns, reported: gross return per signal from 2010 to 2019 is 21.0 bps at 1:1, 20.2 inverse-volatility and 19.7 minimum-variance; since 2021, 1.6, 6.2 and 0.1, all within a standard error of about 9 of each other. Validation Sharpe at institutional costs: -1.16, -1.04 and -1.12. As expected beforehand, sizing moves the risk of a trade and not its edge, and no sizing carries a signal over the cost of a round trip. The 1:1 sizing stays.

## Red team

Seven attacks declared in the protocol with their expectations, run once on an Azure VM (`research/redteam.py`, results in `research/results/redteam.json`).

1. **Execution lag.** This is the one that lands. Filled at the close that produced the signal, a signal was worth 21.0 bps from 2010 to 2019. Filled at the next close, 5.6 bps (standard error 7.1); two closes late, 11.5. The edge sits in the first held day, and the first held day is the one a real order cannot have. On the pair, where the hourly bars give a next-morning price, close-to-close was 26.9 bps and filled at the next 10:00 bar 11.0. The rule's design Sharpe at the protocol's costs goes from 0.06 to -0.49 with one close of lag. Expectation was a third to a half; it was three quarters.
2. **Causal cleaning.** A rule that flags any one-day move beyond 40% at the close, without seeing the next day, flags the same Standard Bank print (2025-04-25) and one more: Capitec on 2020-03-20, a real fall in the COVID crash that the current rule correctly keeps. No other day differs. As expected.
3. **Leave-one-year-out.** Without 2020 the 2010 to 2026 average per signal falls from 19.9 to 13.5 bps. Without 2015, the best design year, the 2010 to 2019 figure is 14.0 bps. As expected: the pre-2020 edge is not one year, the post-2020 edge is.
4. **Placebo.** Against 10,000 random entry sets with the same count of signals in each year and the same hold, the actual 2010 to 2019 figure sits at the 99.9th percentile (placebo mean 0.0, sd 6.6); 2020 onward at the 98.1th, carried by 2020; 2021 onward at the 57.2th, which is nothing. Random direction on the signal's own days gives the same picture. As expected.
5. **Full basket costs.** Daily rebalancing of the four-share leg turns over 0.72% of the basket a day and costs 0.6 bps a round trip at the institutional schedule, 10.3 bps a year. Smaller than expected; it does not change the cost picture.
6. **The overlay.** For someone who must trade these banks anyway, the signal's 2010 to 2019 value was 21.0 bps a signal with a block-bootstrap 95% interval of 8.2 to 34.8 and 57% of signals positive (sign test p = 0.0548). Since 2021 the interval is -22.7 to 21.8. And the lag attack applies here too: the overlay is only worth having if the trade can be done at the close.
7. **Copula combination.** The equal-weight mixture of the score-driven and Markov-switching copula densities gains 0.51 thousandths of a log point a day over the score-driven copula on the basket in validation (t = 0.32) and 1.36 on the pair (t = 1.25). Under the 2 expected; no ensemble is warranted.

Verdict. The instrument survives every attack on its honesty: the signal is real before 2020 against placebo, no single year carries it, the cleaning is not the story and the basket costs are not the story. It does not survive the attack on its practicability. A fill one session after the close removes about three quarters of a 21 bps edge that was already below the 25 bps of securities transfer tax on a round trip. As a trading strategy it cannot stand on its own; as a measurement of a reversal that existed, was never tradeable after costs, and has since gone, it stands.

## Overlay

Reporting only (`research/overlay.py`, results in `research/results/overlay.json`). A manager who must make a relative trade between Standard Bank and the basket within W sessions waits for a signal in the trade's favour and fills at the next close, or at the deadline if none comes; the baseline fills at the first possible close. Value is the log price improvement over the baseline, in bps of notional, averaged over the buy and the sell each session; intervals are block bootstraps.

| | 2010 to 2019 | 2021 to 2026 | Random-day placebo, 2010 to 2019 |
| --- | --- | --- | --- |
| Basket, 5-day window | 0.3 bps [-0.7, 1.3] | -0.4 [-1.7, 1.0] | 0.0 |
| Basket, 10-day window | 2.5 [-0.3, 5.4] | 0.6 [-4.3, 5.2] | -1.3 |
| Pair at the next 10:00 bar, 5-day window | 1.0 [-0.2, 2.0] | 0.0 [-2.1, 1.9] | 1.0 |
| Pair at the next 10:00 bar, 10-day window | 2.8 [-0.6, 5.7] | 1.6 [-4.5, 7.4] | 0.2 |

A favourable signal arrives inside the window for 16% of trades at five days and about a third at ten. Every interval includes zero, in both periods. The figure for trades where a signal does arrive (about 47 bps on the basket) is not a value: the signal fires because the price has already moved the trade's way since the baseline fill, so conditioning on it selects that move. Expectation was a few bps before 2020 and nothing since; the point estimates match, but none is distinguishable from zero.

Verdict. Timed at a price a real order can have, the instrument is worth at most about 3 bps a trade to someone trading these banks anyway, and that cannot be told apart from nothing. It does not earn a use as an overlay either.

## Decay study

Mean one-year lag-1 autocorrelation of the daily return spread across the 15 pairs of SBK, NED, FSR, ABG, CPI and INL: about −0.16 in 2011, close to zero from 2020 (−0.01 at the start of 2026). The SBK/NED next-day return after an extreme copula signal averaged about 16 bps from 2010 to 2019 and about −6 bps since 2020. This is the most likely reason every reversal rule weakens after 2019.

## Amendments and corrections

Every one of these was made before the affected verdict was known, or changed no verdict.

1. **H1 threshold.** The protocol first gave the opening threshold as |h − 0.5| > 0.40, a typo for the 90th percentile (0.45). Amended before any H1 result was computed.
2. **H2b data source.** Changed from the GDELT DOC API to the GDELT 2.0 knowledge graph on BigQuery before any H2b result was computed. The 60-day median needs a warm-up, so the H2b design period starts on 13 May 2015, not 18 February.
3. **H2a rolling median.** The first run took the median of the previous 60 consecutive sessions and needed all 60 to have volume, so holiday gaps left most pre-2018 days unflagged. Corrected to the last 60 sessions with data. Only design figures changed; the validation verdict did not. The first-run output is not used anywhere.
4. **Period boundaries.** Both the service and the research scripts first restarted flat at the start of each period, charging a fresh entry and dropping the first held day. Returns are now computed on the full record and then sliced, so positions carry across boundaries. No verdict changed; H1 post-freeze moved from −2.49 to −2.31.

5. **Sortino ratios and H4.** Added to the protocol on 25 October 2026, before any H4 result was computed. Adding Sortino changed no other figure in H1, H2 or H3. Rerunning H2 extended its post-freeze figures to 23 October; design and validation figures are unchanged.

6. **H5.** Added to the protocol on 9 November 2026 after the design-period inspection and before the validation run. The inspection used three design-period return evaluations, all logged; the ARMA edit it rejected is reported above rather than dropped.

7. **H6.** Added to the protocol on 9 November 2026 after the H5 result and before any H6 result. The first run crashed while writing its daily CSV, after the results JSON was saved; the line was fixed and the deterministic run repeated, producing a byte-identical JSON. No paired comparison with H3b is given because H3's daily positions were not stored.

8. **Hourly study and H7.** The hourly study was added as descriptive on 9 November 2026 and H7 registered after it, before any H7 return was computed. The first H7 run crashed on an indexing error before any figure was computed or logged; the line was fixed and the script run once.

9. **Model comparison and H8.** Candidates declared on 9 November 2026 before any score; H8 registered after the design comparison and before any validation score. The validation scores of the other two copulas were produced by the same script run and are reported, not tested. The first copula run was started with a training-length bug that made every PIT undefined; it was stopped before producing output, fixed, and rerun.

10. **H9.** Registered after the H8 result and before any H9 score. The reported rule figures on the GAS h are logged in `research/results/h5_log.json` with the other looks at returns. Switching the service and the headline chart to the GAS copula was written into the protocol before the test.

11. **Cost schedule.** Added 9 November 2026 as reporting only. No verdict uses it; the pre-registered marks stay at 10 bps a leg.

12. **H10.** Registered before any figure. The gross-constrained minimum-variance variant was added after the registered test failed and is labelled post hoc; it changes nothing.

13. **Red team.** Seven attacks declared with expectations on 9 November 2026 before any figure, run once on an Azure VM, reported in full. The expectation for the execution lag understated it.

14. **Overlay.** Registered 9 November 2026 before any figure. The first run measured improvement in simple price ratios, and its placebo showed 2 to 7 bps with no information: Jensen's inequality, not timing. Amended to log prices and block bootstraps before any figure was reported; the first-run output is not used anywhere. Ran in seconds on the Mac, so no VM was used.

15. **Re-centring on the pair.** Registered 9 November 2026 before any new pair figure, listing the pair figures already seen. `research/pair.py` was run once, then rerun with two descriptive additions (the next-session figure by year and the fixed copula's edge) and the cost output reshaped; every other figure was byte-identical between the two runs. Ran in seconds on the Mac.

16. **H14.** Registered 11 November 2026, detector rule written before the simulation. `select` was run once; `run` was rerun after the first, and the reruns only added the frozen export and its reference figures, every other output identical. The first parity check read the wrong key for the futures Sharpe; it was a lookup error, fixed before any H14 figure was reported. Ran in under a minute on the Mac.

17. **H15.** Registered 11 November 2026 before any label or fit; the forecast script was run once. Yahoo has no kwanza history, as the registration noted before the run. A dividend skipped (Nedbank in 2020) is compared with the dividend before it; the registration had not covered that case, and the rule was set before the run.

18. **H16.** Registered 11 November 2026 after `research/explore_gap.py` was run, as the registration says. The script was rerun once to add the walk-forward, window, entry and sector checks to one record; the first run's figures were unchanged.

19. **H14 and H16 scored from 1 April 2026.** At the user's request on 11 November 2026, both are scored on trades opened from 1 April 2026, not 12 November, so one date marks unseen data for all three strategies. The freezes, the rules and the verdict rules are unchanged. The months from April to 11 November were unseen by the fitting and selection but not by the researcher; `research/PROTOCOL.md` (amendment of 11 November 2026) lists what was seen. On prices to 10 November, H16 opened no trade in that window. Looser cutoffs (−2.4, −2.6) would have opened trades there and lost, which flatters −2.8.

## H11: a direct repair to the Nedbank margin

Stopped at the design stage, as the protocol requires: no edit qualified, so nothing was frozen and no edited instrument runs live. The harness reproduces the stored walk-forward Nedbank transforms to 1e-10.

| Edit, set from each fold's training residuals | Design years failing at 5% | Design log density gain, thousandths a day | DM t |
| --- | --- | --- | --- |
| None | 2010, 2012, 2015, 2019 | | |
| Scale | the same four | 0.17 | 3.74 |
| Shape (ν from the share beyond 3 sd) | the same four | 0.56 | 1.43 |
| Location (ARMA terms to zero) | the same four | −0.71 | −0.53 |

No edit fixes a single failing year. The rule chose the shape edit (all tie on failing years; it has the best design density), and its gain has t = 1.43, short of 2, so H11 stops. The scale edit's t of 3.74 is on a gain of 0.17 thousandths a day, and it was not the edit the rule chose.

The diagnosis says why. In 2010 the miss is scale: the realised variance of the standardised residual was 0.63, the model expecting post-crisis volatility that did not come; the training residuals' variance is 0.995 in that fold, so nothing set from training data can see it. In 2015 and 2019 the miss is location: 60% and 57% of days fell below the forecast median, the years Nedbank drifted down (December 2015's rand and finance-minister shock; 2019's derating). 2012 is a little of both. These are changes between training and test, not a flaw in the fitted parameters. In the weight-editing study the edit worked where there was a built-in fault to remove and did nothing where there was none; this margin is the second case. The expectation written in the protocol, that a scale edit would fix two or three of the years, was wrong.

## Trading the pair through derivatives (reporting only)

`research/derivative_costs.py` reprices the same positions through single stock futures and CFDs. These carry no transfer tax and no stock borrow; financing is charged as the spread over JIBAR while a position is held. Fees come from the price lists of November 2026, cited in the script; the assumptions are marked. Capital is R250,000, R125,000 a leg. A round trip is one open and one close over a five-day hold. No hold reached an expiry, so no roll was paid.

| Route | Round trip, bps | Net a signal 2010–19 | Net since 2021 | Sharpe, design | Sharpe, validation |
| --- | --- | --- | --- | --- | --- |
| Cash, institutional (with borrow) | 59.6 | −36.8 | −66.1 | −1.16 | −1.68 |
| Cash, retail | 95.5 | −72.7 | −102.0 | −2.32 | −2.55 |
| Futures, institutional (commission 5 bps and half-spread 10 assumed) | 33.8 | −11.0 | −40.2 | −0.28 | −1.03 |
| Futures, Standard Bank online (R50 + 0.4% in the price) | 94.4 | −71.6 | −100.9 | −2.29 | −2.53 |
| Futures, PSG (0.4% + 0.1% + VAT) | 116.3 | −93.5 | −122.7 | −2.90 | −3.02 |
| CFD, IG (0.20%, half-spread 5 and borrow 1% assumed) | 62.0 | −39.2 | −68.4 | −1.23 | −1.74 |
| CFD, Sharenet (0.30%, min R115) | 84.0 | −61.2 | −90.4 | −1.96 | −2.28 |

Net figures are taken at the signal's own close (gross 22.8 bps before 2020 and −6.5 since 2021). At the next close the gross is 10.6 and −3.3, and every route is negative in both periods. The futures dealer's half-spread and commission are varied from 5 to 20 and 2 to 10 bps. The round trip runs from 16.9 to 65.3 bps. The best case, a 5 bps half-spread and a 2 bps commission, leaves +5.9 bps a signal before 2020 and −23.3 since 2021.

The registered expectation, a round trip of 15 to 30 bps through either derivative with 2010–19 near breakeven, held only for institutional futures at the narrow end of the assumed spreads. The JSE's own futures fee is 0.55 bps, but no SBK or NED futures traded on 6 November 2026, so the price a dealer would quote is the real cost and it is not published. Retail futures and CFDs cost as much as cash or more, because the commission and the spread the market maker builds in replace the transfer tax. No route makes the rule pay since 2021, because the edge itself is below zero before costs.

## H12: a market volatility gauge in the pair's copula

`research/models/h12_gauge.py`, `research/results/h12.json`. **Stopped at design: no gauge beat H8.** The Top 40 gauge was dropped before fitting, because Yahoo's Satrix 40 history starts in January 2009, not 2005. Four rand prints were dropped as one-day spikes that reverse. The refitted H8 reproduces the stored H8 scores to 5 × 10⁻⁷.

| Gauge | Design gain a day (×10⁻³) | DM t | Validation gain | DM t | Post-freeze gain | DM t |
| --- | --- | --- | --- | --- | --- | --- |
| VIX | −1.41 | −1.39 | −0.71 | −1.22 | +1.03 | 1.15 |
| Rand volatility | −1.19 | −1.58 | −0.23 | −0.57 | +0.79 | 0.68 |
| The pair's own volatility (control) | −6.21 | −2.78 | +3.97 | 2.12 | +4.45 | 1.08 |

Every gauge improves the fit on its own training years, by 0.1 to 13 log points over several thousand days, and loses on the year that follows. Two things the fitted coefficients show:
- **The correlation channel.** The gauge's effect on correlation (γ) is clearly positive only in the early, short-sample folds. From 2016 on it is near zero, and the score-driven correlation's own persistence (β about 0.99) carries what the gauge would add.
- **The tail channel.** η₁ is positive, so a higher gauge means more degrees of freedom: thinner joint tails, not heavier ones. Each bank's GARCH margin already scales for volatility, so after that standardisation the joint extremes are no heavier when markets are volatile.

The idea that the two banks' tails should widen with market volatility is absorbed by the margins; it is not missing from the copula.

The registered expectation was wrong in direction. VIX and the control lower the design score; they do not raise it. The pair's own gauge scores DM t = 2.12 on validation, but the rule chose on design and it lost there (t = −2.78), so it is not adopted. Choosing it now would be choosing on validation. The page and the service are unchanged.

## Closing auction: can the signal's own close be caught? (reporting only)

`research/closing_auction.py`, `research/results/closing_auction.json`. The signal is recomputed from each bank's 16:00 price (the 16:00 return correlates 0.95 with the day's close-to-close return) and filled at the official close. The close-signal h is reproduced to 5 × 10⁻⁹.

| Design, 2010 to 2019 | Signals | Gross a signal (bps) | Net, cash institutional | Net, futures institutional |
| --- | --- | --- | --- | --- |
| Close signal, filled at that close (not tradeable) | 223 | 24.3 (se 8.1) | −35.3 | −9.5 |
| 16:00 signal, filled at the close | 176 | 11.7 (se 9.4) | −47.9 | −22.1 |
| Close signals not visible at 16:00 | 102 | 35.8 (se 10.9) | −23.8 | +2.0 |

Only 121 of the 223 close signals show at 16:00 on the same side. The ones that don't are the best: they form in the last 50 minutes and the auction, and the reversal that pays comes from that late move. A tradeable version keeps about half the edge, 11.7 bps before costs, at the low end of the registered expectation (half to all). It falls further below both round trips than the headline figure did.

On validation the 16:00 signal earns −38.8 bps (se 21.8) against −18.7 for the close signal. The bars end on 2 June 2026, and no signal fell in the covered sessions after the freeze. The headline 23 bps is the instrument's measurement; a trader acting before the close would have had about 12.

## H13: two volatility variants scored only on live sessions

Frozen on 9 November 2026 (`research/models/export_shadow.py`, `data/pair_shadow.json`). Served live at `/api/shadow` from dashboard v10, and scored on signals from 10 November 2026. A, the own-volatility copula, refits the final fold to γ = 0.0069 and η₁ = 0.108, H12's last-fold values. The service's filter matches the research filter (`tests/test_parity.py`). B gates the H8 signal on a VIX above 17.10.

Since the freeze, before scoring began, A's h has correlated 0.999 with H8's: A fired 9 times to H8's 10, and B fired twice. A will hardly ever separate from H8. Verdict at 225 signals each or on 31 December 2030.

## H14: the spread while the long-run relationship holds, the copula when it breaks

Registered 11 November 2026 before any figure (`research/h14_switch.py`, engine `service/app/switch.py`). Spread mode is H4b's trade, copula mode H8's rule, both unchanged; the only new choice was the break detector, made on simulated pairs calibrated to design. Thresholds: CUSUM c = 7.66 (5%) and 5.98 (10%), real-time sup-F 47.6 and 41.4. Mean spread-mode sessions in the 252 after a break:

| Detector | Stable | Hedge-ratio shift | Residual becomes a random walk | Spurious spell | Break score |
| --- | --- | --- | --- | --- | --- |
| E, the 126-session Engle-Granger gate | 246.8 | 213.9 | 40.8 | 19.8 | 91.5 |
| C05, CUSUM at 5% | 251.9 | 247.3 | 155.7 | 209.1 | 204.0 |
| C10, CUSUM at 10% | 251.9 | 244.8 | 142.2 | 195.7 | 194.2 |
| B05, sup-F at 5% | 251.7 | 211.1 | 63.9 | 56.5 | 110.5 |
| B10, sup-F at 10% | 251.3 | 207.7 | 58.5 | 48.5 | 104.9 |

All five kept at least 90% of stable sessions; E has the lowest break score and was chosen. The expectation that C or B would be chosen was wrong: both are anchored to the spell's first window and keep trading a relationship the rolling gate has already dropped, and the CUSUM barely sees a hedge-ratio shift at all.

Parity: the copula half alone reproduces H8's design Sharpe at the institutional cash and futures schedules (−1.16, −0.28) and the spread half alone H4b's 22 design trades and Sharpe 0.40 and 0.45 at 10 bps a leg.

| Period | Spread-mode share | Switch Sharpe, gross / cash / futures | Copula alone | Switch net a trade, futures | Copula alone | Switch minus copula, futures |
| --- | --- | --- | --- | --- | --- | --- |
| Design, 2010–2019 | 17.3% | 0.80 / −0.94 / −0.18 (170 trades, 23 spread) | 0.82 / −1.16 / −0.28 (189) | −6.1 bps | −8.4 bps | +54 bps a year, t 0.54 |
| Validation, already seen | 14.1% | −0.13 / −1.58 / −0.96 (105, 12 spread) | −0.21 / −1.68 / −1.03 (103) | −39.9 bps | −42.7 bps | +33 bps a year, t 0.25 |

Validation (2020 to March 2026) had been seen through both halves before H14 and is not a test. Spread-mode trades netted +44.5 bps each at futures in design (+19.8 cash) and +23.8 in validation; the copula-mode trades lost. The switch helps by about the spread trades' few wins, within noise. From April to October 2026 the gate never held, so the switch equalled the copula rule trade for trade.

Spread-mode share by year: 2010 3%, 2011 30%, 2012 57%, 2013 38%, 2014 1%, 2015 0%, 2016 5%, 2017 4%, 2018 25%, 2019 10%, 2020 7%, 2021 6%, 2022 26%, 2023 8%, 2024 26%, 2025 15%, 2026 0.5%. After the design Bai-Perron breaks: 133 spread sessions in the 252 after March 2011, 5 after February 2015, 9 after February 2019. On 10 November 2026 the statistic is −1.40 against −3.34, the 126-session hedge ratio about 0, the method copula; the last spread session was 30 January 2026.

Frozen 11 November 2026 (`data/pair_switch.json`), served at `/api/switch` from dashboard v11, scored on trades opened from 12 November 2026 at institutional futures with cash reported and H8's trades beside it. Verdict at 225 completed trades or 31 December 2030: pass if mean net a trade is above zero with one-sided t > 1.65. If the gate stays closed, the switch is the copula rule, and no spread trade by the verdict means no evidence on the switch. Outputs: `research/results/h14_select.json`, `h14.json`, `h14_daily.csv` (statistic, hedge ratio, mode and daily net by date), `h14_by_year.csv`.

## H15: will the gap close from here? Stopped at the forecast test

Registered 11 November 2026 before any label or fit (`research/h15_forecast.py`, inputs from `research/h15_data.py`). For H15 only, all data to 31 March 2026 is development data and no figure on it is a test. Step 4, descriptive (`research/h15_decompose.py`): the 126-session hedge ratio to 10 November 2026 is −0.0004 while daily-return correlation is 0.65. Nedbank's own move net of the sector is +9.8%, most of it in August, and Standard Bank's −1.5%; removing Nedbank's own part would put the hedge ratio at 0.62. African currencies explain 4% of Standard Bank's own move.

Development: 5,094 closes from 3 January 2006 to 6 January 2026 (the last whose 60-session horizon ends by 31 March 2026), 1,342 event closes with |z| > 1.5. The frozen gap closed within 60 sessions, before the stop, on 44.8% of them (median 21 sessions when it did). Five purged folds, out of fold:

| Model | Log score | Brier |
| --- | --- | --- |
| Z, \|z\| only | −0.675 | 0.242 |
| G, H14's gate statistic and \|z\| | −0.609 | 0.208 |
| M, Markov-switching baseline | −0.679 | 0.244 |
| X, baseline plus five external inputs | −0.721 | 0.260 |

| Comparison | Mean log-score gain | Newey-West t |
| --- | --- | --- |
| X against M (the gate) | −0.041 | −2.97 |
| M against Z | −0.004 | −0.71 |
| G against Z | +0.066 | 1.82 |
| M against G | −0.071 | −2.02 |
| XN against M, from April 2015 (767 events) | −0.440 | −2.39 |

X does not beat the baseline, so H15 stops at (a): no trading rule was chosen, nothing is frozen, and there is no live record. The expectation was right on X and wrong on M, which did not beat |z| alone. The Markov fit is stable across folds (φ 0.970 to 0.975, σ 1.0% against 2.4 to 2.7%, persistence 0.97 to 0.98 and 0.85 to 0.95), but its two states separate calm from turbulent days rather than reverting from wandering spreads, and its filtered probability is uncorrelated with the label (−0.02). The external inputs add noise across eras; only results-ahead has a visible correlation with the label (0.16). News made the fit much worse. The one input that forecasts the gap closing is the 126-session Engle-Granger statistic itself (correlation −0.41 with the label, G beating Z at t 1.82): on development data the gate the brief called reactive carries more forward information than the daily model. That is a development figure, not a test, and H15 does not trade on it.

Outputs: `research/results/h15.json`, `h15_daily.csv` (label, inputs, the baseline's filtered probability and every model's out-of-fold probability by date), `h15_events.csv` (ex-dividend dates and results months), `h15_decompose.json`.

## H16: H4b's spread trade under a looser long-run gate, flat otherwise

An open search on development data (every session to 31 March 2026), `research/explore_gap.py`, 54 specifications. All figures are net at the institutional futures schedule, per completed trade, trades opened from 2006 (2009 for walk-forward). They are development figures and none is a test.

**Forecasting the frozen gap (H15's label, out of fold).** Adding the 126-session Engle-Granger statistic to |z| gains on log score (t 1.62); adding the 63- and 252-session statistics as well does not help (t 1.35). Walk-forward logistic fits (refit each January on resolved labels only) used as a gate earn 75 bps a trade at p > 0.6 (74 trades, t 2.59), but range from 15 to 75 bps across thresholds. The logistic is close to a linear cutoff on the statistic, so the simpler rule was kept.

**Exits.** Holding the regression line fixed from entry and closing when that frozen gap closes is worse than H4b's rolling-z exit in every gate tried (for example 56 against 91 bps at p > 0.6). Dead end.

**Gate cutoffs, 126-session window, H4b's trade:**

| Engle-Granger below | Trades | Per trade, bps | t | 2006–12 | 2013–19 | 2020–Mar 2026 |
|---|---|---|---|---|---|---|
| none | 137 | 4.6 | 0.17 | 84.0 | −19.1 | −63.4 |
| −2.0 | 108 | 52.3 | 1.93 | 88.4 | 46.4 | 17.3 |
| −2.4 | 95 | 81.3 | 3.02 | 91.3 | 76.6 | 72.7 |
| −2.6 | 86 | 87.2 | 3.34 | 87.6 | 62.9 | 112.9 |
| **−2.8** | **79** | **91.1** | **3.58** | **76.1** | **105.1** | **98.6** |
| −3.0 | 65 | 79.7 | 2.85 | 84.2 | 70.5 | 81.7 |
| −3.34 (H14's) | 48 | 81.6 | 2.72 | 85.0 | 46.3 | 118.9 |
| −3.6 | 31 | 79.2 | 2.24 | 66.6 | 111.3 | 63.5 |

At −2.8: median trade 145 bps, 81% of trades win, 78 bps a trade without the three best, mean hold 19 sessions, cash 83 bps a trade. Entry 1.0, 1.25, 1.75 and 2.0 give 68, 74, 80 and 64 bps. The gate is open on 36% of sessions since 2006: 22% in 2023, 39% in 2024, 19% in 2025, 5% in 2026 to October. Losing years: 2006, 2010, 2016, 2019, 2021, 2024, all with one to three trades.

**Other windows.** 63 sessions: 29 to 31 bps (t ≤ 1.33) at −2.4 and −2.8, negative at −3.34. 252 sessions: −16 to 57 bps (t ≤ 1.02). Not chosen.

**Sector-hedged spread, dead end.** Each bank less its trailing 126-session beta on the average of FirstRand and Absa, then H4b's trade on the two own parts (legs still SBK and NED only): −39 bps a trade ungated and −35, +4 and −7 bps at −2.4, −2.8 and −3.34. Removing the sector also removes what ties the two banks together.

**Chosen and frozen 11 November 2026** (PROTOCOL.md, H16): the −2.8 gate, flat when shut, scored on trades opened from 12 November 2026.

## H17: when the models refit

A history check on development data only (`research/h17_fits.R`, `research/h17_refit.py`). Every price after 31 March 2026 is deleted before any fit. The scored period runs from the first session of 2010 to 31 March 2026, 4,143 sessions. Yearly refits reproduce the record's GAS h to 5e-9 (the parity check), and the year-end margin refits match the walk-forward's coefficients to 4e-11. All 392 margin fits converged.

Gains are in thousandths of a nat a session against Y, with the Newey-West t (21 lags) in brackets. The bar was a mean gain above zero with t above 2.33. Copula rule trades are those opened from 2010 and completed by 31 March 2026, net per trade in bps at the institutional schedules. The KS p-values are for h, the SBK PITs and the NED PITs over the scored period.

| Refits | Count | Joint gain | Margins | Copula | Rule trades | Futures | Cash | Inside H14, futures | KS p (h / SBK / NED) |
|---|---|---|---|---|---|---|---|---|---|
| Y, year ends only | 17 | — | — | — | 292 | −20.5 | −46.3 | −19.0 | 0.004 / 0.047 / 0.103 |
| Q, plus quarter ends | 65 | +2.81 (3.08) | +0.76 (1.45) | +2.05 (2.78) | 298 | −20.3 | −46.2 | −19.4 | 0.007 / 0.054 / 0.159 |
| M, every month end | 195 | +3.09 (2.93) | +1.59 (2.45) | +1.50 (1.77) | 295 | −19.5 | −45.4 | −17.6 | 0.011 / 0.066 / 0.161 |
| K, PIT drift | 24 | +0.35 (1.23) | +0.12 (0.51) | +0.23 (1.04) | 292 | −21.2 | −47.1 | −19.8 | 0.003 / 0.056 / 0.106 |
| E, Engle-Granger crossings | 102 | +2.31 (2.65) | +0.93 (2.00) | +1.38 (1.85) | 294 | −18.7 | −44.5 | −16.7 | 0.007 / 0.067 / 0.143 |
| **R, end of March and August** | 49 | +2.42 (3.30) | +0.90 (1.88) | +1.52 (2.55) | 296 | −20.2 | −46.1 | −19.2 | 0.005 / 0.057 / 0.156 |

- **What passed.** Q, M, E and R all beat yearly refits on the joint score, and none of them lowers the copula rule's net per trade at futures. M has the largest gain, but Q, E and R are within one standard error of it, so the tie rule picks the one with the fewest refits: **R, refits at the end of March and August plus the year-end reselection**. That is a calendar procedure. The data-driven triggers did not earn their place. PIT drift (K) fired only 7 times between year ends and barely moved the score (t 1.23). Engle-Granger crossings (E) needed 102 refits to do about as well as R's 49.
- **What it means for trading.** Very little. The gain is about 0.002 nats a session, around 0.04% of the joint log density. Under every candidate the copula rule loses about 19 to 21 bps a trade at futures and 45 to 47 at cash on development data, so the timing of refits does not rescue it. The spread strategy has no fitted parameters and is unaffected.
- **Against the stated expectation.** The expectation was Y or Q. R was chosen instead, and the trading figures moved by under 2 bps a trade, as expected.
- **Live.** Under the registration, R runs from the first session after it is switched on, never retroactively. So the record from 1 April 2026 stays on the fit of 31 March 2026, and the 31 August 2026 refit is not made after the fact. The next refit would be the year-end reselection on the close of 31 December 2026.

## Run order

```sh
Rscript research/02_basket.R                 # about 15 minutes; writes data/basket.json and data/h1_daily.csv
service/.venv/bin/python research/decay.py
service/.venv/bin/python research/overlay.py
service/.venv/bin/python research/models/export_pair_gas.py
service/.venv/bin/python research/pair.py
service/.venv/bin/python research/h1_evaluate.py
service/.venv/bin/python research/h2_news.py # reads data/raw/gdelt_banks.csv, the output of research/sql/gdelt_banks.sql on BigQuery
service/.venv/bin/python research/fetch_volume.py   # basket volumes for H3
service/.venv/bin/python research/h3_exit.py      # also reads data/raw/gdelt_basket.csv (research/sql/gdelt_basket.sql)
Rscript research/04_cointegration.R          # descriptive; writes research/results/cointegration.json
service/.venv/bin/python research/h4_cointegration.py
service/.venv/bin/python research/h5_weights.py    # parity check of the edit harness against data/h1_daily.csv
service/.venv/bin/python research/h5_inspect.py && service/.venv/bin/python research/h5_inspect2.py && service/.venv/bin/python research/h5_inspect3.py   # design only
service/.venv/bin/python research/h5_edit.py      # the one validation run; writes research/results/h5.json
service/.venv/bin/python research/h6_rl_exit.py   # about 3 minutes; reads h5_daily.csv, writes research/results/h6.json
service/.venv/bin/python research/hourly_study.py  # descriptive; needs data/raw/sbk_60m.csv and ned_60m.csv (TradingView export, not in the repo)
service/.venv/bin/python research/h7_intraday.py   # design grid, then the one validation run; writes research/results/h7.json
service/.venv/bin/python research/h11_ned_repair.py design   # under a minute; writes research/results/h11.json
service/.venv/bin/python research/derivative_costs.py        # seconds; writes research/results/derivative_costs.json
service/.venv/bin/python research/models/h12_gauge.py         # about three minutes on eight cores; writes research/results/h12.json
service/.venv/bin/python research/closing_auction.py         # under a minute; needs the local hourly bars; writes research/results/closing_auction.json
service/.venv/bin/python research/models/pairdata.py && service/.venv/bin/python research/models/margins_py.py && Rscript research/08_margins_r.R   # margin models
service/.venv/bin/python research/models/copulas_py.py && service/.venv/bin/python research/models/compare.py 2020-01-01 2026-04-01 validation research/results/copulas_validation.json && service/.venv/bin/python research/models/h8_edge.py
service/.venv/bin/python research/models/h9_basket_gas.py   # about 10 minutes on 8 cores
COPULAS_CSV=research/results/copulas_basket.csv service/.venv/bin/python research/models/compare.py 2020-01-01 2026-04-01 validation research/results/copulas_basket_validation.json
service/.venv/bin/python research/models/export_gas.py     # writes data/basket_gas.json for the service; then research/edge.py and export_research.py again
service/.venv/bin/python research/costs.py                 # the JSE cost schedule; writes research/results/costs.json
service/.venv/bin/python research/h10_sizing.py            # leg sizing test; writes research/results/h10.json
service/.venv/bin/python research/redteam.py all           # the red team; writes research/results/redteam.json (run on Azure, 3 seconds of compute)
service/.venv/bin/python research/h14_switch.py select   # about a minute on eight cores; writes research/results/h14_select.json
service/.venv/bin/python research/h14_switch.py run      # seconds; writes h14.json, h14_daily.csv, h14_by_year.csv and data/pair_switch.json
service/.venv/bin/python research/h15_data.py       # downloads data/raw/h15_px.csv, h15_div.csv, h15_rate.csv (Yahoo, FRED); not committed
service/.venv/bin/python research/h15_decompose.py  # seconds; descriptive
service/.venv/bin/python research/h15_forecast.py   # about 25 seconds; writes h15.json, h15_daily.csv, h15_events.csv
service/.venv/bin/python research/explore_gap.py    # seconds; the H16 search, writes explore_gap.json
Rscript research/h17_fits.R                    # about two minutes on seven cores; writes research/results/h17_fits.json
service/.venv/bin/python research/h17_refit.py   # about six minutes on seven cores; writes research/results/h17.json
service/.venv/bin/python research/export_research.py
```
