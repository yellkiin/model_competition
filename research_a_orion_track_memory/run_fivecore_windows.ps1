param(
    [string]$Python = 'D:\python\python.exe',
    [int[]]$Cases = @(5,51,59,67,73,83,90,92),
    [int[]]$Questions = @(1,2,3),
    [int[]]$Cores = @(5),
    [double]$Seconds = 120,
    [int]$MaxEvaluations = 24,
    [double]$TotalSeconds = 1500,
    [string]$Workers = 'auto',
    [ValidateSet('epochs','local')][string]$Proposal = 'epochs',
    [string]$SeedRun = '',
    [int]$Shards = 1,
    [int]$ShardIndex = 0,
    [Parameter(Mandatory=$true)][string]$Out
)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path -LiteralPath $Python)) { throw 'Python missing. Ask the local Agent to adapt the existing CPU-only environment.' }
& $Python -c "import sys; print(sys.version); raise SystemExit(0 if sys.version_info[:2] == (3,12) else 2)"
if ($LASTEXITCODE -ne 0) { throw 'Expected existing Python 3.12.x on Windows; adapt explicitly, do not replace an active environment.' }
$env:PYTHONUTF8 = '1'
$env:OMP_NUM_THREADS = '1'
$env:OPENBLAS_NUM_THREADS = '1'
Push-Location $Root
try {
    $RunArgs = @('-m','research_a_orion_track_memory.trusted_run','--root',$Root,'--out',$Out,'--cases')
    $RunArgs += @($Cases | ForEach-Object { $_.ToString() })
    $RunArgs += '--questions'; $RunArgs += @($Questions | ForEach-Object { $_.ToString() })
    $RunArgs += '--cores'; $RunArgs += @($Cores | ForEach-Object { $_.ToString() })
    $RunArgs += @('--seconds',$Seconds.ToString(),'--max-evaluations',$MaxEvaluations.ToString(),'--total-seconds',$TotalSeconds.ToString(),'--workers',$Workers,'--proposal',$Proposal,'--shards',$Shards.ToString(),'--shard-index',$ShardIndex.ToString())
    if ($SeedRun) { $RunArgs += @('--seed-run',$SeedRun) }
    & $Python @RunArgs
    if ($LASTEXITCODE -ne 0) { throw "Real-graph run failed: $LASTEXITCODE. Keep raw outputs." }
} finally { Pop-Location }
