[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet("dev", "main", "cross", "granularity")]
    [string]$Stage = "dev",

    [ValidateRange(1, 64)]
    [int]$Workers = 2,

    [string]$OutRoot = "research_a\runs",

    [ValidateSet("full", "common", "no_memory", "no_cache", "coarse", "fine", "locality", "spill", "cache", "critical", "explore", "portfolio", "unranked")]
    [string]$MainVariant = "full",

    [string]$PythonExe = "D:\python\python.exe"
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

if (-not (Test-Path $PythonExe)) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $pythonCommand) {
        throw "Python not found. Expected D:\python\python.exe or a python.exe on PATH."
    }
    $PythonExe = $pythonCommand.Source
}

& $PythonExe -c "import sys; assert sys.version_info >= (3, 10); print(sys.executable); print(sys.version)"
if ($LASTEXITCODE -ne 0) { throw "Python >= 3.10 is required." }

function Invoke-Python {
    param([string[]]$ArgsList)
    & $PythonExe @ArgsList
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed: $PythonExe $($ArgsList -join ' ')"
    }
}

New-Item -ItemType Directory -Force -Path $OutRoot | Out-Null
$Cases = Join-Path $OutRoot "cases.json"

if (-not (Test-Path $Cases)) {
    Invoke-Python @("-m", "research_a.run", "prepare", "--out", $Cases)
}

switch ($Stage) {
    "dev" {
        Invoke-Python @(
            "-m", "research_a.run", "run",
            "--manifest", $Cases,
            "--split", "dev",
            "--questions", "1", "2", "3",
            "--cores", "2", "4",
            "--variants", "common", "full", "no_memory", "no_cache",
            "--seeds", "0", "1", "2",
            "--budget", "24",
            "--workers", "$Workers",
            "--out", (Join-Path $OutRoot "dev"),
            "--resume"
        )
        Invoke-Python @(
            "-m", "research_a.report", "analyze",
            "--source", (Join-Path $OutRoot "dev"),
            "--out", (Join-Path $OutRoot "dev_report")
        )
    }

    "main" {
        Invoke-Python @(
            "-m", "research_a.run", "run",
            "--manifest", $Cases,
            "--questions", "1", "2", "3",
            "--cores", "1", "2", "3", "4", "5",
            "--variants", "rr", $MainVariant,
            "--seeds", "0",
            "--budget", "32",
            "--workers", "$Workers",
            "--out", (Join-Path $OutRoot "main"),
            "--resume"
        )
        Invoke-Python @(
            "-m", "research_a.report", "analyze",
            "--source", (Join-Path $OutRoot "main"),
            "--out", (Join-Path $OutRoot "main_report")
        )
    }

    "cross" {
        Invoke-Python @(
            "-m", "research_a.run", "cross",
            "--source", (Join-Path $OutRoot "main"),
            "--variant", $MainVariant,
            "--cores", "1", "2", "3", "4", "5",
            "--seeds", "0",
            "--out", (Join-Path $OutRoot "cross"),
            "--resume"
        )
        Invoke-Python @(
            "-m", "research_a.report", "cross",
            "--source", (Join-Path $OutRoot "cross"),
            "--out", (Join-Path $OutRoot "cross_report")
        )
    }

    "granularity" {
        Invoke-Python @(
            "-m", "research_a.run", "granularity",
            "--manifest", $Cases,
            "--split", "dev",
            "--questions", "1", "2", "3",
            "--cores", "2", "4", "5",
            "--out", (Join-Path $OutRoot "granularity")
        )
    }
}
