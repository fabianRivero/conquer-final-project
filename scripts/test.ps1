# Run the `fiado-confirmado` test suites.
#
#   .\scripts\test.ps1              -> unit + integration
#   .\scripts\test.ps1 -Unit        -> unit only (no database needed)
#   .\scripts\test.ps1 -Integration -> integration only
#
# The integration suite needs PostgreSQL 16 on 127.0.0.1:5433.
# If it is not running, start it with:
#   cmd /c start /B "$env:LOCALAPPDATA\pg16-portable\start-pg.bat"

param(
    [switch]$Unit,
    [switch]$Integration,
    [switch]$SkipIntegration
)

$ErrorActionPreference = 'Continue'

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python   = "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe"
if (-not (Test-Path $Python)) {
    Write-Error "Python not found at $Python. Run scripts\setup-toolchain.ps1 first."
    exit 1
}

$runUnit = $Unit -or (-not $Unit -and -not $Integration)
$runIntegration = $Integration -or (-not $Unit -and -not $Integration -and -not $SkipIntegration)

$failed = $false

if ($runUnit) {
    Write-Host "`n=== UNIT ===" -ForegroundColor Cyan
    # A clean environment: the unit suite must not depend on inherited variables.
    Remove-Item Env:SECRET_KEY, Env:DEBUG, Env:DATABASE_URL, Env:ALLOWED_HOSTS,
                Env:DATABASE_SSLMODE, Env:SECURE_SSL_REDIRECT -ErrorAction SilentlyContinue
    & $Python -m pytest "$RepoRoot\backend\tests\unit" -q
    if ($LASTEXITCODE -ne 0) { $failed = $true }
}

if ($runIntegration) {
    Write-Host "`n=== INTEGRATION ===" -ForegroundColor Cyan
    $env:DATABASE_URL        = "postgres://fiado:fiado@127.0.0.1:5433/fiado_test"
    $env:DATABASE_SSLMODE    = "disable"
    $env:SECRET_KEY          = "local-dev-secret"
    $env:DEBUG               = "False"
    $env:ALLOWED_HOSTS       = "localhost,127.0.0.1"
    $env:SECURE_SSL_REDIRECT = "0"
    & $Python -m pytest "$RepoRoot\backend\tests\integration" -q
    if ($LASTEXITCODE -ne 0) { $failed = $true }
}

if ($failed) { Write-Host "`nFAILURES" -ForegroundColor Red; exit 1 }
Write-Host "`nAll green." -ForegroundColor Green
