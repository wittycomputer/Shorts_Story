param([string]$StudioExe, [string]$AliasPath)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$openPath = $projectRoot
if ($projectRoot -match '[^\x00-\x7F]') {
    if (-not $AliasPath) { $AliasPath = Join-Path $env:USERPROFILE 'shortory_flutter' }
    $AliasPath = [IO.Path]::GetFullPath($AliasPath)
    if ($AliasPath -match '[^\x00-\x7F]') { throw 'Choose an ASCII alias path, for example -AliasPath C:\src\shortory.' }
    if (-not (Test-Path -LiteralPath $AliasPath)) {
        New-Item -ItemType Junction -Path $AliasPath -Target $projectRoot | Out-Null
    }
    $aliasInfo = Get-Item -LiteralPath $AliasPath
    if ($aliasInfo.LinkType -ne 'Junction' -or $aliasInfo.Target -notcontains $projectRoot) {
        throw 'The alias belongs to another project. Use -AliasPath with an unused ASCII path.'
    }
    $openPath = $AliasPath
}
if (-not $StudioExe) { $StudioExe = $env:STUDIO_EXE }
if (-not $StudioExe) { $StudioExe = Join-Path $env:ProgramFiles 'Android/Android Studio/bin/studio64.exe' }
if (-not (Test-Path -LiteralPath $StudioExe)) { throw 'Android Studio not found. Pass -StudioExe with the path to studio64.exe.' }
Start-Process -FilePath $StudioExe -ArgumentList ('"' + $openPath + '"') -WindowStyle Hidden
