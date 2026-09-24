param([string]$Python = 'D:\python\python.exe')
$ErrorActionPreference = 'Stop'
Set-Location (Resolve-Path (Join-Path $PSScriptRoot '..\..\..'))
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
& $Python -X utf8 -u -m research_a_aster_rbc.v3.run @args
if ($LASTEXITCODE -ne 0) { throw "ASTER V3 exited with code $LASTEXITCODE. Preserve existing output and read its logs." }
