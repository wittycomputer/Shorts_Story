param([switch]$SkipModelDownload)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $projectRoot 'backend'
$pythonExe = Join-Path $backendDir '.venv/Scripts/python.exe'
$env:PYTHONUTF8 = '1'
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { throw 'Install uv from https://docs.astral.sh/uv/ and run this script again.' }
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) { throw 'Install FFmpeg with libass support, then add it to PATH.' }
if (-not (Get-Command ffprobe -ErrorAction SilentlyContinue)) { throw 'Add ffprobe from the FFmpeg bin folder to PATH.' }
if (-not (Get-Command flutter -ErrorAction SilentlyContinue)) { throw 'Install Flutter SDK, add its bin folder to PATH, then restart the terminal.' }
if ($projectRoot -match '[^\x00-\x7F]') {
    Write-Warning 'The checkout path contains non-ASCII characters. Use open_android_studio.bat for an ASCII junction, or clone into C:\src\shortory.'
}
$appConfig = Join-Path $projectRoot 'config/firebase.json'
if (-not (Test-Path -LiteralPath $appConfig)) {
    Copy-Item -LiteralPath (Join-Path $projectRoot 'config/firebase.example.json') -Destination $appConfig
}
if (-not (Test-Path -LiteralPath $pythonExe)) {
    uv venv --python 3.11 (Join-Path $backendDir '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Python environment setup failed.' }
}
# Copy mode also works with Windows cloud-backed folders that reject hardlinks.
uv pip install --link-mode copy --python $pythonExe 'torch==2.7.1' --index-url 'https://download.pytorch.org/whl/cu128'
if ($LASTEXITCODE -ne 0) { throw 'PyTorch installation failed.' }
uv pip install --link-mode copy --python $pythonExe -r (Join-Path $backendDir 'requirements.lock.txt')
if ($LASTEXITCODE -ne 0) { throw 'AI dependencies installation failed.' }
if (-not $SkipModelDownload) {
    & $pythonExe -X utf8 (Join-Path $backendDir 'check_environment.py') --skip-models --skip-firebase
    if ($LASTEXITCODE -ne 0) { throw 'Fix the environment checks before downloading model weights.' }
    & $pythonExe -X utf8 (Join-Path $backendDir 'download_models.py')
    if ($LASTEXITCODE -ne 0) { throw 'Model download failed. Run the script again to resume.' }
}
Push-Location $projectRoot
try { flutter pub get; if ($LASTEXITCODE -ne 0) { throw 'Flutter dependencies failed.' } } finally { Pop-Location }
Write-Host 'Dependencies ready. Run setup_firebase.bat, then check_setup.bat before starting the server.'
