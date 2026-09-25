param(
  [int[]]$Cases = @(48,68,85,86,36,84,97),
  [int[]]$Questions = @(1,2,3),
  [int[]]$Cores = @(1,2,3,4,5),
  [double]$Seconds = 300,
  [int]$MaxEvaluations = 40,
  [double]$TotalSeconds = 2100,
  [double]$PairTotalSeconds = 360,
  [string]$Workers = 'auto',
  [int]$Shards = 1,
  [int]$ShardIndex = 0,
  [string]$Python = 'D:\python\python.exe',
  [string]$Out = 'research_a_orion_track_memory/results/frozen_local',
  [switch]$AllowOtherPython
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Python)) { throw "Python missing: $Python. Adapt an isolated interpreter explicitly." }
$version = & $Python -c "import sys; print(str(sys.version_info.major)+'.'+str(sys.version_info.minor))"
if ($LASTEXITCODE -ne 0) { throw 'Python startup failed.' }
if ($version.Trim() -ne '3.12' -and -not $AllowOtherPython) { throw "Expected Python 3.12.x; got $version. Use an explicit local adaptation, not an automatic environment installation." }
$root = Split-Path -Parent $PSScriptRoot
$env:PYTHONUTF8 = '1'
$env:OMP_NUM_THREADS = '1'
$env:OPENBLAS_NUM_THREADS = '1'
$arguments = @('-m','research_a_orion_track_memory.continuous_run','--root',$root,'--out',$Out,'--cases') + $Cases
$arguments += @('--questions') + $Questions + @('--cores') + $Cores
$arguments += @('--seconds',$Seconds,'--max-evaluations',$MaxEvaluations,'--total-seconds',$TotalSeconds,'--pair-total-seconds',$PairTotalSeconds,'--workers',$Workers,'--shards',$Shards,'--shard-index',$ShardIndex)
Push-Location $root
try {
  & $Python @arguments
  if ($LASTEXITCODE -ne 0) { throw "Experiment failed with exit code $LASTEXITCODE; keep the output directory." }
  & $Python -m research_a_orion_track_memory.curve_analysis --root $root --run $Out
  if ($LASTEXITCODE -ne 0) { throw "Analysis failed with exit code $LASTEXITCODE; raw responses are retained." }
} finally { Pop-Location }
