[CmdletBinding()]
param(
    [string]$Python = 'D:\python\python.exe',
    [int[]]$Cases = @(48,68,84,85,86,97),
    [int[]]$Questions = @(1,2,3),
    [int[]]$Cores = @(5),
    [double]$Seconds = 120,
    [int]$MaxEvaluations = 28,
    [double]$TotalSeconds = 1800,
    [string]$Workers = 'auto',
    [int]$Shards = 1,
    [int]$ShardIndex = 0,
    [string]$SeedRun = '',
    [string]$Out = '',
    [switch]$AllowAdaptedPython
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) { throw "Python not found: $Python" }
$Version = & $Python -c "import sys; print('.'.join(map(str,sys.version_info[:3])))"
if ($LASTEXITCODE -ne 0) { throw 'Python could not start' }
if (-not $Version.StartsWith('3.12.') -and -not $AllowAdaptedPython) {
    throw "Expected existing Python 3.12.x, got $Version. Adapt independently and pass -AllowAdaptedPython explicitly."
}
if ($Shards -lt 1 -or $ShardIndex -lt 0 -or $ShardIndex -ge $Shards) { throw 'Invalid shard assignment' }
if ($Seconds -le 0 -or $TotalSeconds -le 0 -or $MaxEvaluations -lt 1) { throw 'Budgets must be positive' }
if ($Out -eq '') {
    $Out = Join-Path $PSScriptRoot ("results\adaptive_v4_{0}_shard{1}" -f (Get-Date -Format 'yyyyMMdd_HHmmss'),$ShardIndex)
}
$Root = Split-Path -Parent $PSScriptRoot
$env:PYTHONUTF8 = '1'
$env:OMP_NUM_THREADS = '1'
$env:OPENBLAS_NUM_THREADS = '1'
$Args = @('-m','research_a_orion_track_memory.trusted_run','--root',$Root,'--plugin','research_a_orion_track_memory.plugin_adaptive_v4','--cases') + @($Cases | ForEach-Object { "$_" })
$Args += @('--questions') + @($Questions | ForEach-Object { "$_" })
$Args += @('--cores') + @($Cores | ForEach-Object { "$_" })
$Args += @('--seconds',"$Seconds",'--max-evaluations',"$MaxEvaluations",'--total-seconds',"$TotalSeconds",'--workers',$Workers,'--shards',"$Shards",'--shard-index',"$ShardIndex",'--out',$Out)
if ($SeedRun -ne '') { $Args += @('--seed-run',$SeedRun) }
Push-Location $Root
try {
    Write-Host "memory-v4 CPU-only Python $Version; workers=$Workers; NPU cores=$($Cores -join ','); shard=$ShardIndex/$Shards"
    & $Python @Args
    $Code = $LASTEXITCODE
} finally { Pop-Location }
exit $Code
