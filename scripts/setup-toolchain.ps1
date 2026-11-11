# Rebuild the local development toolchain for `fiado-confirmado`.

# Run this in PowerShell AFTER a machine format. It restores:
#   - Python 3.14 + the pinned dependencies in requirements.txt
#   - PostgreSQL 16 (portable build, no admin rights needed)
#   - the `fiado_test` database
#   - a detached PostgreSQL server on 127.0.0.1:5433
#
# Everything it creates lives OUTSIDE the repository, so `git status`
# stays clean and a format cannot take the toolchain with it.

$ErrorActionPreference = 'Stop'

$RepoRoot   = Split-Path -Parent $PSScriptRoot
$PythonDir  = "$env:LOCALAPPDATA\Programs\Python\Python314"
$PgRoot     = "$env:LOCALAPPDATA\Programs\pg16-portable\pgsql"
$PgData     = "$env:LOCALAPPDATA\pgdata-fiado"
$PgLogDir   = "$env:LOCALAPPDATA\pglogs"
$PgLog      = "$PgLogDir\pg.log"
$StartBat   = "$env:LOCALAPPDATA\pg16-portable\start-pg.bat"
$PgPort     = 5433
$TempDir    = $env:TEMP

Write-Host "`n== 1/5  Python 3.14 ==" -ForegroundColor Cyan
if (-not (Test-Path "$PythonDir\python.exe")) {
    Write-Host "Installing Python 3.14 via winget..."
    winget install --id Python.Python.3.14 --exact --silent `
        --accept-package-agreements --accept-source-agreements --disable-interactivity
    if ($LASTEXITCODE -ne 0) { throw "Python install failed (winget exit $LASTEXITCODE)" }
} else {
    Write-Host "Already installed."
}

# Use the resolved install directly: this shell may carry a stale PATH.
$Py     = "$PythonDir\python.exe"
$PyPip  = "$PythonDir\Scripts\pip.exe"

Write-Host "`n== 2/5  Python dependencies ==" -ForegroundColor Cyan
& $Py -m pip install --disable-pip-version-check -r "$RepoRoot\requirements.txt"
if ($LASTEXITCODE -ne 0) { throw "pip install failed (exit $LASTEXITCODE)" }

Write-Host "`n== 3/5  PostgreSQL 16 (portable) ==" -ForegroundColor Cyan
if (-not (Test-Path "$PgRoot\bin\pg_ctl.exe")) {
    $zip = "$TempDir\pg16bin.zip"
    if (-not (Test-Path $zip)) {
        $url = "https://get.enterprisedb.com/postgresql/postgresql-16.15-5-windows-x64-binaries.zip"
        Write-Host "Downloading portable binaries (about 373 MB)..."
        $ProgressPreference = 'SilentlyContinue'
        Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing -TimeoutSec 900
    }
    $extract = "$env:LOCALAPPDATA\Programs\pg16-portable"
    if (Test-Path $extract) { Remove-Item $extract -Recurse -Force }
    New-Item -ItemType Directory -Path $extract -Force | Out-Null
    Expand-Archive -Path $zip -DestinationPath $extract -Force
    Remove-Item $zip -Force
} else {
    Write-Host "Already extracted."
}

if (-not (Test-Path "$PgData\PG_VERSION")) {
    Write-Host "Initialising the cluster..."
    & "$PgRoot\bin\initdb.exe" -D $PgData -U fiado -A trust --encoding=UTF8 --locale=C
    if ($LASTEXITCODE -ne 0) { throw "initdb failed (exit $LASTEXITCODE)" }

    # `ssl = off` matters: the production settings pin sslmode=require for Neon,
    # but the local server serves no TLS. The suite opts out with
    # DATABASE_SSLMODE=disable instead.
    # Port 5433, not 5432: Docker and WSL commonly publish a PostgreSQL on
    # 5432, and a bind conflict there silently hands the suite a foreign
    # server that refuses the local credentials.
    Add-Content "$PgData\postgresql.conf" "`n# fiado-confirmado local dev`nlisten_addresses = '127.0.0.1'`nssl = off`nport = $PgPort`n"
} else {
    Write-Host "Cluster already initialised."
}

# The server MUST be launched detached, and its log MUST live outside the data
# directory. Four host-specific facts, each proven the hard way:
#   - a child of the shell command's process group is killed when the command
#     is torn down, so `pg_ctl start` in the foreground does not survive;
#   - `cmd /c start /B` does not survive it either: the child still belongs to
#     the same job object and is torn down with it;
#   - a process created through WMI survives the job object but still has a
#     console, so a Ctrl+C sent to the session reaches it and the server logs
#     "^C" and shuts down cleanly;
#   - a log inside PGDATA is re-opened by the postmaster and deadlocks on a
#     sharing violation.
# The launch that works: start pg_ctl with CREATE_NO_WINDOW, so the child
# has no console at all and no control event can reach it.
New-Item -ItemType Directory -Path $PgLogDir -Force | Out-Null
@"
@echo off
set PGROOT=$PgRoot
set PGDATA=$PgData
set PGLOG=$PgLog
"%PGROOT%\bin\pg_ctl.exe" -D "%PGDATA%" -l "%PGLOG%" -w start
"@ | Set-Content -Path $StartBat -Encoding ASCII

Write-Host "`n== 4/5  Starting the server ==" -ForegroundColor Cyan
& "$PgRoot\bin\pg_ctl.exe" -D $PgData status 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = "$PgRoot\bin\pg_ctl.exe"
    $psi.Arguments = "-D `"$PgData`" -l `"$PgLog`" -w start"
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $proceso = [System.Diagnostics.Process]::Start($psi)
    $proceso.WaitForExit(60000) | Out-Null
    Start-Sleep -Seconds 5
}

$ready = $false
for ($i = 0; $i -lt 10; $i++) {
    & "$PgRoot\bin\pg_isready.exe" -h 127.0.0.1 -p $PgPort -t 5 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { $ready = $true; break }
    Start-Sleep -Seconds 3
}
if (-not $ready) {
    Write-Host "Server did not become ready. Log:" -ForegroundColor Red
    if (Test-Path $PgLog) { Get-Content $PgLog -Tail 30 }
    throw "PostgreSQL failed to start"
}
Write-Host "PostgreSQL is accepting connections on 127.0.0.1:$PgPort"

Write-Host "`n== 5/5  Test database ==" -ForegroundColor Cyan
$env:PGPASSWORD = "fiado"
# `createdb` fails loudly when the database already exists, and with
# $ErrorActionPreference = Stop that failure would abort a rebuild that is
# actually fine. So the existence is checked first and `createdb` only runs
# when the database is genuinely missing.
$ErrorActionPreference = 'Continue'
$exists = & "$PgRoot\bin\psql.exe" -h 127.0.0.1 -p $PgPort -U fiado -d postgres -w -t `
    -c "SELECT 1 FROM pg_database WHERE datname = 'fiado_test';" 2>&1 | Out-String
$ErrorActionPreference = 'Stop'
if ($exists.Trim() -eq "1") {
    Write-Host "fiado_test already exists - reusing it."
} else {
    & "$PgRoot\bin\createdb.exe" -h 127.0.0.1 -p $PgPort -U fiado fiado_test
    if ($LASTEXITCODE -ne 0) { throw "Could not create the fiado_test database" }
}
& "$PgRoot\bin\psql.exe" -h 127.0.0.1 -p $PgPort -U fiado -d fiado_test -w -t -c "SELECT 1;" 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { throw "The fiado_test database is not reachable" }
Write-Host "fiado_test is ready"

Write-Host "`n== Verify ==" -ForegroundColor Cyan
& $Py -m pytest "$RepoRoot\backend\tests\unit" -q
$env:DATABASE_URL        = "postgres://fiado:fiado@127.0.0.1:$PgPort/fiado_test"
$env:DATABASE_SSLMODE    = "disable"
$env:SECRET_KEY          = "local-dev-secret"
$env:DEBUG               = "False"
$env:ALLOWED_HOSTS       = "localhost,127.0.0.1"
$env:SECURE_SSL_REDIRECT = "0"
& $Py -m pytest "$RepoRoot\backend\tests\integration" -q
Write-Host "`nToolchain ready." -ForegroundColor Green
Write-Host "The integration suite needs these variables:"
Write-Host "  `$env:DATABASE_URL=`"postgres://fiado:fiado@127.0.0.1:$PgPort/fiado_test`""
Write-Host '  $env:DATABASE_SSLMODE="disable"'
Write-Host '  $env:SECRET_KEY="local-dev-secret"'
Write-Host '  $env:DEBUG="False"'
Write-Host '  $env:ALLOWED_HOSTS="localhost,127.0.0.1"'
Write-Host '  $env:SECURE_SSL_REDIRECT="0"'
