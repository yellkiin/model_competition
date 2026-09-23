[CmdletBinding()]
param(
    [string]$PythonExe = "D:\python\python.exe",
    [string]$Archive = "",
    [switch]$SkipPull
)
# Compatibility entry point. Never pull the whole repository's LFS datasets.
# Updating Git is separate. This command only obtains missing A inputs.
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) {
    throw "Python not found: $PythonExe. Pass -PythonExe with the correct executable."
}
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$Arguments = @("-X", "utf8", "-u", "-m", "research_a.launch", "prepare")
if ($Archive) { $Arguments += @("--archive", $Archive) }
& $PythonExe @Arguments
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "A inputs ready. Run: powershell -NoProfile -ExecutionPolicy Bypass -File .\research_a\experiments.ps1 all"
