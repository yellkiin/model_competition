param(
    [string]$Python = 'D:\python\python.exe',
    [string]$Official = '',
    [string]$SeedIndex = '',
    [string[]]$Cases = @('024','083','086','001','059','044','084'),
    [ValidateSet('warm','cold')][string]$Mode = 'warm',
    [double]$Seconds = 300,
    [double]$WallSeconds = 7200,
    [string]$Workers = 'auto',
    [int]$MaxWorkers = 1,
    [int]$Shards = 1,
    [int]$ShardIndex = 0,
    [string]$RunId = (Get-Date -Format 'yyyyMMdd_HHmmss')
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python not found at $Python. Let the local Agent select an existing CPU-only Python 3.12; do not disturb another environment."
}
$version = & $Python -c 'import sys; print("%d.%d" % sys.version_info[:2])'
if ($version.Trim() -ne '3.12') {
    throw "This machine is $version, not the requested Python 3.12.x. Local Agent must adapt -Python and document it before comparative runs."
}
$env:PYTHONUTF8 = '1'
$env:OMP_NUM_THREADS = '1'
$env:OPENBLAS_NUM_THREADS = '1'
$env:MKL_NUM_THREADS = '1'
$repo = Split-Path $PSScriptRoot -Parent
Push-Location $repo
try {
    $arguments = @('-m','research_a_orion_track_anytime.runner','--cases') + $Cases + @(
        '--questions','1','2','3','--cores','2','5',
        '--methods','old','budget','combined','--modes',$Mode,
        '--seconds',"$Seconds",'--wall-seconds',"$WallSeconds",'--workers',$Workers,
        '--max-workers',"$MaxWorkers",'--shards',"$Shards",'--shard-index',"$ShardIndex",'--run-id',$RunId)
    if ($Official) { $arguments += @('--official',$Official) }
    if ($SeedIndex) { $arguments += @('--seed-index',$SeedIndex) }
    & $Python @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Run exited $LASTEXITCODE. Keep blocked/error/partial records; do not mark the small-batch gate passed."
    }
} finally { Pop-Location }
