param(
    [string]$PythonExe = 'D:\python\python.exe',
    [string]$Cases = '001,024,044,059,083,084,086',
    [string]$Questions = '1,2,3',
    [string]$Cores = '2,5',
    [string]$Methods = 'old,combined',
    [string]$Modes = 'warm',
    [string]$Revision = 'v4',
    [double]$Seconds = 120,
    [double]$TotalSeconds = 2400,
    [int]$MaxEvaluations = 128,
    [double]$PairSeconds = 30,
    [string]$Workers = 'auto',
    [int]$MaxWorkers = 2,
    [int]$Shards = 1,
    [int]$ShardIndex = 0,
    [Parameter(Mandatory=$true)][string]$SeedManifest,
    [string]$Out = ''
)
$ErrorActionPreference = 'Stop'
$Repo = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path -LiteralPath $PythonExe)) { throw "Python not found: $PythonExe" }
if ($Out -eq '') { $Out = 'research_a_orion_track_anytime/results/wu_v4_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '_s' + $ShardIndex }
Push-Location $Repo
try {
    if (-not (Test-Path -LiteralPath $SeedManifest)) { throw "Seed manifest not found: $SeedManifest" }
    & $PythonExe -u -m research_a_orion_track_anytime.runner --cases $Cases --questions $Questions --cores $Cores --methods $Methods --modes $Modes --revision $Revision --seconds $Seconds --total-seconds $TotalSeconds --max-evaluations $MaxEvaluations --pair-seconds $PairSeconds --workers $Workers --max-workers $MaxWorkers --shards $Shards --shard-index $ShardIndex --seed-manifest $SeedManifest --out $Out
    if ($LASTEXITCODE -ne 0) { throw "Run failed; retain original evidence and incumbent files. Exit: $LASTEXITCODE" }
} finally { Pop-Location }
