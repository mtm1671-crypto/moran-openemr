param(
    [string]$MysqlContainer = "development-easy-mysql-1",
    [string]$MysqlUser = "root",
    [string]$MysqlPassword = "root",
    [string]$Database = "openemr"
)

$ErrorActionPreference = "Stop"

$env:Path = 'C:\Program Files\Docker\Docker\resources\bin;C:\Program Files\Docker\Docker\resources;C:\Program Files\Docker\cli-plugins;' + $env:Path

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
$sql | docker exec -i $MysqlContainer mariadb "-u$MysqlUser" "-p$MysqlPassword" $Database
