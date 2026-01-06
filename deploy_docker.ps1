# Docker Deployment Script
# Usage: .\deploy_docker.ps1

$PROJECT_ID = "gen-lang-client-0229610994"
$IMAGE_NAME = "fastmcp-plan-agent"
$REGION = "us-central1"
$TAG = "gcr.io/$PROJECT_ID/$IMAGE_NAME"

Write-Host "1. Building Docker image..." -ForegroundColor Cyan
docker build -t $IMAGE_NAME .
if ($LASTEXITCODE -ne 0) { Write-Error "Build failed"; exit 1 }

Write-Host "2. Tagging image as $TAG..." -ForegroundColor Cyan
docker tag $IMAGE_NAME $TAG

Write-Host "3. Pushing image to GCR..." -ForegroundColor Cyan
# Ensure we are authenticated
# gcloud auth configure-docker
docker push $TAG
if ($LASTEXITCODE -ne 0) { Write-Error "Push failed. Make sure Docker is authenticated with gcloud."; exit 1 }

Write-Host "4. Deploying to Cloud Run..." -ForegroundColor Cyan
gcloud run deploy $IMAGE_NAME `
    --image $TAG `
    --project $PROJECT_ID `
    --region $REGION `
    --allow-unauthenticated `
    --set-env-vars PLANNING_MOCK_MODE=true `
    --port 8080

if ($LASTEXITCODE -eq 0) {
    Write-Host "Deployment successful!" -ForegroundColor Green
}
else {
    Write-Host "Deployment failed." -ForegroundColor Red
}
