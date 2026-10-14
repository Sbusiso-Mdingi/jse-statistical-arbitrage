# Monthly refit on Cloud Run

The code lives here on GitHub; only the **scheduled compute** runs on Google
Cloud Run instead of GitHub Actions. Each month a Cloud Run job clones this repo
fresh, downloads prices, refits the bank-basket model, runs the parity tests,
pushes the new fits back to GitHub, and redeploys the Azure dashboard — exactly
what `.github/workflows/monthly-refit.yml` used to do.

## How it fits together

```
Cloud Scheduler ──monthly──> Cloud Run job
                               ├─ git clone this repo @ main        (bootstrap.sh)
                               ├─ Rscript research/00_data.R  (download prices)
                               ├─ Rscript research/02_basket.R  (refit basket)
                               ├─ pytest parity gate (service/)
                               ├─ git push fits back to GitHub      (SSH deploy key from Secret Manager)
                               └─ az login via GCP→Azure federation, then deploy/azure.sh
```

- **No Azure secret is stored.** Azure trusts the job's Google identity token
  (workload identity federation) on the existing `gh-jse-pairs-refit` app, which
  already holds Contributor on `rg-mdingi-previews`.
- **The only secret** is a per-repo SSH deploy key (write access to this repo
  only) in Secret Manager, mounted at `/secrets/deploy_key` and used to push
  fits back — no GitHub token anywhere.
- The heavy R packages (`rugarch`, `VineCopula`, `quantmod`, …) are baked into
  the image; application code comes from the clone, so ordinary code changes
  need no image rebuild. Rebuild only when the R dependency set changes.

## One-time setup

Prerequisite: `deploy/github-identity.sh` has already run (creates the Azure
app). Then:

```bash
AZ_SUBSCRIPTION=<Sequrin - Development subscription id> \
  bash deploy/cloudrun/provision.sh
```

The script generates the deploy key, registers its public half on this repo
(needs `gh` authenticated with repo admin), and stores the private half in
Secret Manager — no token to pass in.

Override `GCP_PROJECT` / `GCP_REGION` if needed (defaults: current gcloud
project, `europe-west1`). The first build compiles the R packages and takes a
while; later runs reuse the image.

## Run it manually

```bash
gcloud run jobs execute jse-pairs-refit --region europe-west1
```

## Cost

A monthly job plus one scheduler entry and a small image sit inside the Cloud
Run / Scheduler / Artifact Registry free tiers — effectively zero.
