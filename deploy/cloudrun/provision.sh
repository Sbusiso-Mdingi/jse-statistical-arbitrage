#!/usr/bin/env bash
# One-off: stand up the scheduled refit (research/PROTOCOL.md, H17) on Google Cloud Run.
# GitHub stays the home of the code; the job pushes each refit to a refit/<date> branch.
#
#   bash deploy/cloudrun/provision.sh
#
# No GitHub token is stored, and the job holds no cloud credential beyond its own project: it never
# deploys. Pushes use a per-repo SSH deploy key: generated here, the public half registered on this
# repo (write) and the private half kept in Secret Manager and mounted into the job.
set -euo pipefail

PROJECT="${GCP_PROJECT:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${GCP_REGION:-europe-west1}"

REPO=Sbusiso-Mdingi/jse-statistical-arbitrage
AR_REPO=portfolio-refit               # Artifact Registry docker repo
IMAGE_NAME=jse-pairs-refit
JOB=jse-pairs-refit
SA_NAME=jse-pairs-refit
SECRET=jse-pairs-deploy-key
SCHEDULE="0 6 1 1,4,9 *"              # 1 January, 1 April, 1 September, 06:00 Johannesburg

SA="${SA_NAME}@${PROJECT}.iam.gserviceaccount.com"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${AR_REPO}/${IMAGE_NAME}:latest"

echo "Project ${PROJECT} / region ${REGION}."

echo "==> Enabling APIs"
gcloud services enable --project "$PROJECT" \
  run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com \
  cloudscheduler.googleapis.com secretmanager.googleapis.com

echo "==> Artifact Registry"
gcloud artifacts repositories describe "$AR_REPO" --project "$PROJECT" --location "$REGION" >/dev/null 2>&1 \
  || gcloud artifacts repositories create "$AR_REPO" --project "$PROJECT" --location "$REGION" \
       --repository-format=docker --description="Portfolio monthly-refit images"

echo "==> Cloud Build builder permissions"
# New projects run Cloud Build as the Compute Engine default service account; it
# needs the builder role to read the source upload and push to Artifact Registry.
PNUM="$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')"
gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:${PNUM}-compute@developer.gserviceaccount.com" \
  --role=roles/cloudbuild.builds.builder >/dev/null

echo "==> Service account"
gcloud iam service-accounts describe "$SA" --project "$PROJECT" >/dev/null 2>&1 \
  || gcloud iam service-accounts create "$SA_NAME" --project "$PROJECT" \
       --display-name="JSE pairs refit (Cloud Run)"
# A freshly created SA is eventually consistent; wait for it to become visible.
SA_SUBJECT=""
for _ in 1 2 3 4 5 6; do
  SA_SUBJECT="$(gcloud iam service-accounts describe "$SA" --project "$PROJECT" --format='value(uniqueId)' 2>/dev/null || true)"
  [ -n "$SA_SUBJECT" ] && break
  sleep 5
done
[ -n "$SA_SUBJECT" ] || { echo "ERROR: service account $SA not visible yet; re-run." >&2; exit 1; }

echo "==> SSH deploy key (push auth; no token stored)"
if ! gcloud secrets describe "$SECRET" --project "$PROJECT" >/dev/null 2>&1; then
  k="$(mktemp -u)"
  ssh-keygen -t ed25519 -N '' -C cloud-run-refit -f "$k" >/dev/null
  gh api --method POST "repos/${REPO}/keys" -f title=cloud-run-refit \
    -f key="$(cat "$k.pub")" -F read_only=false >/dev/null
  gcloud secrets create "$SECRET" --project "$PROJECT" --replication-policy=automatic --data-file="$k"
  rm -f "$k" "$k.pub"
fi
gcloud secrets add-iam-policy-binding "$SECRET" --project "$PROJECT" \
  --member="serviceAccount:${SA}" --role=roles/secretmanager.secretAccessor >/dev/null

echo "==> Build image in Cloud Build"
cfg="$(mktemp).yaml"
cat > "$cfg" <<YAML
steps:
- name: gcr.io/cloud-builders/docker
  args: ["build","-t","${IMAGE}","-f","deploy/cloudrun/Dockerfile","."]
images: ["${IMAGE}"]
options:
  logging: CLOUD_LOGGING_ONLY
YAML
gcloud builds submit --project "$PROJECT" --region "$REGION" --config "$cfg" .
rm -f "$cfg"

echo "==> Cloud Run job"
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMAGE" --service-account "$SA" \
  --max-retries 1 --task-timeout 9000 --cpu 2 --memory 4Gi \
  --set-env-vars "GH_REPO=${REPO},GH_REF=main" \
  --set-secrets "/secrets/deploy_key=${SECRET}:latest"

echo "==> Cloud Scheduler (three runs a year; the name is kept from the old monthly job)"
gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:${SA}" --role=roles/run.developer >/dev/null
RUN_URL="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT}/jobs/${JOB}:run"
if gcloud scheduler jobs describe "${JOB}-monthly" --project "$PROJECT" --location "$REGION" >/dev/null 2>&1; then
  VERB=update
else
  VERB=create
fi
gcloud scheduler jobs "$VERB" http "${JOB}-monthly" --project "$PROJECT" --location "$REGION" \
  --schedule="$SCHEDULE" --time-zone="Africa/Johannesburg" \
  --uri="$RUN_URL" --http-method=POST \
  --oauth-service-account-email="$SA"

echo
echo "Done. Trigger a run now with:"
echo "  gcloud run jobs execute ${JOB} --project ${PROJECT} --region ${REGION}"
