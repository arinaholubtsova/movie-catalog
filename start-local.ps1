$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'
$python = Join-Path $root '.venv\Scripts\python.exe'
$node = 'C:\Users\Аріна\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
$vite = Join-Path $frontend 'node_modules\vite\bin\vite.js'
$runtime = Join-Path $root '.run'
$state = Join-Path $runtime 'processes.json'

function Test-PortAvailable([int]$port) {
    foreach ($address in @([System.Net.IPAddress]::Loopback, [System.Net.IPAddress]::IPv6Loopback)) {
        $listener = [System.Net.Sockets.TcpListener]::new($address, $port)
        try { $listener.Start() }
        catch [System.Net.Sockets.SocketException] { return $false }
        finally { $listener.Stop() }
    }
    return $true
}

if (Test-Path -LiteralPath $state) {
    $saved = Get-Content -LiteralPath $state -Raw | ConvertFrom-Json
    $apiRunning = Get-Process -Id $saved.backend_pid -ErrorAction SilentlyContinue
    $webRunning = Get-Process -Id $saved.frontend_pid -ErrorAction SilentlyContinue
    if ($apiRunning -and $webRunning) {
        Write-Output "Movie Catalog is already running at http://localhost:$($saved.frontend_port)"
        exit 0
    }
}

if (-not (Test-Path -LiteralPath $python)) { throw 'Python venv is missing. Install backend/requirements.txt first.' }
if (-not (Test-Path -LiteralPath $vite)) { throw 'Frontend dependencies are missing. Run pnpm install in frontend.' }
if (-not (Test-Path -LiteralPath $node)) { throw 'Bundled Node.js was not found.' }
if (-not (Test-Path -LiteralPath (Join-Path $root '.env'))) { throw '.env is missing.' }

Get-Content -LiteralPath (Join-Path $root '.env') | ForEach-Object {
    if ($_ -and -not $_.StartsWith('#')) {
        $parts = $_.Split('=', 2)
        if ($parts.Count -eq 2) { [Environment]::SetEnvironmentVariable($parts[0], $parts[1], 'Process') }
    }
}
$webPort = 5173
while (-not (Test-PortAvailable $webPort)) { $webPort++ }
$env:DATABASE_URL = 'sqlite:///./movie_catalog.db'
$env:CORS_ORIGINS = "http://localhost:$webPort,http://127.0.0.1:$webPort"
if (-not $env:METADATA_URL) { $env:METADATA_URL = "http://127.0.0.1:$webPort/metadata.json" }

New-Item -ItemType Directory -Path $runtime -Force | Out-Null
Push-Location $backend
try {
    & $python -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw 'Database migration failed.' }
    & $python seed.py
    if ($LASTEXITCODE -ne 0) { throw 'Database seed failed.' }
} finally { Pop-Location }

$api = Start-Process -FilePath $python -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000') -WorkingDirectory $backend -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtime 'backend.out.log') -RedirectStandardError (Join-Path $runtime 'backend.err.log') -PassThru
$web = Start-Process -FilePath $node -ArgumentList @($vite, '--host', '127.0.0.1', '--port', $webPort, '--strictPort') -WorkingDirectory $frontend -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtime 'frontend.out.log') -RedirectStandardError (Join-Path $runtime 'frontend.err.log') -PassThru
@{ backend_pid = $api.Id; frontend_pid = $web.Id; frontend_port = $webPort } | ConvertTo-Json | Set-Content -LiteralPath $state -Encoding utf8
Write-Output "Frontend: http://localhost:$webPort"
Write-Output 'API: http://localhost:8000/docs'
