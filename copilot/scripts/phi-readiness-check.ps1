param(
    [switch]$SkipDocker
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$copilotDir = Split-Path -Parent $scriptDir
$repoRoot = Split-Path -Parent $copilotDir
$apiDir = Join-Path $copilotDir "api"
$webDir = Join-Path $copilotDir "web"
$python = Join-Path $apiDir ".venv\Scripts\python.exe"

function Invoke-Checked {
    param(
        [string]$WorkingDirectory,
        [string[]]$Command
    )

    Push-Location $WorkingDirectory
    try {
        & $Command[0] $Command[1..($Command.Length - 1)]
        if ($LASTEXITCODE -ne 0) {
            throw "Command failed with exit code ${LASTEXITCODE}: $($Command -join ' ')"
        }
    }
    finally {
        Pop-Location
    }
}

if (-not (Test-Path $python)) {
    throw "API virtualenv not found at $python"
}

Invoke-Checked $apiDir @($python, "-m", "pytest", "tests", "-q")
Invoke-Checked $apiDir @($python, "-m", "ruff", "check", "app", "tests")
Invoke-Checked $apiDir @($python, "-m", "mypy", "app", "tests")
Invoke-Checked $apiDir @($python, "-m", "pip_audit")

Invoke-Checked $webDir @("npm", "audit", "--audit-level=moderate")
Invoke-Checked $webDir @("npm", "run", "build")
Invoke-Checked $webDir @("npm", "run", "test:e2e", "--", "--project=chromium")

if (-not $SkipDocker) {
    Invoke-Checked $apiDir @("docker", "build", "-t", "agentforge-copilot-api:phi-ready", ".")
    Invoke-Checked $webDir @("docker", "build", "-t", "agentforge-copilot-web:phi-ready", ".")
    Invoke-Checked $repoRoot @("docker", "build", "-t", "agentforge-openemr:phi-ready", ".")
}

Write-Host "PHI readiness checks passed."
