# Cloud Run Deployment Script
# Usage: .\deploy.ps1

Write-Host "Deploying FastMCP Plan Agent to Cloud Run..."

gcloud run deploy fastmcp-plan-agent `
    --source . `
    --project gen-lang-client-0229610994 `
    --region us-central1 `
    --allow-unauthenticated `
    --set-env-vars PLANNING_MOCK_MODE=true > deploy_output.txt 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host "Deployment output saved to deploy_output.txt"
}
else {
    Write-Host "Deployment failed." -ForegroundColor Red
}
