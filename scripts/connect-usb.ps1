param([string]$DeviceSerial, [string]$AdbExe)
$ErrorActionPreference = 'Stop'
if (-not $AdbExe) {
    $adbCommand = Get-Command adb -ErrorAction SilentlyContinue
    if ($adbCommand) { $AdbExe = $adbCommand.Source }
}
if (-not $AdbExe) {
    $sdkDir = $env:ANDROID_SDK_ROOT
    if (-not $sdkDir) { $sdkDir = $env:ANDROID_HOME }
    if (-not $sdkDir) { $sdkDir = Join-Path $env:LOCALAPPDATA 'Android/Sdk' }
    $AdbExe = Join-Path $sdkDir 'platform-tools/adb.exe'
}
if (-not (Test-Path -LiteralPath $AdbExe)) { throw 'Install Android SDK platform-tools, or pass -AdbExe with the path to adb.exe.' }
& $AdbExe devices
$deviceArgs = @()
if ($DeviceSerial) { $deviceArgs = @('-s', $DeviceSerial) }
& $AdbExe @deviceArgs reverse tcp:8765 tcp:8765
if ($LASTEXITCODE -ne 0) { throw 'Connect a device with USB debugging enabled. With multiple devices, pass -DeviceSerial.' }
Write-Host 'In the app, select USB and save http://127.0.0.1:8765'
