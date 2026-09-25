param(
    [string]$PythonExe = 'D:\python\python.exe',
    [string]$Cases = '001,016,024,044,048,059,064',
    [string]$Questions = '1,2,3',
    [string]$Cores = '5',
    [string]$Methods = 'old,safe',
    [double]$Seconds = 300,
    [double]$WallSeconds = 1800,
    [int]$MaxEvaluations = 128,
    [string]$Workers = 'auto',
    [int]$Shards = 1,
    [int]$ShardIndex = 0,
    [Parameter(Mandatory=$true)][string]$SeedManifest,
    [string]$Out = ''
)
$ErrorActionPreference = 'Stop'
$Repo = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path -LiteralPath $PythonExe)) { throw "Python executable not found: $PythonExe" }
if ($Out -eq '') { $Out = 'research_a_orion_track_structure/results/safe_local_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '_shard' + $ShardIndex }
Push-Location $Repo
try {
    if (-not (Test-Path -LiteralPath $SeedManifest)) { throw "Seed manifest not found: $SeedManifest" }
    & $PythonExe -u -m research_a_orion_track_structure.safe_refine --cases $Cases --questions $Questions --cores $Cores --methods $Methods --seconds $Seconds --wall-seconds $WallSeconds --max-evaluations $MaxEvaluations --workers $Workers --shards $Shards --shard-index $ShardIndex --seed-manifest $SeedManifest --out $Out
    if ($LASTEXITCODE -ne 0) { throw "Run failed; retain logs and existing incumbent plans. Exit: $LASTEXITCODE" }
} finally { Pop-Location }
