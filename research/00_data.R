# Download daily adjusted prices for the six JSE banks from Yahoo and VIX from FRED.
suppressPackageStartupMessages({ library(quantmod); library(xts) })
dir.create("data/raw", showWarnings = FALSE, recursive = TRUE)
get_adj <- function(sym) {
  x <- getSymbols(sym, src = "yahoo", from = "2005-01-01", auto.assign = FALSE)
  data.frame(date = index(x), close = as.numeric(Cl(x)), adjusted = as.numeric(Ad(x)))
}
banks <- c(sbk = "SBK.JO", ned = "NED.JO", fsr = "FSR.JO", abg = "ABG.JO", cpi = "CPI.JO", inl = "INL.JO")
px <- lapply(banks, get_adj)
for (b in names(px)) write.csv(px[[b]], file.path("data/raw", paste0(b, ".csv")), row.names = FALSE)
# curl over HTTP/1.1 with retries: R's own reader fails on FRED's HTTP/2 from Cloud Run.
tmp <- tempfile(fileext = ".csv")
if (system2("curl", c("-sfL", "--http1.1", "--retry", "5", "--retry-all-errors", "-o", tmp,
                      shQuote("https://fred.stlouisfed.org/graph/fredgraph.csv?id=VIXCLS"))) != 0) stop("VIX download failed")
vix <- read.csv(tmp, na.strings = ".")
names(vix) <- c("date", "vix")
write.csv(vix, "data/raw/vix.csv", row.names = FALSE)
cat(sapply(px, nrow), nrow(vix), "\n")
