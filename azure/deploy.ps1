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
#   - 1 Azure Container Registry (images built via `az acr build --no-logs`
#     from the existing Dockerfiles, then deployed from the registry)
#   - 2 Azure Container Apps (backend + frontend)
#
# Usage:
#   cd azure
#   ./deploy.ps1
#
# After it finishes, it prints the backend and frontend URLs. Use the
# frontend URL to actually use the app.

$ErrorActionPreference = "Stop"

# ---- Force UTF-8 console I/O ----------------------------------------------
# Belt-and-suspenders: force UTF-8 everywhere in case any `az` subcommand
# prints non-ASCII output. (The specific crash this used to guard against --
# `az containerapp up --source` streaming remote ACR build logs through
# azure-cli's colorama wrapper -- is now avoided entirely by never using
# `--source`; see the Container Registry section below.)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
try { chcp.com 65001 | Out-Null } catch {}

# ---- Helper: run an `az` lookup that is EXPECTED to fail when the resource -
# doesn't exist yet (e.g. "does this resource group already exist?"). With
# $ErrorActionPreference = "Stop", PowerShell turns a native command's stderr
# output into a terminating error the moment it's produced -- BEFORE a
# `2>$null` redirection gets a chance to silence it. So a plain `2>$null` is
# not enough to make these "not found is fine" lookups non-fatal; the
# preference has to be relaxed for the duration of the call instead.
function Invoke-AzQuiet {
    param([scriptblock]$ScriptBlock)
    $prevPreference = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    try {
        & $ScriptBlock
    } finally {
        $ErrorActionPreference = $prevPreference
    }
}

# ---- Helper: `az containerapp up` is NOT self-healing when the target app --
# is already stuck in ProvisioningState 'Failed' (e.g. left over from an
# earlier run that failed mid-deploy, such as a bad image). Calling
# `containerapp up` against it throws `(ResourceNotProvisioned)` instead of
# fixing it. Delete-and-recreate is the reliable fix, so check first and only
# delete when actually needed (this keeps re-runs fast when nothing is stuck).
function Remove-FailedContainerApp {
    param([string]$Name, [string]$ResourceGroup)
    $state = Invoke-AzQuiet { az containerapp show --name $Name --resource-group $ResourceGroup --query "properties.provisioningState" -o tsv 2>$null }
    if ($state -eq "Failed") {
        Write-Host "    (containerapp $Name is stuck in ProvisioningState 'Failed' -- deleting it so it can be recreated cleanly)" -ForegroundColor Yellow
        az containerapp delete --name $Name --resource-group $ResourceGroup --yes --only-show-errors | Out-Null
    }
}

# ---- Paths (resolved relative to this script, not the caller's cwd) -------
$BackendSourcePath = Join-Path $PSScriptRoot "..\backend"
$FrontendSourcePath = Join-Path $PSScriptRoot "..\frontend"

# ---- Config (edit if you like) --------------------------------------------
$Prefix = "lifehub"                 # must be globally-unique-ish; tweak if a name is taken
$Location = "norwayeast"            # change to a region close to you (westeurope is currently closed to new customers on this subscription)
$ResourceGroup = "$Prefix-rg"
$PgServerName = "$Prefix-pg-$(Get-Random -Minimum 1000 -Maximum 9999)"
$PgAdminUser = "lifehubadmin"
$PgDbName = "lifehub"
$BackendAppName = "$Prefix-backend"
$FrontendAppName = "$Prefix-frontend"
$AcrName = "$($Prefix)acr$(Get-Random -Minimum 1000 -Maximum 9999)"  # ACR names: alphanumeric only, globally unique

# ---- Sanity checks ----------------------------------------------------------
$account = Invoke-AzQuiet { az account show 2>$null } | ConvertFrom-Json
if (-not $account) {
    Write-Error "Not logged in to Azure CLI. Run 'az login' with your PERSONAL Microsoft account (the one linked to the FTE Azure subscription), then re-run this script."
    exit 1
}
Write-Host "Using Azure subscription: $($account.name) ($($account.id))" -ForegroundColor Cyan
Write-Host "If this is NOT your personal FTE-credit subscription, Ctrl+C now and run 'az account set --subscription <correct-one>'." -ForegroundColor Yellow
Start-Sleep -Seconds 5

az extension add --name containerapp --upgrade --only-show-errors

# ---- Resource group ----------------------------------------------------------
$existingGroup = Invoke-AzQuiet { az group show --name $ResourceGroup 2>$null } | ConvertFrom-Json
if ($existingGroup) {
    # Reuse the existing group's region so every resource in this run lands in
    # the same place (Azure won't let a group be "moved" to a new location).
    $Location = $existingGroup.location
    Write-Host "`n==> Resource group $ResourceGroup already exists in $Location -- reusing it" -ForegroundColor Cyan
} else {
    Write-Host "`n==> Creating resource group $ResourceGroup in $Location" -ForegroundColor Cyan
    az group create --name $ResourceGroup --location $Location --only-show-errors | Out-Null
}

# ---- Container Registry (created explicitly, NOT via `containerapp up --source`) -
# `containerapp up --source` streams remote ACR build logs through azure-cli's
# colorama wrapper and crashes with a UnicodeEncodeError on certain non-ASCII
# build output (pip/npm package metadata), even with UTF-8 console encoding
# forced above -- colorama's console writer doesn't respect it. The only
# reliable fix is to never use `--source` at all: build images with
# `az acr build --no-logs` (which queues+waits for the build but skips the
# crashing log stream) and then deploy pre-built images with `containerapp up
# --image`.
$existingAcr = Invoke-AzQuiet { az acr list --resource-group $ResourceGroup --query "[?starts_with(name, '$($Prefix)acr')] | [0]" 2>$null } | ConvertFrom-Json
if ($existingAcr) {
    $AcrName = $existingAcr.name
    Write-Host "`n==> Reusing existing Container Registry $AcrName" -ForegroundColor Cyan
} else {
    Write-Host "`n==> Creating Container Registry $AcrName (Basic SKU)" -ForegroundColor Cyan
    az acr create `
        --resource-group $ResourceGroup `
        --name $AcrName `
        --sku Basic `
        --admin-enabled true `
        --only-show-errors | Out-Null
}
az acr update --name $AcrName --admin-enabled true --only-show-errors | Out-Null
$AcrServer = "$AcrName.azurecr.io"
$AcrCreds = az acr credential show --name $AcrName --query "{username:username, password:passwords[0].value}" -o json | ConvertFrom-Json
$AcrUsername = $AcrCreds.username
$AcrPassword = $AcrCreds.password

# ---- Postgres Flexible Server --------------------------------------------
# Reuse an existing "$Prefix-pg-*" server from a prior run instead of always
# minting a new random one (avoids orphaned/duplicate-billed servers when
# this script is re-run after a failure further down the pipeline).
$existingPg = Invoke-AzQuiet { az postgres flexible-server list --resource-group $ResourceGroup --query "[?starts_with(name, '$Prefix-pg-')] | [0]" 2>$null } | ConvertFrom-Json

if ($existingPg) {
    $PgServerName = $existingPg.name
    Write-Host "`n==> Reusing existing Postgres Flexible Server $PgServerName" -ForegroundColor Cyan
    Write-Host "    (password unknown -- resetting it so this run can connect)" -ForegroundColor Cyan
    $PgAdminPassword = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 24 | ForEach-Object { [char]$_ })
    az postgres flexible-server update `
        --resource-group $ResourceGroup `
        --name $PgServerName `
        --admin-password $PgAdminPassword `
        --only-show-errors | Out-Null
} else {
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
}

Write-Host "==> Ensuring database '$PgDbName' exists" -ForegroundColor Cyan
az postgres flexible-server db create `
    --resource-group $ResourceGroup `
    --server-name $PgServerName `
    --database-name $PgDbName `
    --only-show-errors | Out-Null

$PgHost = "$PgServerName.postgres.database.azure.com"
$DatabaseUrl = "postgresql+psycopg" + "://" + $PgAdminUser + ":" + $PgAdminPassword + "@" + $PgHost + ":5432/" + $PgDbName + "?sslmode=require"

# ---- Secrets ----------------------------------------------------------------
$SessionSecret = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 48 | ForEach-Object { [char]$_ })

# ---- Optional meal assistant (chat) config ---------------------------------
# The assistant/chat feature is OFF unless $env:ASSISTANT_API_KEY is set in
# the shell running this script (never hardcode a key here). Defaults target
# Groq's free-tier OpenAI-compatible API; override $env:ASSISTANT_BASE_URL /
# $env:ASSISTANT_MODEL for a different OpenAI-compatible provider (e.g. xAI's
# Grok at https://api.x.ai/v1).
$AssistantApiKey = $env:ASSISTANT_API_KEY
$AssistantBaseUrl = if ($env:ASSISTANT_BASE_URL) { $env:ASSISTANT_BASE_URL } else { "https://api.groq.com/openai/v1" }
$AssistantModel = if ($env:ASSISTANT_MODEL) { $env:ASSISTANT_MODEL } else { "openai/gpt-oss-120b" }
if (-not $AssistantApiKey) {
    Write-Host "`n(ASSISTANT_API_KEY not set in this shell -- meal assistant chat will stay disabled. Set `$env:ASSISTANT_API_KEY before re-running to enable it.)" -ForegroundColor Yellow
}

# ---- Backend container app (built from ./backend via its Dockerfile) -----
Write-Host "`n==> Building backend image via ACR (this can take a few minutes)" -ForegroundColor Cyan
az acr build `
    --registry $AcrName `
    --image "lifehub-backend:latest" `
    $BackendSourcePath `
    --no-logs `
    --only-show-errors | Out-Null

Write-Host "`n==> Deploying backend container app" -ForegroundColor Cyan
Remove-FailedContainerApp -Name $BackendAppName -ResourceGroup $ResourceGroup
$BackendEnvVars = @(
    "ENVIRONMENT=production",
    "DATABASE_URL=$DatabaseUrl",
    "SESSION_SECRET_KEY=$SessionSecret",
    "MIN_PASSWORD_LENGTH=10",
    "CORS_ORIGINS=*"
)
if ($AssistantApiKey) {
    $BackendEnvVars += "ASSISTANT_API_KEY=$AssistantApiKey"
    $BackendEnvVars += "ASSISTANT_BASE_URL=$AssistantBaseUrl"
    $BackendEnvVars += "ASSISTANT_MODEL=$AssistantModel"
}
az containerapp up `
    --name $BackendAppName `
    --resource-group $ResourceGroup `
    --location $Location `
    --image "$AcrServer/lifehub-backend:latest" `
    --registry-server $AcrServer `
    --registry-username $AcrUsername `
    --registry-password $AcrPassword `
    --ingress external `
    --target-port 8000 `
    --env-vars $BackendEnvVars

$BackendFqdn = az containerapp show --name $BackendAppName --resource-group $ResourceGroup --query "properties.configuration.ingress.fqdn" -o tsv
$BackendUrl = "https://$BackendFqdn"
Write-Host "Backend deployed at: $BackendUrl" -ForegroundColor Green

Write-Host "`n==> Running database migrations" -ForegroundColor Cyan
Invoke-AzQuiet { az containerapp exec --name $BackendAppName --resource-group $ResourceGroup --command "alembic upgrade head" 2>$null }

# ---- Frontend container app -------------------------------------------------
# `containerapp up --source` has no build-arg passthrough anyway, and Vite
# needs VITE_API_BASE_URL baked in at build time, so this one was always built
# via `az acr build` -- just add `--no-logs` for the same reason as backend.
Write-Host "`n==> Building frontend image via ACR (VITE_API_BASE_URL=$BackendUrl baked in)" -ForegroundColor Cyan
az acr build `
    --registry $AcrName `
    --image "lifehub-frontend:latest" `
    --build-arg "VITE_API_BASE_URL=$BackendUrl" `
    $FrontendSourcePath `
    --no-logs `
    --only-show-errors | Out-Null

Write-Host "`n==> Deploying frontend container app" -ForegroundColor Cyan
Remove-FailedContainerApp -Name $FrontendAppName -ResourceGroup $ResourceGroup
az containerapp up `
    --name $FrontendAppName `
    --resource-group $ResourceGroup `
    --location $Location `
    --image "$AcrServer/lifehub-frontend:latest" `
    --registry-server $AcrServer `
    --registry-username $AcrUsername `
    --registry-password $AcrPassword `
    --ingress external `
    --target-port 80

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
