#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${1:?Usage: scripts/deploy.sh PROJECT_ID [REGION]}"
REGION="${2:-europe-west1}"
SERVICE_NAME="autonomous-maintenance-0317"

command -v gcloud >/dev/null || { echo "gcloud is required"; exit 1; }
echo "This deploys billable resources to $PROJECT_ID in $REGION."
read -r -p "Type DEPLOY to continue: " confirmation
[[ "$confirmation" == "DEPLOY" ]] || { echo "Cancelled"; exit 1; }

gcloud config set project "$PROJECT_ID"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com aiplatform.googleapis.com firestore.googleapis.com pubsub.googleapis.com
gcloud pubsub topics describe maintenance-events >/dev/null 2>&1 || gcloud pubsub topics create maintenance-events
gcloud firestore databases describe --database='(default)' >/dev/null 2>&1 || gcloud firestore databases create --database='(default)' --location=eur3 --type=firestore-native
gcloud run deploy "$SERVICE_NAME" --source . --region "$REGION" --allow-unauthenticated --min-instances 0 --max-instances 1 --memory 1Gi --cpu 1 --timeout 300 --set-env-vars "ENVIRONMENT=production,AGENT_RUNTIME=adk,PERSISTENCE_BACKEND=firestore,EVENT_BACKEND=pubsub,GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GOOGLE_CLOUD_LOCATION=global,GOOGLE_GENAI_USE_VERTEXAI=true,GEMINI_MODEL=gemini-3.5-flash,PUBSUB_TOPIC=maintenance-events,DEMO_STEP_DELAY_SECONDS=0.45"
SERVICE_URL="$(gcloud run services describe "$SERVICE_NAME" --region "$REGION" --format='value(status.url)')"
gcloud pubsub subscriptions describe maintenance-worker >/dev/null 2>&1 && gcloud pubsub subscriptions update maintenance-worker --push-endpoint="$SERVICE_URL/api/events/pubsub" || gcloud pubsub subscriptions create maintenance-worker --topic=maintenance-events --push-endpoint="$SERVICE_URL/api/events/pubsub" --ack-deadline=300
echo "Deployment complete: $SERVICE_URL"
