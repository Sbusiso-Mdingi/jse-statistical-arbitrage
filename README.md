# Standard Bank against its peers: one signal, one result

A copula-GARCH signal on Standard Bank against an equal-weight basket of FirstRand, Absa, Nedbank and Capitec, built to answer one question: is there still a reversal between South African banks worth trading after costs? The signal is a measuring instrument. It is calibrated out of sample, it is refitted every month on data before the month it trades, and it has been scored live on sessions no model has seen since 1 April 2026.

The answer it gives: a signal was worth about 18 bps before costs from 2010 to 2019 and about 1 bp since 2021, against a round trip that costs 20. The edge was never larger than the cost of acting on it, and it has since gone.

Live record: https://mdingi-jse-pairs.azurewebsites.net (embedded at mdingi.co.za/work/jse-statistical-arbitrage).

## The instrument

Daily adjusted closes since 2005. For Standard Bank and for the basket, an ARMA-GARCH specification is chosen by BIC from 36 candidates each December (GARCH, GJR or EGARCH; normal or Student t; with or without lagged VIX); parameters and the copula (family by AIC, Student t in all 202 fits) are re-estimated at every month end and filter only the following month. The signal is h = P(basket ≤ today | Standard Bank = today). The rule, fixed on 2010 to 2019 and validated once on 2020 to March 2026: open when h passes 0.05 or 0.95, long Standard Bank and short the basket when the basket has moved up more than Standard Bank implies, hold five sessions, half of capital a side, 10 bps per leg on every change of position.

Standard Bank and Nedbank are not cointegrated (Engle-Granger −2.61 in logs against −3.34; six Bai-Perron breaks), which is why the project models dependence day to day instead of a long-run spread.

## Results

| | Before costs | After costs |
| --- | --- | --- |
| Sharpe, design 2010 to 2019 | 0.74 | 0.08 |
| Sharpe, validation 2020 to March 2026 | 0.64 | 0.06 |
| Return a year, walk-forward 2010 to March 2026 | 3.4% | 0.3% |
| Gross per signal, 2010 to 2019 | 18 bps (SE 8) | |
| Gross per signal, 2021 onward | 1 bp (SE 11) | |

Holding half Standard Bank and half the basket returned 10.5% a year over the walk-forward. The live record since April 2026 is served by `/api/summary` and changes daily; with months of data it sits inside the range a strategy with no edge would land in.

Seven other rules went through the same pre-registration gate: two news filters, the classic z-score trade with and without a cointegration gate, two learned exits, a direct edit to the fitted copula correlation, an exit network trained on every day, and an intraday rule on hourly bars. Four failed and three passed by margins within noise. None earned a place in the write-up; all are in `research/RESULTS.md`, with every amendment to `research/PROTOCOL.md` dated.

## Layout

- `research/` R pipeline (`00_data.R`, `clean.R`, `lib.R`, `02_basket.R`) and Python evaluation. `h1_evaluate.py` scores the rule, `edge.py` measures the gross edge per signal by year, `export_research.py` collects everything into `data/research.json`. The other scripts are the tests in `RESULTS.md`; `h5_weights.py` re-filters any month from the stored coefficients and matches the R record to 1e-9.
- `service/` FastAPI app. `app/model.py` reimplements the rugarch filters and copula h-functions in NumPy; `app/basket.py` runs the rule; `tests/test_parity.py` checks both against R.
- `dashboard/` React and Vite front end, themed to match mdingi.co.za and designed to be embedded.
- `deploy/azure.sh` builds the image in Azure Container Registry and deploys it to App Service; `deploy/cloudrun/` runs the monthly refit.

## Running locally

```sh
Rscript research/00_data.R && Rscript research/02_basket.R   # only to refit, about 15 minutes
cd dashboard && bun install && bun run build
cd ../service && python -m venv .venv && .venv/bin/pip install -r requirements.txt pytest
.venv/bin/python -m pytest -q tests
APP_ROOT=.. .venv/bin/uvicorn app.main:app --port 8000
```

Live prices refresh every 30 minutes (`REFRESH_SECONDS`); if Yahoo is unreachable the service falls back to the stored record.

## Deploying

```sh
AZ_SUBSCRIPTION=<subscription id> TAG=v4 deploy/azure.sh
```

Resource group `rg-mdingi-previews`: an App Service F1 (free) Linux plan pulling from ACR Basic through a managed identity. Response headers allow framing only from mdingi.co.za and localhost. The monthly refit on Cloud Run downloads fresh prices, refits the basket model and redeploys on the 5th of every month.

## Data

Prices come from Yahoo Finance and VIX from FRED; neither is redistributed. `Rscript research/00_data.R` downloads them into `data/raw/`. The GDELT counts in `data/raw/gdelt_*.csv` are open data from the queries in `research/sql/`. The 60-minute bars behind the hourly study are a TradingView export, kept locally and not redistributed.

Research output, not investment advice. Extended from a BSc Honours group project with Matlhatse Makgopa.
