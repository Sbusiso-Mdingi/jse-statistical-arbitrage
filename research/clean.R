# Load SBK and NED adjusted closes, drop bad prints and align trading days.
#
# A bad print is a single day whose price jumps by more than 40% and reverses
# the next day (for example SBK on 25 April 2025, quoted in rand, not cents).
# The service applies the same rule to live data.
drop_bad_prints <- function(df, jump = 0.4) {
  repeat {
    r <- diff(log(df$adjusted))
    n <- length(r)
    bad <- which(abs(r[-n]) > log(1 + jump) & sign(r[-n]) != sign(r[-1]) &
                 abs(r[-n] + r[-1]) < log(1 + jump) / 4) + 1
    if (!length(bad)) return(df)
    df <- df[-bad, ]
  }
}

load_prices <- function(dir) {
  read <- function(f) {
    x <- read.csv(file.path(dir, f), stringsAsFactors = FALSE)
    x$date <- as.Date(x$date)
    x <- x[!is.na(x$adjusted) & x$adjusted > 0, ]
    drop_bad_prints(x)
  }
  s <- read("sbk.csv"); n <- read("ned.csv")
  m <- merge(s[, c("date", "adjusted")], n[, c("date", "adjusted")], by = "date",
             suffixes = c("_sbk", "_ned"))
  data.frame(date = m$date, sbk = m$adjusted_sbk, ned = m$adjusted_ned)
}
