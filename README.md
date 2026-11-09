# Standard Bank against Nedbank: one signal, one result

A copula-GARCH signal on Standard Bank against Nedbank, built to answer one question: is there still a reversal between the two banks worth trading after costs? The signal is a measuring instrument. It is calibrated out of sample, each year's model is fitted only on data before that year, and since 1 April 2026 it has been scored live on sessions no model has seen.

The answer it gives: a signal was worth about 23 bps before costs from 2010 to 2019, if filled at the very close that produced it, and about 11 bps filled at the next close. Since 2021 it has been worth about −7 bps. A round trip costs 20 bps in brokerage alone and about 59 on the JSE once securities transfer tax, VAT, spread and borrow are counted. The edge was real before 2020, at the 99.9th percentile of 10,000 random entry sets, but it was never larger than the cost of acting on it, and it has since gone.

Live record: https://mdingi-jse-pairs.azurewebsites.net (embedded at mdingi.co.za/work/jse-statistical-arbitrage).

## The instrument

Daily adjusted closes since 2005. For each bank an ARMA-GARCH specification is chosen by BIC from 36 candidates each December (GARCH, GJR or EGARCH; normal or Student t; with or without lagged VIX), fitted on data to that year end and used only for the following year. The final fit was frozen on 31 March 2026. The copula is Student t with a score-driven correlation (ρ_t = tanh f_t, f updated by the scaled score each day). It was chosen over a fixed correlation by a pre-registered forecast test: 20 thousandths of a log point a day better on 2020 to March 2026, Diebold-Mariano t = 3.4, and a signal calibrated out of sample where the fixed one was not. Four margin models and four dependence models were compared the same way (`research/RESULTS.md`); no margin model beat the BIC-chosen ARMA-GARCH. The signal is h = P(Nedbank ≤ today | Standard Bank = today). The measurement opens when h passes 0.05 or 0.95, goes long Standard Bank and short Nedbank when Nedbank has moved up more than Standard Bank implies, and holds five sessions with half of capital a side. It is a fixed hold; holding until the signal returns to normal was measured too and does worse after costs.

Standard Bank and Nedbank are not cointegrated (Engle-Granger −2.61 in logs against −3.34; six Bai-Perron breaks), which is why the project models dependence day to day instead of a long-run spread.

## Results

| Sharpe, five-day hold | Before costs | 10 bps a leg | JSE, institutional |
| --- | --- | --- | --- |
| Design, 2010 to 2019 | 0.82 | 0.18 | −1.16 |
| Validation, 2020 to March 2026 | −0.21 | −0.69 | −1.68 |

At institutional costs the walk-forward returns −8.1% a year; holding half of each bank returned 6.4%. The red team (`research/RESULTS.md`) finds the pre-2020 edge real against placebo and not carried by any one year. A fill one session late halves it. Sizing the legs from the instrument's own volatilities and correlation makes the position more variable, so 1:1 stays. Used as a timing overlay by someone who must trade these banks anyway, it is worth at most about 3 bps a trade at a price a real order can have.

The validation years are spent: every trading rule tried on the pair, from the group report's rule to news filters, the classic z-score trade and an intraday rule on hourly bars, went through the same pre-registration gate, and none passed by more than noise. An earlier stage of the project measured Standard Bank against a basket of four banks. It told the same story and is kept in `research/RESULTS.md` as the record, with every amendment to `research/PROTOCOL.md` dated.

## Layout

- `research/` R pipeline (`00_data.R`, `clean.R`, `lib.R`, `02_basket.R`) and Python evaluation. `h1_evaluate.py` scores the rule, `pair.py` measures the instrument (edge per signal by year, costs, red team, sizing), `export_research.py` collects everything into `data/research.json`. `models/` holds the margin and dependence model comparison; `models/export_pair_gas.py` writes `data/pair_gas.json`, the score-driven copula the service runs. `01_walkforward.R` fits the pair; `02_basket.R` and the scripts named for the basket are the earlier stage. The other scripts are the tests in `RESULTS.md`; `h5_weights.py` re-filters any month from the stored coefficients and matches the R record to 1e-9.
- `service/` FastAPI app for the pair only. `app/model.py` reimplements the rugarch filters and copula h-functions in NumPy, `app/pair.py` filters new sessions through the score-driven copula, `app/rule.py` holds the measurement rule and the JSE cost schedule, and `app/data.py` fetches Standard Bank and Nedbank after each close. `tests/test_parity.py` checks the filters against R, the copula against the research filter, and the rule's Sharpe ratios at every cost tier against `research/results/pair.json`.
- `dashboard/` React and Vite front end, themed to match mdingi.co.za and designed to be embedded.
- `deploy/azure.sh` builds the image in Azure Container Registry and deploys it to App Service. `deploy/cloudrun/` is the monthly refit of the earlier basket stage; its schedule is paused because the pair is frozen.

## Running locally

```sh
Rscript research/00_data.R && Rscript research/01_walkforward.R   # only to refit the pair
cd dashboard && bun install && bun run build
cd ../service && python -m venv .venv && .venv/bin/pip install -r requirements.txt pytest
.venv/bin/python -m pytest -q tests
APP_ROOT=.. .venv/bin/uvicorn app.main:app --port 8000
```

Live prices refresh every 30 minutes (`REFRESH_SECONDS`); if Yahoo is unreachable the service falls back to the stored record.

## Deploying

```sh
AZ_SUBSCRIPTION=<subscription id> TAG=v9 deploy/azure.sh
```

Resource group `rg-mdingi-previews`: an App Service F1 (free) Linux plan pulling from ACR Basic through a managed identity. Response headers allow framing only from mdingi.co.za and localhost. The pair's final fit is frozen on 31 March 2026 and is not refitted. The service filters each new session forward from that fit, so nothing scheduled is needed; the old monthly Cloud Run refit (`jse-pairs-refit-monthly`) is paused.

## Data

Prices come from Yahoo Finance and VIX from FRED; neither is redistributed. `Rscript research/00_data.R` downloads them into `data/raw/`. The GDELT counts in `data/raw/gdelt_*.csv` are open data from the queries in `research/sql/`. The 60-minute bars behind the hourly study are a TradingView export, kept locally and not redistributed.

Research output, not investment advice. Extended from a BSc Honours group project with Matlhatse Makgopa.
