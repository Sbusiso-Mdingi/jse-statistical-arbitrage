# Scheduled refit on Cloud Run

The models refit at the end of March, August and December on data to that date only (research/PROTOCOL.md, H17, and its amendment of 11 November 2026). A Cloud Run job does the fitting three times a year and stops at a branch: it never deploys and never touches main.

## How it fits together

```
Cloud Scheduler ── 1 Jan, 1 Apr, 1 Sep, 06:00 Johannesburg ──> Cloud Run job jse-pairs-refit
   ├─ git clone this repo @ main                       (bootstrap.sh, SSH deploy key)
   ├─ Rscript research/00_data.R                        (fresh prices)
   ├─ Rscript research/refit.R <month end>              (margins; reselection at the year end)
   ├─ python research/refit_export.py <month end>       (PITs, GAS copula, state; appends data/refits.json)
   ├─ pytest parity gate (service/)
   └─ git push refit/<month end>                        (nothing deployed)
```

The new entry in `data/refits.json` has no `applies_from`, so even if the branch were deployed as it is, the service would not use it.

## Taking a refit live (a person, after review)

```bash
git fetch origin && git merge origin/refit/2026-12-31          # after reading the diff
python3 research/refit_apply.py                                # used from the next weekday
AZ_SUBSCRIPTION=<Sequrin - Development id> TAG=<tag> bash deploy/azure.sh
git commit -am "Refit to 2026-12-31 applies from <date>" && git push origin main
```

## Run it by hand

A test run on a non-refit month end, pushed under a throwaway prefix:

```bash
gcloud run jobs execute jse-pairs-refit --region europe-west1 --wait \
  --update-env-vars REFIT_DATE=2026-10-31,BRANCH_PREFIX=dryrun
git push origin --delete dryrun/2026-10-31                     # afterwards
```

## Setup

`provision.sh` (one-off, already run) builds the image, creates the service account, the deploy key (write access to this repo only, private half in Secret Manager) and the job and scheduler. The R packages are baked into the image; application code comes from the clone, so code changes need no rebuild.

## Cost

Three runs a year of a few minutes each, one scheduler entry and a small image: about $0.10 to $0.30 a month, mostly image storage.
