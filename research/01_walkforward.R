# Walk-forward estimation for the SBK/NED copula-GARCH pairs strategy.
#
# Each fold uses only data up to its training end date:
#   1. choose an ARMA-GARCH specification per bank by BIC (training data only)
#   2. fit a bivariate copula to the training PITs, family chosen by AIC
#   3. filter the next trading window with the frozen parameters (one-step-ahead,
#      so day t uses only information available at the close of day t - 1)
#   4. record training-period signal and volatility quantiles for thresholds
#
# Folds refit at each year end from 2009 to 2025. The final fold is frozen at
# 31 March 2026; everything after that date is genuinely unseen and is filtered
# live by the service using the exported parameters.

suppressPackageStartupMessages({
  library(rugarch)
  library(VineCopula)
  library(jsonlite)
  library(parallel)
})

FREEZE <- as.Date("2026-03-31")
FOLD_ENDS <- c(as.Date(sprintf("%d-12-31", 2009:2025)), FREEZE)
CORES <- max(1, detectCores() - 1)
VOL_WINDOW <- 21

source("research/clean.R")

px <- load_prices("data/raw")
vix <- read.csv("data/raw/vix.csv", stringsAsFactors = FALSE)
vix$date <- as.Date(vix$date)
vix <- vix[!is.na(vix$vix), ]
# VIX known before the JSE close on day t: the last US close strictly before t.
idx <- findInterval(as.numeric(px$date) - 1, as.numeric(vix$date))
px$vix <- ifelse(idx > 0, vix$vix[pmax(idx, 1)] / 100, NA)
px <- px[!is.na(px$vix), ]

r_sbk <- diff(log(px$sbk))
r_ned <- diff(log(px$ned))
d <- data.frame(
  date = px$date[-1],
  r_sbk = r_sbk,
  r_ned = r_ned,
  vix = px$vix[-1]
)
d$spread_vol <- c(rep(NA, VOL_WINDOW - 1),
                  sapply(VOL_WINDOW:nrow(d), function(i) sd(d$r_sbk[(i - VOL_WINDOW + 1):i] - d$r_ned[(i - VOL_WINDOW + 1):i])))
cat("Observations:", nrow(d), "from", format(min(d$date)), "to", format(max(d$date)), "\n")

source("research/lib.R")

folds <- list()
rows <- list()
probs <- seq(0.50, 0.99, by = 0.01)

for (k in seq_along(FOLD_ENDS)) {
  train_end <- FOLD_ENDS[k]
  is_final <- train_end == FREEZE
  trade_end <- if (is_final) max(d$date) else FOLD_ENDS[k + 1]
  n_train <- sum(d$date <= train_end)
  n_all <- sum(d$date <= trade_end)
  t0 <- Sys.time()

  sel_s <- select_marginal(d$r_sbk[1:n_train], d$vix[1:n_train])
  sel_n <- select_marginal(d$r_ned[1:n_train], d$vix[1:n_train])
  fs <- filter_marginal(sel_s, d$r_sbk[1:n_all], d$vix[1:n_all], n_train)
  fn <- filter_marginal(sel_n, d$r_ned[1:n_all], d$vix[1:n_all], n_train)

  cop <- BiCopSelect(fs$u[1:n_train], fn$u[1:n_train], familyset = COPULA_FAMILIES,
                     selectioncrit = "AIC", indeptest = FALSE)
  h_ns <- BiCopHfunc1(fs$u, fn$u, cop$family, cop$par, cop$par2)
  h_sn <- BiCopHfunc2(fs$u, fn$u, cop$family, cop$par, cop$par2)

  train_signal <- abs(h_ns[1:n_train] - 0.5)
  train_vol <- d$spread_vol[1:n_train]
  ks_s <- ks.test(fs$u[1:n_train], "punif")$p.value
  ks_n <- ks.test(fn$u[1:n_train], "punif")$p.value

  trade_idx <- (n_train + 1):n_all
  fold <- list(
    id = k,
    train_start = format(min(d$date)),
    train_end = format(train_end),
    trade_start = format(d$date[n_train + 1]),
    trade_end = format(d$date[n_all]),
    final = is_final,
    sbk = describe(sel_s),
    ned = describe(sel_n),
    copula = list(family = cop$family, name = BiCopName(cop$family, short = FALSE),
                  par = cop$par, par2 = cop$par2, tau = cop$tau,
                  aic = cop$AIC, taildep = cop$taildep),
    pit_ks = list(sbk = ks_s, ned = ks_n),
    q_signal = unname(quantile(train_signal, probs)),
    q_vol = unname(quantile(train_vol, probs, na.rm = TRUE))
  )
  if (is_final) {
    # Terminal state for the live filter, plus the R path over the live window
    # so the service can be checked against rugarch.
    fold$state <- list(
      date = format(train_end),
      sbk = list(r = d$r_sbk[n_train], mu = fs$mu[n_train], sigma = fs$sigma[n_train], z = fs$z[n_train]),
      ned = list(r = d$r_ned[n_train], mu = fn$mu[n_train], sigma = fn$sigma[n_train], z = fn$z[n_train]),
      vol_tail_sbk = tail(d$r_sbk[1:n_train], VOL_WINDOW - 1),
      vol_tail_ned = tail(d$r_ned[1:n_train], VOL_WINDOW - 1)
    )
    fold$parity <- data.frame(
      date = format(d$date[trade_idx]), r_sbk = d$r_sbk[trade_idx], r_ned = d$r_ned[trade_idx],
      vix = d$vix[trade_idx], sigma_sbk = fs$sigma[trade_idx], sigma_ned = fn$sigma[trade_idx],
      mu_sbk = fs$mu[trade_idx], mu_ned = fn$mu[trade_idx],
      u = fs$u[trade_idx], v = fn$u[trade_idx], h_ns = h_ns[trade_idx], h_sn = h_sn[trade_idx]
    )
  } else {
    rows[[k]] <- data.frame(
      date = format(d$date[trade_idx]), fold = k,
      r_sbk = d$r_sbk[trade_idx], r_ned = d$r_ned[trade_idx],
      u = fs$u[trade_idx], v = fn$u[trade_idx],
      h_ns = h_ns[trade_idx], h_sn = h_sn[trade_idx],
      spread_vol = d$spread_vol[trade_idx]
    )
  }
  folds[[k]] <- fold
  cat(sprintf("Fold %2d  train to %s  SBK %s(%s) %s%s  NED %s(%s) %s%s  copula %s tau %.3f  %.0fs\n",
              k, format(train_end),
              sel_s$g$model, sel_s$g$arma, sel_s$g$dist, if (sel_s$g$vix) "+VIX" else "",
              sel_n$g$model, sel_n$g$arma, sel_n$g$dist, if (sel_n$g$vix) "+VIX" else "",
              BiCopName(cop$family), cop$tau, as.numeric(difftime(Sys.time(), t0, units = "secs"))))
}

history <- do.call(rbind, rows)
final <- folds[[length(folds)]]
write_json(list(
  generated = format(Sys.time(), "%Y-%m-%dT%H:%M:%S%z"),
  freeze = format(FREEZE),
  probs = probs,
  vol_window = VOL_WINDOW,
  folds = lapply(folds, function(f) { f$parity <- NULL; f$state <- NULL; f }),
  history = history
), "data/walkforward.json", digits = 10, auto_unbox = TRUE, dataframe = "columns")
write_json(final, "data/model_final.json", digits = 12, auto_unbox = TRUE, dataframe = "columns")
cat("Wrote data/walkforward.json and data/model_final.json\n")
