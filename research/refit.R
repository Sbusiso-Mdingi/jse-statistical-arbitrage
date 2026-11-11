# One refit under H17 (research/PROTOCOL.md): the margins on every session to T, nothing after.
#
#   Rscript research/refit.R 2026-08-31
#
# At a year end each bank's specification is reselected by BIC over lib.R's grid; at the end of March or
# August the specification in force (the last entry of data/refits.json) keeps its form and its parameters
# are re-estimated. Writes research/results/refit_<T>.json; research/refit_export.py does the rest.

suppressPackageStartupMessages({
  library(rugarch)
  library(jsonlite)
  library(parallel)
})

args <- commandArgs(trailingOnly = TRUE)
TE <- as.Date(args[1])
stopifnot(!is.na(TE), format(TE + 1, "%d") == "01")
CORES <- max(1, detectCores() - 1)
source("research/clean.R")
source("research/lib.R")

px <- load_prices("data/raw")
px <- px[px$date <= TE, ]
vix <- read.csv("data/raw/vix.csv", stringsAsFactors = FALSE)
vix$date <- as.Date(vix$date)
vix <- vix[!is.na(vix$vix) & vix$date < TE, ]
idx <- findInterval(as.numeric(px$date) - 1, as.numeric(vix$date))
px$vix <- ifelse(idx > 0, vix$vix[pmax(idx, 1)] / 100, NA)
px <- px[!is.na(px$vix), ]
d <- data.frame(date = px$date[-1], r_sbk = diff(log(px$sbk)), r_ned = diff(log(px$ned)), vix = px$vix[-1])
if (max(d$date) < TE - 7) stop("no prices in the last week before ", TE, "; the download is stale")

reselect <- format(TE, "%m-%d") == "12-31"
prior <- tail(fromJSON("data/refits.json", simplifyVector = FALSE)$refits, 1)[[1]]
if (prior$train_end >= format(TE)) stop("data/refits.json already has a refit on or after ", TE)

out <- list(train_end = format(TE), last_session = format(max(d$date)), sessions = nrow(d), reselected = reselect)
for (bank in c("sbk", "ned")) {
  r <- d[[paste0("r_", bank)]]
  if (reselect) {
    f <- select_marginal(r, d$vix)
  } else {
    s <- prior[[bank]]
    g <- data.frame(model = s$model, arma = s$arma, dist = s$dist, vix = s$vix, stringsAsFactors = FALSE)
    f <- fit_one(g, r, d$vix)
    if (!is.null(f)) f$n_converged <- 1
  }
  out[[bank]] <- if (is.null(f)) list(ok = FALSE) else c(list(ok = TRUE), describe(f))
  cat(sprintf("%s to %s: %s\n", toupper(bank), format(TE),
              if (is.null(f)) "not converged, previous parameters stay" else sprintf("%s(%s) %s%s, BIC %.1f", f$g$model, f$g$arma, f$g$dist, if (f$g$vix) "+VIX" else "", f$bic)))
}
write_json(out, sprintf("research/results/refit_%s.json", format(TE)), digits = 12, auto_unbox = TRUE)
