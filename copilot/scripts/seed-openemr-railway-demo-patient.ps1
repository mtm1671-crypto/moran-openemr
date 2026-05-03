param(
    [string]$Project = "c1ae2188-ab73-4e4c-8c4e-ac49fd5b63a3",
    [string]$Environment = "production",
    [string]$DatabaseService = "MySQL",
    [string]$Database = "openemr",
    [switch]$UseInjectedRailwayVariables
)

$ErrorActionPreference = "Stop"

if ($Database -notmatch '^[A-Za-z0-9_]+$') {
    throw "Database name contains unsupported characters: $Database"
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$sqlFiles = @(
    "seed-openemr-demo-patient.sql",
    "seed-openemr-demo-population.sql",
    "seed-openemr-demo-notes.sql"
)
$sqlParts = foreach ($sqlFile in $sqlFiles) {
    $sqlPath = Join-Path $scriptDir $sqlFile
    if (-not (Test-Path -LiteralPath $sqlPath)) {
        throw "Seed SQL file not found: $sqlPath"
    }
    Get-Content -LiteralPath $sqlPath -Raw
}
$sql = $sqlParts -join "`n`n"

if (-not $UseInjectedRailwayVariables) {
    $railwayArgs = @(
        "run",
        "--project", $Project,
        "--environment", $Environment,
        "--service", $DatabaseService,
        "--",
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", $PSCommandPath,
        "-UseInjectedRailwayVariables",
        "-Database", $Database
    )

    Write-Host "Seeding demo patients through Railway '$DatabaseService' TCP proxy in '$Environment'."
    & railway @railwayArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Railway seed failed. Confirm 'railway login' is active and Docker is running."
    }
    exit 0
}

$requiredEnv = @("RAILWAY_TCP_PROXY_DOMAIN", "RAILWAY_TCP_PROXY_PORT", "MYSQL_ROOT_PASSWORD")
foreach ($name in $requiredEnv) {
    if (-not [Environment]::GetEnvironmentVariable($name)) {
        throw "$name is required from the Railway database service variables."
    }
}

$mysqlCommand = "mysql -h `"`$RAILWAY_TCP_PROXY_DOMAIN`" -P `"`$RAILWAY_TCP_PROXY_PORT`" -u root `"-p`$MYSQL_ROOT_PASSWORD`" $Database"
$dockerArgs = @(
    "run",
    "-i",
    "--rm",
    "-e", "RAILWAY_TCP_PROXY_DOMAIN",
    "-e", "RAILWAY_TCP_PROXY_PORT",
    "-e", "MYSQL_ROOT_PASSWORD",
    "mysql:9.4",
    "sh",
    "-lc",
    $mysqlCommand
)

$sql | docker @dockerArgs
if ($LASTEXITCODE -ne 0) {
    throw "Docker MySQL seed command failed."
}
