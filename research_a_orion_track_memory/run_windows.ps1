[CmdletBinding()]
param(
    [string]$Python = 'D:\python\python.exe',
    [int[]]$Cases = @(5,51,73,90,92,83),
    [int[]]$Questions = @(1,2,3),
    [int[]]$Cores = @(2,5),
    [double]$Seconds = 300,
    [double]$SeedSeconds = 60,
    [int]$SeedEvaluations = 8,
    [int]$MaxEvaluations = 24,
    [double]$TotalSeconds = 3600,
    [double]$PairSeconds = 120,
    [string]$Workers = 'auto',
    [ValidateSet('warm_start','cold_start')][string[]]$Modes = @('warm_start'),
    [int]$Shards = 1,
    [int]$ShardIndex = 0,
    [string]$SeedIndex = '',
    [string]$Official = '',
    [string]$Data = '',
    [string]$Config = '',
    [string]$Out = '',
    [switch]$Resume,
    [switch]$AllowAdaptedPython
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) { throw "Python not found: $Python" }
$Version = & $Python -c "import sys; print('.'.join(map(str,sys.version_info[:3])))"
if ($LASTEXITCODE -ne 0) { throw 'Python could not start' }
if (-not $Version.StartsWith('3.12.') -and -not $AllowAdaptedPython) {
    throw "Expected existing Python 3.12.x, got $Version. Adapt independently and use -AllowAdaptedPython explicitly."
}
if ($Shards -lt 1 -or $ShardIndex -lt 0 -or $ShardIndex -ge $Shards) { throw 'Invalid shard assignment' }
if ($Modes -contains 'warm_start' -and [string]::IsNullOrWhiteSpace($SeedIndex)) {
    throw 'Provide -SeedIndex for day01 warm continuation; do not silently replace formal seeds with fresh construction.'
}
if ($Out -eq '') {
    $Out = Join-Path $PSScriptRoot ("results\priority_{0}_shard{1}" -f (Get-Date -Format 'yyyyMMdd_HHmmss'),$ShardIndex)
}
$Root = Split-Path -Parent $PSScriptRoot
$env:PYTHONUTF8 = '1'
$env:OMP_NUM_THREADS = '1'
$env:OPENBLAS_NUM_THREADS = '1'
$Arguments = @('-m','research_a_orion_track_memory.run','--cases') + @($Cases | ForEach-Object { "$_" })
$Arguments += @('--questions') + @($Questions | ForEach-Object { "$_" })
$Arguments += @('--cores') + @($Cores | ForEach-Object { "$_" })
$Arguments += @('--seconds',"$Seconds",'--seed-seconds',"$SeedSeconds",'--seed-evaluations',"$SeedEvaluations",'--max-evaluations',"$MaxEvaluations",'--total-seconds',"$TotalSeconds",'--pair-seconds',"$PairSeconds",'--workers',$Workers,'--shards',"$Shards",'--shard-index',"$ShardIndex",'--out',$Out,'--modes') + $Modes
if ($SeedIndex -ne '') { $Arguments += @('--seed-index',$SeedIndex) }
if ($Official -ne '') { $Arguments += @('--official',$Official) }
if ($Data -ne '') { $Arguments += @('--data',$Data) }
if ($Config -ne '') { $Arguments += @('--config',$Config) }
if ($Resume) { $Arguments += '--resume' }
Push-Location $Root
try {
    Write-Host "CPU-only Python $Version; workers=$Workers; NPU cores=$($Cores -join ','); cases=$($Cases -join ',')"
    & $Python @Arguments
    $Code = $LASTEXITCODE
} finally { Pop-Location }
exit $Code
