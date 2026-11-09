# Margin models in R for the SBK/NED pair, yearly walk-forward folds as in 01_walkforward.R:
# (c) Realized GARCH on the hourly-bar realised variance (training from 2009-02-02, scored from 2012),
# (d) two-regime Markov-switching GJR-GARCH with Student t errors.
# Out-of-sample one-step log densities and PITs to research/results/margins_r.csv.
suppressPackageStartupMessages({ library(rugarch); library(MSGARCH); library(xts) })
d <- read.csv("data/rv_daily.csv", stringsAsFactors = FALSE)
d$date <- as.Date(d$date)
ends <- c(as.Date(sprintf("%d-12-31", 2009:2025)), as.Date("2026-03-31"))
out <- list()
for (k in seq_along(ends)) {
  te <- ends[k]
  n_train <- sum(d$date <= te)
  n_all <- if (k < length(ends)) sum(d$date <= ends[k + 1]) else nrow(d)
  if (n_all <= n_train) next
  test <- (n_train + 1):n_all
  for (s in c("sbk", "ned")) {
    r <- d[[paste0("r_", s)]]
    # (d) MSGARCH, two regimes, fitted on all training data; densities for the test window with frozen parameters
    spec <- CreateSpec(variance.spec = list(model = c("gjrGARCH", "gjrGARCH")),
                       distribution.spec = list(distribution = c("std", "std")))
    mu <- mean(r[1:n_train])
    fit <- tryCatch(FitML(spec, data = r[1:n_train] - mu, ctr = list(do.se = FALSE)), error = function(e) NULL)
    if (!is.null(fit)) {
      pdf <- PredPdf(spec, par = fit$par, data = r[1:n_all] - mu, log = TRUE, do.its = TRUE)
      pit <- PIT(spec, par = fit$par, data = r[1:n_all] - mu, do.its = TRUE)
      out[[length(out) + 1]] <- data.frame(date = format(d$date[test]), fold = k, series = s, model = "ms_gjr_garch_t",
                                           logf = as.numeric(pdf)[test], u = as.numeric(pit)[test])
    }
    # (c) Realized GARCH, training restricted to days with realised variance (from 2009-02-02)
    rv <- d[[paste0("rv_", s)]]
    ok <- which(!is.na(rv))
    tr <- ok[ok <= n_train]
    if (length(tr) >= 500 && te >= as.Date("2011-12-31")) {
      all_idx <- ok[ok <= n_all]
      rspec <- ugarchspec(variance.model = list(model = "realGARCH", garchOrder = c(1, 1)),
                          mean.model = list(armaOrder = c(0, 0), include.mean = TRUE), distribution.model = "std")
      xr <- xts(r[all_idx], d$date[all_idx]); xrv <- xts(sqrt(rv[all_idx]), d$date[all_idx])
      rfit <- tryCatch(suppressWarnings(ugarchfit(rspec, xr[1:length(tr)], solver = "hybrid", realizedVol = xrv[1:length(tr)])), error = function(e) NULL)
      if (!is.null(rfit) && rfit@fit$convergence == 0) {
        fspec <- ugarchspec(variance.model = list(model = "realGARCH", garchOrder = c(1, 1)),
                            mean.model = list(armaOrder = c(0, 0), include.mean = TRUE), distribution.model = "std",
                            fixed.pars = as.list(coef(rfit)))
        filt <- ugarchfilter(fspec, xr, n.old = length(tr), realizedVol = xrv)
        sig <- as.numeric(sigma(filt)); mu_f <- as.numeric(fitted(filt)); sh <- coef(rfit)[["shape"]]
        z <- (as.numeric(xr) - mu_f) / sig
        lf <- log(ddist("std", z, mu = 0, sigma = 1, shape = sh)) - log(sig)
        u <- pdist("std", z, mu = 0, sigma = 1, shape = sh)
        tst <- which(all_idx > n_train)
        out[[length(out) + 1]] <- data.frame(date = format(d$date[all_idx[tst]]), fold = k, series = s, model = "realgarch_t",
                                             logf = lf[tst], u = u[tst])
      }
    }
    cat(format(te), s, "done\n")
  }
}
res <- do.call(rbind, out)
write.csv(res, "research/results/margins_r.csv", row.names = FALSE)
cat("wrote", nrow(res), "rows\n")
