# Is there a stable long-run relationship between Standard Bank and Nedbank?
#
# Reproduces the group report's cointegration tests (ADF, Engle-Granger, Johansen trace and maximum
# eigenvalue, Phillips-Ouliaris) on the full sample to March 2026 and on the design period alone, in
# price levels as in the report and in logs. Then asks whether a relationship holds in pieces: rolling
# two-year Engle-Granger tests, a Gregory-Hansen test that allows one break, and Bai-Perron breaks in
# the cointegrating regression. Descriptive only: nothing here chooses a trading rule.
#
#   Rscript research/04_cointegration.R   ->  research/results/cointegration.json
suppressPackageStartupMessages({ library(urca); library(strucchange); library(jsonlite) })
source("research/clean.R")

px <- load_prices("data/raw")
px <- px[px$date <= as.Date("2026-03-31"), ]

# MacKinnon (2010) critical values for an Engle-Granger test with two variables and a constant.
EG_CRIT <- c(`1%` = -3.90, `5%` = -3.34, `10%` = -3.04)
# Gregory and Hansen (1996), one regressor: level shift (C) and regime shift (C/S).
GH_CRIT <- list(level = c(`1%` = -5.13, `5%` = -4.61, `10%` = -4.34),
                regime = c(`1%` = -5.47, `5%` = -4.95, `10%` = -4.68))

adf_resid <- function(u) {
  t <- ur.df(u, type = "none", lags = 10, selectlags = "AIC")
  unname(t@teststat[1])
}

tests <- function(d, log_prices) {
  y <- if (log_prices) log(d$ned) else d$ned
  x <- if (log_prices) log(d$sbk) else d$sbk
  adf <- function(v) {
    t <- ur.df(v, type = "drift", lags = 10, selectlags = "AIC")
    list(stat = unname(t@teststat[1]), crit5 = unname(t@cval[1, "5pct"]))
  }
  reg <- lm(y ~ x)
  eg <- adf_resid(residuals(reg))
  m <- cbind(ned = y, sbk = x)
  jo_t <- ca.jo(m, type = "trace", ecdet = "const", K = 2)
  jo_e <- ca.jo(m, type = "eigen", ecdet = "const", K = 2)
  po <- ca.po(m, demean = "constant", type = "Pu")
  row <- function(stat, c1, c5, c10, lower) list(stat = stat, crit = c(`1%` = c1, `5%` = c5, `10%` = c10),
                                                reject5 = if (lower) stat < c5 else stat > c5)
  list(
    from = as.character(min(d$date)), to = as.character(max(d$date)), days = nrow(d),
    adf_levels = list(sbk = adf(x), ned = adf(y)),
    adf_differences = list(sbk = adf(diff(x)), ned = adf(diff(y))),
    regression = list(intercept = unname(coef(reg)[1]), slope = unname(coef(reg)[2]),
                      r2 = summary(reg)$r.squared),
    engle_granger = row(eg, EG_CRIT[[1]], EG_CRIT[[2]], EG_CRIT[[3]], TRUE),
    johansen_trace = row(unname(jo_t@teststat[2]), jo_t@cval[2, "1pct"], jo_t@cval[2, "5pct"], jo_t@cval[2, "10pct"], FALSE),
    johansen_eigen = row(unname(jo_e@teststat[2]), jo_e@cval[2, "1pct"], jo_e@cval[2, "5pct"], jo_e@cval[2, "10pct"], FALSE),
    phillips_ouliaris = row(unname(po@teststat), po@cval[1, "1pct"], po@cval[1, "5pct"], po@cval[1, "10pct"], FALSE)
  )
}

# Two-year windows, stepped a month at a time, in logs.
rolling <- function(d, window = 504, step = 21) {
  y <- log(d$ned); x <- log(d$sbk)
  ends <- seq(window, nrow(d), by = step)
  out <- t(sapply(ends, function(e) {
    i <- (e - window + 1):e
    reg <- lm(y[i] ~ x[i])
    c(stat = adf_resid(residuals(reg)), slope = unname(coef(reg)[2]))
  }))
  data.frame(end = as.character(d$date[ends]), stat = round(out[, "stat"], 3), slope = round(out[, "slope"], 3))
}

# Smallest residual ADF statistic over break dates in the middle 70% of the sample.
gregory_hansen <- function(d, regime) {
  y <- log(d$ned); x <- log(d$sbk); n <- length(y)
  cand <- seq(floor(0.15 * n), ceiling(0.85 * n), by = 5)
  stats <- sapply(cand, function(k) {
    s <- as.numeric(seq_len(n) > k)
    reg <- if (regime) lm(y ~ s + x + I(s * x)) else lm(y ~ s + x)
    adf_resid(residuals(reg))
  })
  i <- which.min(stats)
  crit <- if (regime) GH_CRIT$regime else GH_CRIT$level
  list(stat = stats[i], break_date = as.character(d$date[cand[i]]), crit = crit, reject5 = stats[i] < crit[["5%"]])
}

# Bai-Perron breaks in the log cointegrating regression, on month-end prices to keep the search small.
bai_perron <- function(d) {
  me <- d[!duplicated(format(d$date, "%Y-%m"), fromLast = TRUE), ]
  y <- log(me$ned); x <- log(me$sbk)
  bp <- breakpoints(y ~ x, h = 0.1)
  k <- bp$breakpoints
  if (all(is.na(k))) return(list(breaks = character(0), segments = list()))
  fit <- lm(y ~ breakfactor(bp) / x - 1)
  cf <- coef(fit)
  seg <- breakfactor(bp)
  edges <- c(0, k, length(y))
  list(breaks = as.character(me$date[k]),
       segments = lapply(seq_along(levels(seg)), function(j) list(
         from = as.character(me$date[edges[j] + 1]), to = as.character(me$date[edges[j + 1]]),
         intercept = unname(cf[j]), slope = unname(cf[length(levels(seg)) + j]))))
}

design <- px[px$date >= as.Date("2010-01-01") & px$date <= as.Date("2019-12-31"), ]
roll <- rolling(px)
out <- list(
  note = "Descriptive tests of SBK and NED adjusted closes. Nothing here chooses a trading rule.",
  full_levels = tests(px, FALSE), full_logs = tests(px, TRUE),
  design_levels = tests(design, FALSE), design_logs = tests(design, TRUE),
  rolling = list(window_days = 504, step_days = 21, crit5 = EG_CRIT[["5%"]],
                 share_rejecting = mean(roll$stat < EG_CRIT[["5%"]]), windows = roll),
  gregory_hansen = list(level = gregory_hansen(px, FALSE), regime = gregory_hansen(px, TRUE)),
  bai_perron = bai_perron(px)
)
dir.create("research/results", showWarnings = FALSE)
write_json(out, "research/results/cointegration.json", auto_unbox = TRUE, digits = 6, pretty = TRUE)

p <- function(name, r) cat(sprintf("%-22s EG %6.2f  trace %6.2f  eigen %6.2f  PO %6.2f  slope %.3f  (%s to %s)\n", name,
  r$engle_granger$stat, r$johansen_trace$stat, r$johansen_eigen$stat, r$phillips_ouliaris$stat,
  r$regression$slope, r$from, r$to))
p("full, levels", out$full_levels); p("full, logs", out$full_logs)
p("design, levels", out$design_levels); p("design, logs", out$design_logs)
cat(sprintf("rolling 2y windows rejecting at 5%%: %.0f%% of %d\n", 100 * out$rolling$share_rejecting, nrow(roll)))
for (k in c("level", "regime")) with(out$gregory_hansen[[k]], cat(sprintf("Gregory-Hansen %-6s %6.2f (5%% %.2f) break %s\n", k, stat, crit[["5%"]], break_date)))
cat("Bai-Perron breaks:", paste(out$bai_perron$breaks, collapse = ", "), "\n")
