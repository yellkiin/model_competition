[CmdletBinding()]
param(
    [string]$PythonExe = "D:\python\python.exe",
    [switch]$SkipPull
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

& $PythonExe -c "import sys; print('python:', sys.executable); print('version:', sys.version); assert sys.version_info >= (3, 10)"
if ($LASTEXITCODE -ne 0) {
    throw "Python >= 3.10 is required."
}

$condaCommand = Get-Command conda -ErrorAction SilentlyContinue
if ($null -ne $condaCommand) {
    & conda --version
    Write-Host "Conda detected, but research_a does not require activating a Conda environment."
}

& git --version
if ($LASTEXITCODE -ne 0) { throw "Git is required." }
& git lfs version
if ($LASTEXITCODE -ne 0) { throw "Git LFS is required. Install/update Git for Windows with Git LFS support." }

if (-not $SkipPull) {
    Write-Host "Updating main and downloading all Git LFS objects..."
    & git switch main
    if ($LASTEXITCODE -ne 0) { throw "git switch main failed." }
    & git pull --ff-only origin main
    if ($LASTEXITCODE -ne 0) { throw "git pull failed." }
    & git lfs install --local
    if ($LASTEXITCODE -ne 0) { throw "git lfs install failed." }
    & git lfs pull
    if ($LASTEXITCODE -ne 0) { throw "git lfs pull failed." }
}

Write-Host ""
Write-Host "Windows environment is ready."
Write-Host "Python used by the A experiments: $PythonExe"
Write-Host "CUDA/GPU is not used; RTX 3060 does not need any extra setup."
Write-Host ""
Write-Host "Next commands:"
Write-Host "  powershell -NoProfile -ExecutionPolicy Bypass -File .\research_a\experiments.ps1 dev"
Write-Host "  powershell -NoProfile -ExecutionPolicy Bypass -File .\research_a\experiments.ps1 main"
