param(
    [string]$Python = 'D:\python\python.exe',
    [string]$Out = 'research_a_next\environment.local.json',
    [switch]$AllowCompatible
)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    Write-Host "Python not found: $Python"
    Write-Host 'Local agent: locate an installed CPython 3.12.5 x64 and rerun with -Python; do not alter existing environments or install CUDA.'
    exit 3
}
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$arguments = @('-X','utf8','-m','research_a_next.environment','--out',$Out)
if ($AllowCompatible) { $arguments += '--allow-compatible' }
& $Python @arguments
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Read research_a_next/LOCAL_AGENT.md. A compatible installed interpreter may be selected explicitly; no automatic system installation was attempted.'
    exit $LASTEXITCODE
}
Write-Host 'Environment ready. No venv/Conda, CUDA, PyTorch or third-party packages required.'
