# Results

Results of the tests in `PROTOCOL.md`, computed 13 October 2026 (H3 the same day, after its protocol entry; H4 on 25 October, after its protocol entry). All figures are annualised, after 10 bps per leg unless stated, from `data/research.json`. Post-freeze runs from 1 April 2026 and is reported only: to 9 October for v1, H1 and H3, and to 23 October for the five-day hold, H2 and H4, which read the price cache directly.

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

## Decay study

Mean one-year lag-1 autocorrelation of the daily return spread across the 15 pairs of SBK, NED, FSR, ABG, CPI and INL: about −0.16 in 2011, close to zero from 2020 (−0.01 at the start of 2026). The SBK/NED next-day return after an extreme copula signal averaged about 16 bps from 2010 to 2019 and about −6 bps since 2020. This is the most likely reason every reversal rule weakens after 2019.

## Amendments and corrections

Every one of these was made before the affected verdict was known, or changed no verdict.

1. **H1 threshold.** The protocol first gave the opening threshold as |h − 0.5| > 0.40, a typo for the 90th percentile (0.45). Amended before any H1 result was computed.
2. **H2b data source.** Changed from the GDELT DOC API to the GDELT 2.0 knowledge graph on BigQuery before any H2b result was computed. The 60-day median needs a warm-up, so the H2b design period starts on 13 May 2015, not 18 February.
3. **H2a rolling median.** The first run took the median of the previous 60 consecutive sessions and needed all 60 to have volume, so holiday gaps left most pre-2018 days unflagged. Corrected to the last 60 sessions with data. Only design figures changed; the validation verdict did not. The first-run output is not used anywhere.
4. **Period boundaries.** Both the service and the research scripts first restarted flat at the start of each period, charging a fresh entry and dropping the first held day. Returns are now computed on the full record and then sliced, so positions carry across boundaries. No verdict changed; H1 post-freeze moved from −2.49 to −2.31.

5. **Sortino ratios and H4.** Added to the protocol on 25 October 2026, before any H4 result was computed. Adding Sortino changed no other figure in H1, H2 or H3. Rerunning H2 extended its post-freeze figures to 23 October; design and validation figures are unchanged.

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
service/.venv/bin/python research/export_research.py
```
