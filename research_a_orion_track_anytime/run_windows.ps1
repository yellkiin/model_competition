# Alias required by COMMON.md; all arguments pass unchanged to the small-batch script.
& (Join-Path $PSScriptRoot 'run_small.ps1') @args
exit $LASTEXITCODE
