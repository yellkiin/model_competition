[CmdletBinding()]
param([string]$Python='D:\python\python.exe')
$ErrorActionPreference='Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding
$OutputEncoding = [Console]::OutputEncoding
if (!(Test-Path -LiteralPath $Python)) { throw "Python not found: $Python. Local agent: configure an isolated 64-bit CPython 3.12.x, do not replace an active environment." }
$Repo=Split-Path -Parent $PSScriptRoot
Push-Location $Repo
try {
    $raw=& $Python -m research_a_orion_anytime.run probe
    if ($LASTEXITCODE -ne 0) { throw 'Environment probe failed' }
    $probe=($raw -join "`n") | ConvertFrom-Json
    $probe | Format-List
    if (!$probe.reference_compatible) { throw 'Expected 64-bit CPython 3.12.x. Configure another interpreter and pass -Python. Do not install CUDA, torch, WSL or Conda for this program.' }
    if ($null -ne $probe.available_memory_gib -and $probe.available_memory_gib -lt 4) { throw 'Less than 4 GiB available. Free memory or use another machine; this is a conservative admission policy, not a formal memory guarantee.' }
    Write-Host 'Standard library only; no pip installation needed.'
    Write-Host "Recommended worker processes: $($probe.recommended_workers)"
} finally { Pop-Location }
