$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $projectRoot 'backend'
$pythonExe = Join-Path $backendDir '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Run scripts/setup.ps1 first.' }
$existing = $null
try {
    $existing = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/health' -TimeoutSec 2
} catch { }
if ($null -ne $existing) {
    if ($existing.api_version -eq 2 -and $existing.privacy -eq 'local-ai-firebase-records') {
        $localConfigPath = Join-Path $backendDir 'firebase.local.json'
        if (-not (Test-Path -LiteralPath $localConfigPath)) { throw 'Configure this checkout with setup_firebase.bat first.' }
        $localConfig = Get-Content -LiteralPath $localConfigPath -Raw | ConvertFrom-Json
        $expectedProject = $localConfig.project_id
        if ($env:SHORTORY_FIREBASE_PROJECT) { $expectedProject = $env:SHORTORY_FIREBASE_PROJECT }
        if ($existing.firebase.project_id -ne $expectedProject) { throw 'Another Firebase project is using port 8765. Stop that server before starting this checkout.' }
        Write-Host 'Shortory server is already running: http://127.0.0.1:8765'
        exit 0
    }
    throw 'Port 8765 is in use by another service.'
}
$env:PYTHONUTF8 = '1'
& $pythonExe -X utf8 (Join-Path $backendDir 'check_environment.py')
if ($LASTEXITCODE -ne 0) { throw 'Setup is incomplete. Follow the checks above before starting the server.' }
$dataDir = Join-Path $backendDir 'data'
New-Item -ItemType Directory -Path $dataDir -Force | Out-Null
$env:PYTHONUTF8 = '1'
$serverProcess = Start-Process -FilePath $pythonExe -ArgumentList '-X','utf8','-m','uvicorn','server:app','--host','127.0.0.1','--port','8765' -WorkingDirectory $backendDir -WindowStyle Hidden -RedirectStandardOutput (Join-Path $dataDir 'server.log') -RedirectStandardError (Join-Path $dataDir 'server-error.log') -PassThru
$serverProcess.Id | Set-Content -LiteralPath (Join-Path $dataDir 'server.pid')
for ($attempt = 0; $attempt -lt 120; $attempt++) {
    Start-Sleep -Milliseconds 500
    try {
        $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/health' -TimeoutSec 2
        if ($health.api_version -eq 2) { Write-Host 'Shortory server ready. Open the Flutter app in Android Studio.'; exit 0 }
    } catch { }
    if ($serverProcess.HasExited) { break }
}
throw ('Server did not start. Check ' + (Join-Path $dataDir 'server-error.log'))
