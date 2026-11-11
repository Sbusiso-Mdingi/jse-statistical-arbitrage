# H17 (research/PROTOCOL.md): margin parameters re-estimated at every month end, 31 December 2009 to
# 31 March 2026, under the specification chosen at the latest year end (data/walkforward.json).
# Every price after 31 March 2026 is deleted first. Writes research/results/h17_fits.json.
#
#   Rscript research/h17_fits.R

suppressPackageStartupMessages({
  library(rugarch)
  library(jsonlite)
  library(parallel)
})

DEV_END <- as.Date("2026-03-31")
CORES <- max(1, detectCores() - 1)
source("research/clean.R")
source("research/lib.R")

px <- load_prices("data/raw")
px <- px[px$date <= DEV_END, ]
vix <- read.csv("data/raw/vix.csv", stringsAsFactors = FALSE)
vix$date <- as.Date(vix$date)
vix <- vix[!is.na(vix$vix) & vix$date < DEV_END, ]
idx <- findInterval(as.numeric(px$date) - 1, as.numeric(vix$date))
px$vix <- ifelse(idx > 0, vix$vix[pmax(idx, 1)] / 100, NA)
px <- px[!is.na(px$vix), ]
d <- data.frame(date = px$date[-1], r_sbk = diff(log(px$sbk)), r_ned = diff(log(px$ned)), vix = px$vix[-1])

W <- fromJSON("data/walkforward.json", simplifyVector = FALSE)
sel_ends <- as.Date(sapply(W$folds, `[[`, "train_end"))
ym <- format(d$date, "%Y-%m")
# Calendar month ends, as the walk-forward's fold ends (31 December even when the last session is the 30th).
last_day <- d$date[c(ym[-1] != ym[-length(ym)], TRUE)]
month_end <- as.Date(sapply(last_day, function(x) seq(as.Date(format(x, "%Y-%m-01")), by = "month", length.out = 2)[2] - 1),
                     origin = "1970-01-01")
month_end <- month_end[month_end >= as.Date("2009-12-31")]
cat("month ends", length(month_end), format(min(month_end)), "to", format(max(month_end)), "\n")

jobs <- expand.grid(k = seq_along(month_end), bank = c("sbk", "ned"), stringsAsFactors = FALSE)
t0 <- Sys.time()
res <- mclapply(seq_len(nrow(jobs)), function(j) {
  te <- month_end[jobs$k[j]]; bank <- jobs$bank[j]
  fold <- W$folds[[max(which(sel_ends <= te))]]
  s <- fold[[bank]]
  g <- data.frame(model = s$model, arma = s$arma, dist = s$dist, vix = s$vix, stringsAsFactors = FALSE)
  n_train <- sum(d$date <= te)
  f <- fit_one(g, d[[paste0("r_", bank)]][1:n_train], d$vix[1:n_train])
  list(train_end = format(te), bank = bank, spec_from = fold$train_end, model = s$model, arma = s$arma,
       dist = s$dist, vix = s$vix, converged = !is.null(f),
       coef = if (is.null(f)) NULL else as.list(f$coef), rho_start = fold$copula$par)
}, mc.cores = CORES)
cat(sprintf("%d fits in %.0fs, %d not converged\n", length(res), as.numeric(difftime(Sys.time(), t0, units = "secs")),
            sum(!sapply(res, `[[`, "converged"))))
write_json(list(dev_end = format(DEV_END), sessions = nrow(d), last_session = format(max(d$date)), fits = res),
           "research/results/h17_fits.json", digits = 12, auto_unbox = TRUE, null = "null")
