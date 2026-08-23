param(
    [Parameter(Mandatory = $true)][string]$ProjectId,
    [string]$Region = "europe-west1",
    [string]$FirestoreLocation = "eur3",
    [string]$ServiceName = "autonomous-maintenance-0317"
)

$ErrorActionPreference = "Stop"
if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
    throw "gcloud is required. Install Google Cloud CLI first."
}

Write-Host "Target project: $ProjectId"
Write-Host "Cloud Run region: $Region"
Write-Warning "This deploys billable Google Cloud resources. Cloud Run is configured to scale to zero."
$confirmation = Read-Host "Type DEPLOY to continue"
if ($confirmation -ne "DEPLOY") { throw "Deployment cancelled." }

gcloud config set project $ProjectId
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com aiplatform.googleapis.com firestore.googleapis.com pubsub.googleapis.com

gcloud pubsub topics describe maintenance-events --project $ProjectId 2>$null
if ($LASTEXITCODE -ne 0) { gcloud pubsub topics create maintenance-events --project $ProjectId }

gcloud firestore databases describe --database="(default)" --project $ProjectId 2>$null
if ($LASTEXITCODE -ne 0) {
    gcloud firestore databases create --database="(default)" --location=$FirestoreLocation --type=firestore-native --project $ProjectId
}

gcloud run deploy $ServiceName `
    --source . `
    --region $Region `
    --allow-unauthenticated `
    --min-instances 0 `
    --max-instances 2 `
    --memory 1Gi `
    --cpu 1 `
    --timeout 300 `
    --set-env-vars "ENVIRONMENT=production,AGENT_RUNTIME=adk,PERSISTENCE_BACKEND=firestore,EVENT_BACKEND=pubsub,GOOGLE_CLOUD_PROJECT=$ProjectId,GOOGLE_CLOUD_LOCATION=global,GOOGLE_GENAI_USE_VERTEXAI=true,GEMINI_MODEL=gemini-3.5-flash,PUBSUB_TOPIC=maintenance-events,DEMO_STEP_DELAY_SECONDS=0.45"

$serviceUrl = gcloud run services describe $ServiceName --region $Region --format="value(status.url)"
$subscription = "maintenance-worker"
gcloud pubsub subscriptions describe $subscription --project $ProjectId 2>$null
if ($LASTEXITCODE -eq 0) {
    gcloud pubsub subscriptions update $subscription --push-endpoint="$serviceUrl/api/events/pubsub" --project $ProjectId
} else {
    gcloud pubsub subscriptions create $subscription --topic=maintenance-events --push-endpoint="$serviceUrl/api/events/pubsub" --ack-deadline=300 --project $ProjectId
}

Write-Host "Deployment complete: $serviceUrl"
Write-Host "Verify: $serviceUrl/api/health"
