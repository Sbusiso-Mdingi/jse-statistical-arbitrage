# Results

Results of the tests in `PROTOCOL.md`, computed 13 October 2026 (H3 the same day, after its protocol entry; H4 on 25 October, H5, H6 and H7 on 9 November, each after its protocol entry). All figures are annualised, after 10 bps per leg unless stated, from `data/research.json`. Post-freeze runs from 1 April 2026 and is reported only: to 9 October for v1, H1, H3, H5 and H6, to 23 October for the five-day hold, H2 and H4, which read the price cache directly, and to 2 June for H7, where the hourly data ends.

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

## Run order

```sh
Rscript research/02_basket.R                 # about 15 minutes; writes data/basket.json and data/h1_daily.csv
service/.venv/bin/python research/decay.py
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
service/.venv/bin/python research/models/pairdata.py && service/.venv/bin/python research/models/margins_py.py && Rscript research/08_margins_r.R   # margin models
service/.venv/bin/python research/models/copulas_py.py && service/.venv/bin/python research/models/compare.py 2020-01-01 2026-04-01 validation research/results/copulas_validation.json && service/.venv/bin/python research/models/h8_edge.py
service/.venv/bin/python research/models/h9_basket_gas.py   # about 10 minutes on 8 cores
COPULAS_CSV=research/results/copulas_basket.csv service/.venv/bin/python research/models/compare.py 2020-01-01 2026-04-01 validation research/results/copulas_basket_validation.json
service/.venv/bin/python research/models/export_gas.py     # writes data/basket_gas.json for the service; then research/edge.py and export_research.py again
service/.venv/bin/python research/costs.py                 # the JSE cost schedule; writes research/results/costs.json
service/.venv/bin/python research/export_research.py
```
