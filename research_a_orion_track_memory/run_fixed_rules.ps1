param(
  [int[]]$Cases,
  [int[]]$Questions = @(1,2,3),
  [int[]]$Cores = @(5),
  [double]$SecondsPerPhase = 60,
  [int]$MaxEvaluations = 16,
  [double]$TotalSecondsPerPhase = 1200,
  [string]$Workers = 'auto',
  [int]$Shards = 1,
  [int]$ShardIndex = 0,
  [string]$Out = 'research_a_orion_track_memory/results/fixed_rules_local',
  [string]$Python = 'D:\python\python.exe'
)
$ErrorActionPreference = 'Stop'
if (-not $Cases -or $Cases.Count -eq 0) { throw '-Cases is required' }
if (-not (Test-Path $Python)) { $Python = 'python' }
$Root = (Resolve-Path '.').Path
$StageA = Join-Path $Out 'stage_epochs'
$StageB = Join-Path $Out 'stage_local'

& $Python -m research_a_orion_track_memory.trusted_run --root $Root --out $StageA --cases $Cases --questions $Questions --cores $Cores --seconds $SecondsPerPhase --max-evaluations $MaxEvaluations --workers $Workers --total-seconds $TotalSecondsPerPhase --shards $Shards --shard-index $ShardIndex --proposal epochs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $Python -m research_a_orion_track_memory.trusted_run --root $Root --out $StageB --seed-run $StageA --cases $Cases --questions $Questions --cores $Cores --seconds $SecondsPerPhase --max-evaluations $MaxEvaluations --workers $Workers --total-seconds $TotalSecondsPerPhase --shards $Shards --shard-index $ShardIndex --proposal local
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if ($Questions -contains 3) {
  & $Python -m research_a_orion_track_memory.pair_selected --run $StageB --total-seconds ([Math]::Max(600,$TotalSecondsPerPhase)) --workers $Workers
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
Write-Host "Fixed rules complete: $StageB"
