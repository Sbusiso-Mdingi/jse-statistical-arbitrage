# H1: Standard Bank against an equal-weight bank basket, refitted monthly.
#
# Pre-registered in research/PROTOCOL.md. Each month end:
#   - at a year end (or the first month), choose an ARMA-GARCH specification for
#     SBK and for the basket by BIC on all data to that date
#   - re-estimate the chosen specifications on all data to that month end
#   - choose and fit the copula by AIC on the training PITs
#   - filter the next month one step ahead with the frozen parameters
# Writes data/h1_daily.csv for research/h1_evaluate.py and data/basket.json for the
# service: every monthly fit, the out-of-sample history, and the latest model with its
# terminal state so new sessions can be filtered live.

suppressPackageStartupMessages({
  library(rugarch)
  library(VineCopula)
  library(parallel)
  library(jsonlite)
})

CORES <- max(1, detectCores() - 1)
FIRST <- as.Date("2009-12-31")
BASKET <- c("fsr", "abg", "ned", "cpi")

source("research/clean.R")
source("research/lib.R")

read_px <- function(f) {
  x <- read.csv(file.path("data/raw", paste0(f, ".csv")), stringsAsFactors = FALSE)
  x$date <- as.Date(x$date)
  x <- x[!is.na(x$adjusted) & x$adjusted > 0, ]
  x <- drop_bad_prints(x)
  setNames(x[, c("date", "adjusted")], c("date", f))
}
px <- Reduce(function(a, b) merge(a, b, by = "date"), lapply(c("sbk", BASKET), read_px))

vix <- read.csv("data/raw/vix.csv", stringsAsFactors = FALSE)
vix$date <- as.Date(vix$date)
vix <- vix[!is.na(vix$vix), ]
idx <- findInterval(as.numeric(px$date) - 1, as.numeric(vix$date))
px$vix <- ifelse(idx > 0, vix$vix[pmax(idx, 1)] / 100, NA)
px <- px[!is.na(px$vix), ]

simple <- sapply(c("sbk", BASKET), function(k) px[[k]][-1] / px[[k]][-nrow(px)] - 1)
d <- data.frame(date = px$date[-1], simple, vix = px$vix[-1])
d$r_sbk <- log1p(d$sbk)
d$r_bsk <- log1p(rowMeans(d[, BASKET]))
cat("Observations:", nrow(d), "from", format(min(d$date)), "to", format(max(d$date)), "\n")

# Month ends with a following trading day.
month <- format(d$date, "%Y-%m")
ends <- d$date[c(month[-1] != month[-length(month)], FALSE)]
ends <- ends[ends >= FIRST]

refit <- function(g, r, vx) {
  fit <- tryCatch(suppressWarnings(ugarchfit(make_spec(g, vx), r, solver = "hybrid")),
                  error = function(e) NULL)
  if (is.null(fit) || fit@fit$convergence != 0) NULL else list(g = g, coef = coef(fit))
}

out <- list()
fits <- list()
sel <- list()
for (k in seq_along(ends)) {
  te <- ends[k]
  n_train <- sum(d$date <= te)
  n_all <- if (k < length(ends)) sum(d$date <= ends[k + 1]) else nrow(d)
  tr <- seq_len(n_train)
  new_year <- k == 1 || format(te, "%m") == "12"
  for (s in c("sbk", "bsk")) {
    r <- d[[paste0("r_", s)]]
    if (new_year) {
      sel[[s]] <- select_marginal(r[tr], d$vix[tr])
    } else {
      f <- refit(sel[[s]]$g, r[tr], d$vix[tr])
      # Keep last month's parameters if the re-estimate fails to converge.
      if (!is.null(f)) sel[[s]]$coef <- f$coef
    }
  }
  all <- seq_len(n_all)
  fs <- filter_marginal(sel$sbk, d$r_sbk[all], d$vix[all], n_train)
  fb <- filter_marginal(sel$bsk, d$r_bsk[all], d$vix[all], n_train)
  cop <- BiCopSelect(fs$u[tr], fb$u[tr], familyset = COPULA_FAMILIES, selectioncrit = "AIC")
  h <- BiCopHfunc1(fs$u, fb$u, cop$family, cop$par, cop$par2)
  ti <- (n_train + 1):n_all
  out[[k]] <- data.frame(
    date = d$date[ti], train_end = te, u = fs$u[ti], v = fb$u[ti], h = h[ti],
    copula = cop$family, par = cop$par, par2 = cop$par2,
    spec_sbk = paste(sel$sbk$g$model, sel$sbk$g$arma, sel$sbk$g$dist, sel$sbk$g$vix),
    spec_bsk = paste(sel$bsk$g$model, sel$bsk$g$arma, sel$bsk$g$dist, sel$bsk$g$vix),
    d[ti, c("sbk", BASKET)]
  )
  fits[[k]] <- list(
    train_end = format(te), sbk = describe(sel$sbk), bsk = describe(sel$bsk),
    copula = list(family = cop$family, name = BiCopName(cop$family, short = FALSE),
                  par = cop$par, par2 = cop$par2, tau = cop$tau, taildep = cop$taildep),
    pit_ks = list(sbk = ks.test(fs$u[tr], "punif")$p.value, bsk = ks.test(fb$u[tr], "punif")$p.value)
  )
  if (k == length(ends)) {
    latest <- fits[[k]]
    latest$state <- list(
      sbk = list(r = d$r_sbk[n_train], mu = fs$mu[n_train], sigma = fs$sigma[n_train], z = fs$z[n_train]),
      bsk = list(r = d$r_bsk[n_train], mu = fb$mu[n_train], sigma = fb$sigma[n_train], z = fb$z[n_train])
    )
    latest$parity <- data.frame(
      date = format(d$date[ti]), r_sbk = d$r_sbk[ti], r_bsk = d$r_bsk[ti], vix = d$vix[ti],
      sigma_sbk = fs$sigma[ti], sigma_bsk = fb$sigma[ti], u = fs$u[ti], v = fb$u[ti], h = h[ti]
    )
  }
  cat(format(te), cop$familyname, round(cop$par, 3), nrow(out[[k]]), "days\n")
}
res <- do.call(rbind, out)
write.csv(res, "data/h1_daily.csv", row.names = FALSE)
hist <- res[, c("date", "u", "v", "h", "sbk", BASKET)]
hist$date <- format(hist$date)
hist$fit <- match(format(res$train_end), sapply(fits, `[[`, "train_end"))
write_json(list(
  generated = format(Sys.time(), "%Y-%m-%dT%H:%M:%S%z"),
  basket = BASKET,
  fits = fits,
  latest = latest,
  history = hist
), "data/basket.json", digits = 10, auto_unbox = TRUE, dataframe = "columns")
cat("Wrote", nrow(res), "rows\n")
