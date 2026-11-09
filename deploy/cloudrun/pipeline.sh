#!/usr/bin/env bash
# The monthly refit of the earlier basket stage, run as a Cloud Run job inside a
# fresh clone (see bootstrap.sh). The R packages are already in the image; prices
# are downloaded fresh and the parity tests must pass before anything is pushed or
# deployed.
set -euo pipefail

# Retired 9 November 2026: the project is Standard Bank against Nedbank, frozen on
# 31 March 2026, and the service no longer carries the basket. Refitting it here would
# push basket files and redeploy over the pair. Stop before touching anything.
echo "pipeline.sh is retired; see deploy/cloudrun/README.md" >&2
exit 1

git config user.name "cloud-run-refit[bot]"
git config user.email "cloud-run-refit@users.noreply.github.com"

Rscript research/00_data.R
Rscript research/02_basket.R

# Python runs in an isolated venv (the base image is R-first).
python3 -m venv /tmp/parity
/tmp/parity/bin/pip install --no-cache-dir -r service/requirements.txt pytest

# The score-driven copula (H9) for the new fit, the re-measured headline, and the dashboard's research.json.
/tmp/parity/bin/python research/models/export_gas.py
/tmp/parity/bin/python research/edge.py
/tmp/parity/bin/python research/export_research.py

# Parity tests, including the score-driven copula against the research record.
( cd service && PATH=/tmp/parity/bin:$PATH python -m pytest -q tests )

git add data/basket.json data/h1_daily.csv data/basket_gas.json data/research.json \
        research/results/copulas_basket.csv research/results/edge.json
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
