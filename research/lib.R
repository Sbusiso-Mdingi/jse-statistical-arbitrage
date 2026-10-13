# Shared ARMA-GARCH and copula helpers for the walk-forward scripts.

COPULA_FAMILIES <- c(1, 2, 3, 4, 5, 13, 14)

GRID <- expand.grid(
  model = c("sGARCH", "gjrGARCH", "eGARCH"),
  arma = c("0,0", "1,0", "1,1"),
  dist = c("norm", "std"),
  vix = c(FALSE, TRUE),
  stringsAsFactors = FALSE
)

make_spec <- function(g, vx, fixed = NULL) {
  arma <- as.integer(strsplit(g$arma, ",")[[1]])
  ugarchspec(
    variance.model = list(model = g$model, garchOrder = c(1, 1),
                          external.regressors = if (g$vix) matrix(vx, ncol = 1) else NULL),
    mean.model = list(armaOrder = arma, include.mean = TRUE),
    distribution.model = g$dist,
    fixed.pars = if (is.null(fixed)) list() else as.list(fixed)
  )
}

fit_one <- function(g, r, vx) {
  fit <- tryCatch(
    suppressWarnings(ugarchfit(make_spec(g, vx), r, solver = "hybrid")),
    error = function(e) NULL
  )
  if (is.null(fit) || fit@fit$convergence != 0) return(NULL)
  ic <- infocriteria(fit)
  list(g = g, fit = fit, bic = ic[2], coef = coef(fit))
}

select_marginal <- function(r, vx) {
  fits <- mclapply(seq_len(nrow(GRID)), function(i) fit_one(GRID[i, ], r, vx), mc.cores = CORES)
  fits <- Filter(Negate(is.null), fits)
  bics <- sapply(fits, `[[`, "bic")
  best <- fits[[which.min(bics)]]
  best$n_converged <- length(fits)
  best
}

pit <- function(z, dist, coef) {
  u <- if (dist == "std") pdist("std", z, mu = 0, sigma = 1, shape = coef[["shape"]]) else pnorm(z)
  pmin(pmax(u, 1e-6), 1 - 1e-6)
}

# Filter a series with frozen parameters; n.old keeps the fit's initialisation.
filter_marginal <- function(sel, r, vx, n_train) {
  spec <- make_spec(sel$g, vx, fixed = sel$coef)
  f <- ugarchfilter(spec, r, n.old = n_train)
  mu <- as.numeric(fitted(f))
  sigma <- as.numeric(sigma(f))
  z <- (r - mu) / sigma
  list(mu = mu, sigma = sigma, z = z, u = pit(z, sel$g$dist, sel$coef))
}

describe <- function(sel) {
  list(
    model = sel$g$model, arma = sel$g$arma, dist = sel$g$dist, vix = sel$g$vix,
    bic = unname(sel$bic), converged = sel$n_converged,
    coef = as.list(sel$coef)
  )
}

