#!/usr/bin/env bash
# One-off: the daily 16:00 price capture for H18 (research/PROTOCOL.md) on Google Cloud, in the refit job's project
# and region. Creates a private bucket, a service account that can only create objects in it and run this job, the
# image, the job, and a scheduler entry left PAUSED (resume it by hand once the user has seen what was created).
#
#   bash deploy/capture/provision.sh
#
# No key is created or stored: the job authenticates as its service account through the metadata server.
set -euo pipefail

PROJECT="${GCP_PROJECT:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${GCP_REGION:-europe-west1}"
PNUM="$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')"
BUCKET="jse-pairs-1600-${PNUM}"
SA_NAME=jse-pairs-capture
SA="${SA_NAME}@${PROJECT}.iam.gserviceaccount.com"
JOB=jse-pairs-capture
AR_REPO=portfolio-refit
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${AR_REPO}/${JOB}:latest"
SCHEDULE="30 17 * * 1-5"   # 17:30 Johannesburg, Monday to Friday

echo "==> Bucket gs://${BUCKET} (private, uniform access, public access prevented)"
gcloud storage buckets describe "gs://${BUCKET}" >/dev/null 2>&1 \
  || gcloud storage buckets create "gs://${BUCKET}" --project "$PROJECT" --location "$REGION" \
       --uniform-bucket-level-access --public-access-prevention --default-storage-class=STANDARD

echo "==> Service account ${SA}"
gcloud iam service-accounts describe "$SA" --project "$PROJECT" >/dev/null 2>&1 \
  || gcloud iam service-accounts create "$SA_NAME" --project "$PROJECT" --display-name="JSE pairs 16:00 price capture (Cloud Run)"
for _ in 1 2 3 4 5 6; do gcloud iam service-accounts describe "$SA" --project "$PROJECT" >/dev/null 2>&1 && break; sleep 5; done
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" --member="serviceAccount:${SA}" --role=roles/storage.objectCreator >/dev/null

echo "==> Image ${IMAGE}"
gcloud builds submit deploy/capture --project "$PROJECT" --region "$REGION" --tag "$IMAGE"

echo "==> Cloud Run job ${JOB}"
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" --image "$IMAGE" --service-account "$SA" \
  --max-retries 2 --task-timeout 300 --cpu 1 --memory 512Mi --set-env-vars "BUCKET=${BUCKET}"
gcloud run jobs add-iam-policy-binding "$JOB" --project "$PROJECT" --region "$REGION" \
  --member="serviceAccount:${SA}" --role=roles/run.invoker >/dev/null

echo "==> Cloud Scheduler ${JOB}-daily (created PAUSED)"
RUN_URL="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT}/jobs/${JOB}:run"
if gcloud scheduler jobs describe "${JOB}-daily" --project "$PROJECT" --location "$REGION" >/dev/null 2>&1; then VERB=update; else VERB=create; fi
gcloud scheduler jobs "$VERB" http "${JOB}-daily" --project "$PROJECT" --location "$REGION" \
  --schedule="$SCHEDULE" --time-zone="Africa/Johannesburg" --uri="$RUN_URL" --http-method=POST --oauth-service-account-email="$SA"
[ "$VERB" = create ] && gcloud scheduler jobs pause "${JOB}-daily" --project "$PROJECT" --location "$REGION"

echo
echo "Test:   gcloud run jobs execute ${JOB} --region ${REGION} --wait"
echo "Enable: gcloud scheduler jobs resume ${JOB}-daily --location ${REGION}"
