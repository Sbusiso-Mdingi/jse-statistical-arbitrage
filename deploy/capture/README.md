# Daily 16:00 price capture

H18 (research/PROTOCOL.md) decides on each bank's 16:00 price: the last trade of the 15:00–16:00 SAST hour. A Cloud Run job at 17:30 Johannesburg time on weekdays reads Yahoo's hourly bars for Standard Bank and Nedbank and stores each session's 16:00 prices in a private bucket, one object per session (`1600/<date>.json`, with the day's raw hourly bars for audit). It writes only objects that do not exist yet, so a missed run fills itself in from the next one (Yahoo keeps about two years of hourly bars) and nothing captured is overwritten. Yahoo's 15:00-bar closes matched the TradingView bars behind H18's development figures exactly on 99% of sessions from December 2023 to March 2026.

- **What it creates** (`provision.sh`, same project and region as the refit job): bucket `jse-pairs-1600-<project number>` (private, uniform access, public access prevented); service account `jse-pairs-capture` (can create objects in that bucket and run this job, nothing else); job `jse-pairs-capture`; scheduler `jse-pairs-capture-daily`, `30 17 * * 1-5` Africa/Johannesburg, created paused.
- **No key.** The job authenticates as its service account through the metadata server.
- **Data terms.** Yahoo's prices are for personal use and are not redistributed: the bucket is private and the public repository never holds them.
- **Cost.** About 250 runs a year of a few seconds, a few hundred kilobytes stored: within the free tiers, at most about $0.10 a month (the scheduler entry, if the billing account already has three).
