param(
    [string]$OpenEmrBaseUrl = "http://localhost:8300",
    [string]$RedirectUri = "http://localhost:3000/callback",
    [string]$PostLogoutRedirectUri = "http://localhost:3000/",
    [string]$ClientName = "AgentForge Local Dev",
    [string]$DockerExe = "C:\Program Files\Docker\Docker\resources\bin\docker.exe",
    [string]$MysqlContainer = "development-easy-mysql-1",
    [string]$Database = "openemr"
)

$ErrorActionPreference = "Stop"

$scope = "openid offline_access api:oemr api:fhir user/Patient.read user/Practitioner.read user/Observation.read user/Condition.read"

$registrationBody = @{
    application_type = "private"
    redirect_uris = @($RedirectUri)
    post_logout_redirect_uris = @($PostLogoutRedirectUri)
    client_name = $ClientName
    token_endpoint_auth_method = "client_secret_post"
    contacts = @("dev@example.com")
    scope = $scope
} | ConvertTo-Json -Compress

$registration = Invoke-RestMethod `
    -Uri "$OpenEmrBaseUrl/oauth2/default/registration" `
    -Method POST `
    -ContentType "application/json" `
    -Body $registrationBody

if (!(Test-Path -LiteralPath $DockerExe)) {
    $DockerExe = "docker"
}

$clientIdSql = $registration.client_id.Replace("'", "''")
$scopeSql = $scope.Replace("'", "''")
$sql = "UPDATE oauth_clients SET is_enabled=1, grant_types='authorization_code password', scope='$scopeSql' WHERE client_id='$clientIdSql';"

& $DockerExe exec $MysqlContainer mariadb -uroot -proot $Database -e $sql

@"
OPENEMR_BASE_URL=$OpenEmrBaseUrl
OPENEMR_SITE=default
OPENEMR_FHIR_BASE_URL=$OpenEmrBaseUrl/apis/default/fhir
OPENEMR_OAUTH_TOKEN_URL=$OpenEmrBaseUrl/oauth2/default/token
OPENEMR_TLS_VERIFY=false
OPENEMR_DEV_PASSWORD_GRANT=true
OPENEMR_CLIENT_ID=$($registration.client_id)
OPENEMR_CLIENT_SECRET=$($registration.client_secret)
OPENEMR_DEV_USERNAME=admin
OPENEMR_DEV_PASSWORD=pass
OPENEMR_DEV_SCOPES=$scope
"@
