#!/usr/bin/env bash
# The monthly refit, mirroring .github/workflows/monthly-refit.yml, but run as a
# Cloud Run job instead of GitHub Actions. Runs inside a fresh clone (see
# bootstrap.sh). The R packages are already in the image; prices are downloaded
# fresh and the parity tests must pass before anything is pushed or deployed.
set -euo pipefail

git config user.name "cloud-run-refit[bot]"
git config user.email "cloud-run-refit@users.noreply.github.com"

Rscript research/00_data.R
Rscript research/02_basket.R

# Parity tests run in an isolated venv (the base image is R-first).
python3 -m venv /tmp/parity
/tmp/parity/bin/pip install --no-cache-dir -r service/requirements.txt pytest
( cd service && PATH=/tmp/parity/bin:$PATH python -m pytest -q tests )

git add data/basket.json data/h1_daily.csv
if git diff --cached --quiet; then
  echo "No change in fits; nothing to commit."
else
  git commit -m "Monthly refit to $(jq -r '.fits[-1].train_end' data/basket.json)"
  git push origin "HEAD:${GH_REF:-main}"
fi

# Deploy the dashboard. Azure trusts this job's Google identity token (workload
# identity federation), so no Azure secret is stored anywhere.
: "${AZURE_CLIENT_ID:?}" "${AZURE_TENANT_ID:?}" "${AZ_SUBSCRIPTION:?}"
audience="${AZURE_AUDIENCE:-api://AzureADTokenExchange}"
token="$(curl -sf -H 'Metadata-Flavor: Google' \
  "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity?audience=${audience}")"
az login --service-principal -u "$AZURE_CLIENT_ID" -t "$AZURE_TENANT_ID" \
  --federated-token "$token" -o none
az account set --subscription "$AZ_SUBSCRIPTION"

TAG="refit-$(jq -r '.fits[-1].train_end' data/basket.json)-$(date +%s)" \
  AZ_SUBSCRIPTION="$AZ_SUBSCRIPTION" bash deploy/azure.sh
