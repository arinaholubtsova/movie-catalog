$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$state = Join-Path $root '.run\processes.json'
if (-not (Test-Path -LiteralPath $state)) { Write-Output 'No local process state found.'; exit 0 }
$pids = Get-Content -LiteralPath $state -Raw | ConvertFrom-Json
foreach ($id in @($pids.backend_pid, $pids.frontend_pid)) {
    if ($id) { Stop-Process -Id $id -ErrorAction SilentlyContinue }
}
Remove-Item -LiteralPath $state
Write-Output 'Local Movie Catalog processes stopped.'
