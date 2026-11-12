param([int]$DurationSeconds = 1800, [string]$ReportPath = 'reports\loadtest-30min.json')
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$backend = Join-Path $root 'backend'
$python = Join-Path $root '.venv\Scripts\python.exe'
$alembic = Join-Path $root '.venv\Scripts\alembic.exe'
$tokens = Join-Path $root '.run\loadtest_tokens.json'
$report = Join-Path $root $ReportPath
$env:DATABASE_URL = 'sqlite:///../.run/loadtest.db'
if (Get-NetTCPConnection -LocalPort 8001 -State Listen -ErrorAction SilentlyContinue) { throw 'Port 8001 is already in use.' }
New-Item -ItemType Directory -Path (Join-Path $root '.run') -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $root 'reports') -Force | Out-Null
Push-Location $backend
try {
    & $alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw 'Migration failed' }
    & $python loadtest_seed.py
    if ($LASTEXITCODE -ne 0) { throw 'Load test dataset creation failed' }
    $launcher = Start-Process -FilePath $python -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8001') -WorkingDirectory $backend -WindowStyle Hidden -RedirectStandardOutput (Join-Path $root '.run\loadtest-server.out.log') -RedirectStandardError (Join-Path $root '.run\loadtest-server.err.log') -PassThru
    $actualPid = $launcher.Id
    $apiReady = $false
    for ($attempt = 0; $attempt -lt 120; $attempt++) {
        Start-Sleep -Seconds 1
        try {
            $health = Invoke-WebRequest -Uri 'http://127.0.0.1:8001/health' -UseBasicParsing -TimeoutSec 2
            if ($health.StatusCode -eq 200) { $apiReady = $true; break }
        } catch {
            # The API is still starting; keep waiting for the isolated 20k dataset.
        }
    }
    if (-not $apiReady) { throw 'Load test API did not become healthy on port 8001 within 120 seconds' }
    $server = Get-Process -Id $actualPid
    $server.ProcessorAffinity = 3
    & $python performance_check.py --base-url http://127.0.0.1:8001 --tokens-file $tokens --duration $DurationSeconds --report $report
    if ($LASTEXITCODE -ne 0) { throw 'Load test client failed' }
    Write-Output "Report: $report"
} finally {
    if ($actualPid) { Stop-Process -Id $actualPid -ErrorAction SilentlyContinue }
    if ($launcher) { Stop-Process -Id $launcher.Id -ErrorAction SilentlyContinue }
    Pop-Location
}
