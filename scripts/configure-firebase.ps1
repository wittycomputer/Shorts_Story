param(
    [string]$GoogleServices,
    [string]$ServiceAccount,
    [switch]$Overwrite
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $projectRoot 'backend/.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Run setup.bat first.' }
if (-not $GoogleServices) { $GoogleServices = Read-Host 'Path to your downloaded google-services.json' }
if (-not $ServiceAccount) { $ServiceAccount = Read-Host 'Path to your downloaded Firebase service-account JSON' }
$GoogleServices = $GoogleServices.Trim().Trim('"')
$ServiceAccount = $ServiceAccount.Trim().Trim('"')
$configureArgs = @('-X', 'utf8', (Join-Path $PSScriptRoot 'configure_firebase.py'), '--google-services', $GoogleServices, '--service-account', $ServiceAccount)
if ($Overwrite) { $configureArgs += '--overwrite' }
& $pythonExe @configureArgs
if ($LASTEXITCODE -ne 0) { throw 'Firebase setup failed. Existing settings were not replaced unless --overwrite was selected.' }
Write-Host 'Next: enable Email/Password Auth, create Firestore, and deploy firestore.rules as described in docs/INSTALL_WINDOWS.md.'
