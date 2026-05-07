param(
    [string]$Project = "c1ae2188-ab73-4e4c-8c4e-ac49fd5b63a3",
    [string]$Environment = "production",
    [string]$ApiService = "copilot-api",
    [string]$ApiBaseUrl = "https://copilot-api-production-9f84.up.railway.app",
    [switch]$LinkProject,
    [switch]$SkipDeploy,
    [switch]$SkipReadyCheck
)

$ErrorActionPreference = "Stop"

function Invoke-Railway {
    param([string[]]$Arguments)

    & railway @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Railway command failed: railway $($Arguments -join ' ')"
    }
}

Write-Host "Checking Railway CLI authentication."
Invoke-Railway @("whoami")

if ($LinkProject) {
    Write-Host "Linking Railway project '$Project', environment '$Environment', service '$ApiService'."
    Invoke-Railway @(
        "link",
        "--project", $Project,
        "--environment", $Environment,
        "--service", $ApiService
    )
}

Write-Host "Enabling durable document workflow persistence on Railway service '$ApiService'."
Invoke-Railway @(
    "variable",
    "set",
    "--environment", $Environment,
    "--service", $ApiService,
    "--skip-deploys",
    "DOCUMENT_WORKFLOW_PERSISTENCE_ENABLED=true"
)

if (-not $SkipDeploy) {
    $repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
    $apiRoot = Join-Path $repoRoot "copilot\api"
    Write-Host "Deploying Co-Pilot API from '$apiRoot'."
    Invoke-Railway @(
        "up",
        "--environment", $Environment,
        "--service", $ApiService,
        $apiRoot,
        "--path-as-root"
    )
}

if (-not $SkipReadyCheck) {
    $readyUrl = "$($ApiBaseUrl.TrimEnd('/'))/readyz"
    $capabilitiesUrl = "$($ApiBaseUrl.TrimEnd('/'))/api/capabilities"
    Write-Host "Checking $readyUrl."
    $ready = Invoke-RestMethod -Method Get -Uri $readyUrl
    if (-not $ready.ok) {
        $errors = ($ready.errors | ForEach-Object { "- $_" }) -join "`n"
        throw "API readiness failed after deploy.`n$errors"
    }
    if (-not $ready.checks.document_workflow_persistence_ready) {
        throw "document_workflow_persistence_ready was not true in /readyz."
    }

    Write-Host "Checking $capabilitiesUrl."
    $capabilities = Invoke-RestMethod -Method Get -Uri $capabilitiesUrl
    if (-not $capabilities.providers.document_workflow_persistence_ready) {
        throw "document_workflow_persistence_ready was not true in /api/capabilities."
    }
}

Write-Host "Document workflow persistence is enabled and readiness is green."
