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

Walk-forward is 2010 to March 2026, after costs. H1 before costs: 3.5% a year, Sharpe 0.69. Two news filters (volume and GDELT coverage via BigQuery) and the best of a 78-rule design grid failed validation. Two learned exit models for the basket trade (a classifier and fitted Q-iteration on news, tone, volume and market state) cleared the pass mark by amounts too small to tell from chance. A rolling study of all 15 bank pairs shows the daily reversal these rules rely on has been close to zero since 2020.

The live record since 1 April 2026 is served by `/api/summary` and changes daily. Slippage, borrow fees and securities transfer tax are not modelled.

## Layout

- `research/` R pipeline (`00_data.R`, `clean.R`, `lib.R`, `01_walkforward.R` for v1, `02_basket.R` for H1) and Python evaluation (`decay.py`, `h1_evaluate.py`, `h2_news.py`, `fetch_volume.py`, `h3_exit.py`, `export_research.py`). `sql/` holds the BigQuery queries behind `data/raw/gdelt_banks.csv` and `data/raw/gdelt_basket.csv`.
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

Prices and volumes come from Yahoo Finance and VIX from FRED; neither is redistributed here. `Rscript research/00_data.R` and `research/fetch_volume.py` download them into `data/raw/`. The GDELT article counts in `data/raw/gdelt_*.csv` are open data, from the queries in `research/sql/`.

Research output, not investment advice.
