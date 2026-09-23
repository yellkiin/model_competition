[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet("all", "dev", "main", "cross", "granularity")]
    [string]$Stage = "all",
    [ValidateRange(1, 64)]
    [int]$Workers = 2,
    [string]$OutRoot = "research_a\runs",
    [string]$MainVariant = "full",
    [string]$PythonExe = "D:\python\python.exe",
    [string]$Archive = ""
)
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) {
    throw "Python not found: $PythonExe. Pass -PythonExe with the correct executable."
}
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUNBUFFERED = "1"
$Arguments = @("-X", "utf8", "-u", "-m", "research_a.launch", $Stage,
               "--workers", "$Workers", "--out-root", $OutRoot, "--main-variant", $MainVariant)
if ($Archive) { $Arguments += @("--archive", $Archive) }
& $PythonExe @Arguments
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
