# Copula-GARCH pairs trading: JSE banks

A rebuild of an honours group project (Sbusiso Mdingi and Matlhatse Makgopa) that traded the SBK.JO / NED.JO pair with ARMA-GARCH margins and a bivariate copula. This version fixes what the original did not do: every result is out of sample, costs are charged, rules were fixed on a design period before a single validation run (`research/PROTOCOL.md`), and sessions since 1 April 2026 are scored live on data no model has seen.

Live dashboard: https://mdingi-jse-pairs.azurewebsites.net (embedded at mdingi.co.za).

## Strategies

**Bank basket (H1, the headline).** Standard Bank against an equal-weight, daily-rebalanced basket of FirstRand, Absa, Nedbank and Capitec. ARMA-GARCH specifications are chosen by BIC each December; parameters and the copula (by AIC) are re-estimated at every month end, and each fit trades only the following month. Signal `h = P(basket ≤ v | SBK = u)`; open when it passes the 90th percentile in either direction, hold five days, 10 bps per leg, half of capital per side.

**Original report rule (v1).** SBK against NED, refitted yearly, open at the 90th percentile, close at the 50th, volatility filter at the 80th. Kept in the dashboard as the baseline.

Common to both:

1. **Data.** Daily adjusted closes from Yahoo Finance since 2005, VIX from FRED (the last US close before each JSE day). A one-day jump of more than 40% that reverses the next day is treated as a bad print and dropped.
2. **Margins.** 36 ARMA-GARCH candidates (ARMA 0,0 / 1,0 / 1,1; GARCH, GJR or EGARCH; normal or Student t; with or without lagged VIX).
3. **Copula.** Families 1 to 5, 13 and 14 from VineCopula. Student t wins every fit.
4. **Live sessions.** The service filters each new session with the latest fitted parameters. New fits only appear when `02_basket.R` is rerun and the image redeployed.

## Results

Full detail, including every failed test and every correction, is in `research/RESULTS.md`.

| Rule | Walk-forward CAGR | Sharpe | Max drawdown | Validation Sharpe (2020 to Mar 2026) |
| --- | --- | --- | --- | --- |
| Bank basket (H1) | 0.3% | 0.08 | −15.1% | 0.06, passed narrowly |
| Report rule (v1) | −0.9% | −0.22 | −25.4% | −0.70 |
| Buy and hold SBK and the basket | 10.5% | | | |

Walk-forward is 2010 to March 2026, after costs. H1 before costs: 3.5% a year, Sharpe 0.69. Two news filters (volume and GDELT coverage via BigQuery) and the best of a 78-rule design grid failed validation. Two learned exit models for the basket trade (a classifier and fitted Q-iteration on news, tone, volume and market state) cleared the pass mark by amounts too small to tell from chance. The classic z-score trade, gated on a rolling cointegration test, had the best validation figures but from ten trades. A rolling study of all 15 bank pairs shows the daily reversal these rules rely on has been close to zero since 2020.

**H5, a direct edit to the fitted parameters.** In the spirit of the MIT "weight-space programming" result (a language model reading a network's weights and editing them by hand instead of retraining), the 202 monthly fits were read as text with the design-period record and a logged budget of looks (`research/results/h5_log.json`). The margins were calibrated out of sample but the copula's conditional probability was not: the correlation, fitted on an expanding window from 2005, lagged a dependence that rose from about 0.5 to 0.7 in Kendall's tau, so the rule fired on 7.5% of days instead of 10%, and on 2.8% in 2019. Replacing that one coefficient per fit with the value implied by the last 252 training days' tau calibrated the signal and raised the design Sharpe from 0.08 to 0.15, then failed validation (−0.23 after costs, 0.48 before): the extra signals a correct correlation admits are moderate divergences that revert by less than a round trip costs. `research/h5_weights.py` re-filters every month from the stored coefficients and matches the R record to 1e-9.

**H6, a learned exit trained on every day.** H3's exit models saw only the ~600 days inside real trades. H6 treats every close as a virtual five-day trade in the direction of its signal, so a small network inside the same fitted Q-iteration learns from 17,082 decision points, with the H5 calibrated signal as a state variable. It passed its pre-registered mark (validation Sharpe 0.21 against H1's 0.06 and H3b's 0.14, drawdown −10.5% against −15.1%), 76 bps a year ahead with t = 0.95, so within noise; without the H5 features it scores 0.19 in validation and 0.00 in design.

**Hourly study and H7.** 60-minute SBK and NED bars (a TradingView export to 2 June 2026, kept locally and not redistributed) show that dependence drifts rather than switches (monthly realised correlation 0.3 to 0.8, autocorrelation 0.65, one hump) and that the reversal moved inside the day: a top-decile two-hour divergence after 10:00 reversed by about 31 bps by the close on design data (t = −4.6). Traded as H7 (open at 12:00, close at 17:00, threshold chosen on design), it fails validation: Sharpe 0.33 before costs and −0.60 after, with the gross edge per trade down from 15 bps in design to 7 bps against a 20 bps round trip.

The live record since 1 April 2026 is served by `/api/summary` and changes daily. Slippage, borrow fees and securities transfer tax are not modelled.

## Layout

- `research/` R pipeline (`00_data.R`, `clean.R`, `lib.R`, `01_walkforward.R` for v1, `02_basket.R` for H1) and Python evaluation (`decay.py`, `h1_evaluate.py`, `h2_news.py`, `fetch_volume.py`, `h3_exit.py`, `h4_cointegration.py`, `export_research.py`) and the parameter-edit harness (`h5_weights.py`, `h5_inspect*.py`, `h5_edit.py`) the all-days exit network (`h6_rl_exit.py`) and the hourly study and intraday rule (`hourly_study.py`, `h7_intraday.py`). `sql/` holds the BigQuery queries behind `data/raw/gdelt_banks.csv` and `data/raw/gdelt_basket.csv`.
- `service/` FastAPI app. `app/model.py` reimplements the rugarch filters and copula h-functions in NumPy; `app/basket.py` runs H1; `tests/test_parity.py` checks both against R.
- `dashboard/` React and Vite front end, themed to match mdingi.co.za and designed to be embedded.
- `deploy/azure.sh` builds the image in Azure Container Registry and deploys it to App Service.

## Running locally

```sh
Rscript research/00_data.R && Rscript research/01_walkforward.R && Rscript research/02_basket.R   # only to refit
cd dashboard && bun install && bun run build
cd ../service && python -m venv .venv && .venv/bin/pip install -r requirements.txt pytest
.venv/bin/python -m pytest -q tests
APP_ROOT=.. .venv/bin/uvicorn app.main:app --port 8000
```

The research run order is in `research/RESULTS.md`. Live prices refresh every 30 minutes (`REFRESH_SECONDS`); if Yahoo is unreachable the service falls back to the stored record.

## Deploying

```sh
AZ_SUBSCRIPTION=<subscription id> TAG=v3 deploy/azure.sh
```

Resource group `rg-mdingi-previews`: an App Service F1 (free) Linux plan pulling from ACR Basic through a managed identity. The response headers allow framing only from mdingi.co.za and localhost. `.github/workflows/monthly-refit.yml` downloads fresh prices, refits the basket model and redeploys on the 5th of every month.

## Data

Prices and volumes come from Yahoo Finance and VIX from FRED; neither is redistributed here. The 60-minute bars behind the hourly study and H7 are a TradingView export (`data/raw/sbk_60m.csv`, `ned_60m.csv`), also not redistributed. `Rscript research/00_data.R` and `research/fetch_volume.py` download them into `data/raw/`. The GDELT article counts in `data/raw/gdelt_*.csv` are open data, from the queries in `research/sql/`.

Research output, not investment advice.
