# Deploy Geir Life Hub to Azure using the Microsoft FTE Azure Visual Studio
# credit ($150/month). Run this yourself, from your own machine, AFTER:
#   1. Activating the FTE Azure subscription via the internal SharePoint
#      page ("Activating Your Azure Visual Studio FTE Subscription",
#      AELBootCamp site) with a *personal* Microsoft account (not
#      @microsoft.com).
#   2. `az login` with that personal account (NOT your corp @microsoft.com
#      identity -- the FTE Azure subscription is only visible under the
#      personal account it's linked to).
#   3. `az account set --subscription "<name-or-id-of-your-FTE-subscription>"`
#      -- run `az account list -o table` to find it if you're unsure.
#
# This script is intentionally plain `az` CLI (no Bicep/Terraform) to match
# the project's "don't overengineer" guidance. It is idempotent-ish: safe to
# re-run, but a couple of resources (Postgres server name, ACR name) must be
# globally unique, so change $Prefix if a name collides.
#
# What it creates:
#   - 1 resource group
#   - 1 Azure Database for PostgreSQL Flexible Server (Burstable B1ms, the
#     cheapest SKU, well within the $150/month FTE credit for a 2-user
#     household app)
#   - 2 Azure Container Apps (backend + frontend), built directly from the
#     existing Dockerfiles via `az containerapp up --source`, which also
#     auto-provisions a Container Apps Environment + Container Registry.
#
# Usage:
#   cd azure
#   ./deploy.ps1
#
# After it finishes, it prints the backend and frontend URLs. Use the
# frontend URL to actually use the app.

$ErrorActionPreference = "Stop"

# ---- Config (edit if you like) --------------------------------------------
$Prefix = "lifehub"                 # must be globally-unique-ish; tweak if a name is taken
$Location = "westeurope"            # change to a region close to you
$ResourceGroup = "$Prefix-rg"
$PgServerName = "$Prefix-pg-$(Get-Random -Minimum 1000 -Maximum 9999)"
$PgAdminUser = "lifehubadmin"
$PgDbName = "lifehub"
$BackendAppName = "$Prefix-backend"
$FrontendAppName = "$Prefix-frontend"

# ---- Sanity checks ----------------------------------------------------------
$account = az account show 2>$null | ConvertFrom-Json
if (-not $account) {
    Write-Error "Not logged in to Azure CLI. Run 'az login' with your PERSONAL Microsoft account (the one linked to the FTE Azure subscription), then re-run this script."
    exit 1
}
Write-Host "Using Azure subscription: $($account.name) ($($account.id))" -ForegroundColor Cyan
Write-Host "If this is NOT your personal FTE-credit subscription, Ctrl+C now and run 'az account set --subscription <correct-one>'." -ForegroundColor Yellow
Start-Sleep -Seconds 5

az extension add --name containerapp --upgrade --only-show-errors

# ---- Resource group ----------------------------------------------------------
Write-Host "`n==> Creating resource group $ResourceGroup in $Location" -ForegroundColor Cyan
az group create --name $ResourceGroup --location $Location --only-show-errors | Out-Null

# ---- Postgres Flexible Server --------------------------------------------
Write-Host "`n==> Creating Postgres Flexible Server $PgServerName (Burstable B1ms)" -ForegroundColor Cyan
$PgAdminPassword = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 24 | ForEach-Object { [char]$_ })

az postgres flexible-server create `
    --resource-group $ResourceGroup `
    --name $PgServerName `
    --location $Location `
    --admin-user $PgAdminUser `
    --admin-password $PgAdminPassword `
    --sku-name Standard_B1ms `
    --tier Burstable `
    --storage-size 32 `
    --version 16 `
    --public-access 0.0.0.0-255.255.255.255 `
    --yes `
    --only-show-errors | Out-Null

Write-Host "==> Creating database '$PgDbName'" -ForegroundColor Cyan
az postgres flexible-server db create `
    --resource-group $ResourceGroup `
    --server-name $PgServerName `
    --database-name $PgDbName `
    --only-show-errors | Out-Null

$PgHost = "$PgServerName.postgres.database.azure.com"
$DatabaseUrl = "postgresql+psycopg" + "://" + $PgAdminUser + ":" + $PgAdminPassword + "@" + $PgHost + ":5432/" + $PgDbName + "?sslmode=require"

# ---- Secrets ----------------------------------------------------------------
$SessionSecret = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 48 | ForEach-Object { [char]$_ })

# ---- Backend container app (built from ./backend via its Dockerfile) -----
Write-Host "`n==> Deploying backend (this builds the Docker image remotely, can take a few minutes)" -ForegroundColor Cyan
az containerapp up `
    --name $BackendAppName `
    --resource-group $ResourceGroup `
    --location $Location `
    --source "../backend" `
    --ingress external `
    --target-port 8000 `
    --env-vars `
        "ENVIRONMENT=production" `
        "DATABASE_URL=$DatabaseUrl" `
        "SESSION_SECRET_KEY=$SessionSecret" `
        "MIN_PASSWORD_LENGTH=10" `
        "CORS_ORIGINS=*" `
    --only-show-errors

$BackendFqdn = az containerapp show --name $BackendAppName --resource-group $ResourceGroup --query "properties.configuration.ingress.fqdn" -o tsv
$BackendUrl = "https://$BackendFqdn"
Write-Host "Backend deployed at: $BackendUrl" -ForegroundColor Green

Write-Host "`n==> Running database migrations" -ForegroundColor Cyan
az containerapp exec --name $BackendAppName --resource-group $ResourceGroup --command "alembic upgrade head" 2>$null

# ---- Frontend container app -------------------------------------------------
# `az containerapp up --source` has no build-arg passthrough, and Vite needs
# VITE_API_BASE_URL baked in at build time, so we build the image ourselves
# with `az acr build` (using the ACR that `containerapp up` created for the
# backend above) and then point `containerapp up` at that image.
$AcrName = az containerapp show --name $BackendAppName --resource-group $ResourceGroup --query "properties.configuration.registries[0].server" -o tsv
$AcrName = $AcrName -replace "\.azurecr\.io$", ""

Write-Host "`n==> Building frontend image via ACR (VITE_API_BASE_URL=$BackendUrl baked in)" -ForegroundColor Cyan
az acr build `
    --registry $AcrName `
    --image "lifehub-frontend:latest" `
    --build-arg "VITE_API_BASE_URL=$BackendUrl" `
    "../frontend" `
    --only-show-errors | Out-Null

Write-Host "`n==> Deploying frontend container app" -ForegroundColor Cyan
az containerapp up `
    --name $FrontendAppName `
    --resource-group $ResourceGroup `
    --location $Location `
    --image "$AcrName.azurecr.io/lifehub-frontend:latest" `
    --ingress external `
    --target-port 80 `
    --only-show-errors

$FrontendFqdn = az containerapp show --name $FrontendAppName --resource-group $ResourceGroup --query "properties.configuration.ingress.fqdn" -o tsv
$FrontendUrl = "https://$FrontendFqdn"

# ---- Tighten CORS now that we know the frontend URL ------------------------
Write-Host "`n==> Restricting backend CORS_ORIGINS to the frontend URL" -ForegroundColor Cyan
az containerapp update `
    --name $BackendAppName `
    --resource-group $ResourceGroup `
    --set-env-vars "CORS_ORIGINS=$FrontendUrl" `
    --only-show-errors | Out-Null

Write-Host "`n================================================================" -ForegroundColor Green
Write-Host "Done. Open the app at: $FrontendUrl" -ForegroundColor Green
Write-Host "Backend health check:  $BackendUrl/health" -ForegroundColor Green
Write-Host "Resource group (for cleanup/cost tracking): $ResourceGroup" -ForegroundColor Green
Write-Host "To delete everything: az group delete --name $ResourceGroup --yes --no-wait" -ForegroundColor Yellow
Write-Host "================================================================" -ForegroundColor Green
