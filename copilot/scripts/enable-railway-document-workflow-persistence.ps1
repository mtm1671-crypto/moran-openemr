param(
    [string]$Project = "c1ae2188-ab73-4e4c-8c4e-ac49fd5b63a3",
    [string]$Environment = "production",
    [string]$ApiService = "copilot-api",
    [string]$ApiBaseUrl = "https://copilot-api-production-9f84.up.railway.app",
    [int]$ReadyCheckAttempts = 24,
    [int]$ReadyCheckDelaySeconds = 5,
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

function New-CleanApiDeployStage {
    param([string]$RepoRoot)

    $stage = Join-Path $env:TEMP ("copilot-api-railway-" + [guid]::NewGuid().ToString("N"))
    $archive = Join-Path $env:TEMP ("copilot-api-railway-" + [guid]::NewGuid().ToString("N") + ".tar")
    New-Item -ItemType Directory -Path $stage | Out-Null

    & git -C $RepoRoot archive --format=tar -o $archive HEAD:copilot/api
    if ($LASTEXITCODE -ne 0) {
        throw "git archive failed while staging the Co-Pilot API deploy folder."
    }

    & tar -xf $archive -C $stage
    if ($LASTEXITCODE -ne 0) {
        throw "tar extraction failed while staging the Co-Pilot API deploy folder."
    }

    return $stage
}

function Invoke-SmokeJsonCheck {
    param(
        [string]$Uri,
        [string]$Description,
        [scriptblock]$Validate,
        [int]$Attempts,
        [int]$DelaySeconds
    )

    $lastError = $null
    Write-Host "Checking $Description at $Uri (up to $Attempts attempts)."
    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            $response = Invoke-RestMethod -Method Get -Uri $Uri -TimeoutSec 10
            if (& $Validate $response) {
                Write-Host "$Description passed after $attempt attempt(s)."
                return $response
            }
            $lastError = "$Description response did not pass validation."
        } catch {
            $lastError = $_.Exception.Message
        }

        if ($attempt -lt $Attempts) {
            Write-Verbose "$Description attempt $attempt failed: $lastError"
            Start-Sleep -Seconds $DelaySeconds
        }
    }

    throw "$Description did not pass after $Attempts attempt(s). Last error: $lastError"
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
    $apiRoot = New-CleanApiDeployStage -RepoRoot $repoRoot
    Write-Host "Deploying Co-Pilot API from clean staged folder '$apiRoot'."
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
    $ready = Invoke-SmokeJsonCheck `
        -Uri $readyUrl `
        -Description "API readiness" `
        -Attempts $ReadyCheckAttempts `
        -DelaySeconds $ReadyCheckDelaySeconds `
        -Validate { param($body) $body.ok -eq $true }
    if (-not $ready.ok) {
        $errors = ($ready.errors | ForEach-Object { "- $_" }) -join "`n"
        throw "API readiness failed after deploy.`n$errors"
    }
    if (-not $ready.checks.document_workflow_persistence_ready) {
        throw "document_workflow_persistence_ready was not true in /readyz."
    }

    $capabilities = Invoke-SmokeJsonCheck `
        -Uri $capabilitiesUrl `
        -Description "API capabilities" `
        -Attempts $ReadyCheckAttempts `
        -DelaySeconds $ReadyCheckDelaySeconds `
        -Validate { param($body) $body.providers.document_workflow_persistence_ready -eq $true }
    if (-not $capabilities.providers.document_workflow_persistence_ready) {
        throw "document_workflow_persistence_ready was not true in /api/capabilities."
    }
}

Write-Host "Document workflow persistence is enabled and readiness is green."
