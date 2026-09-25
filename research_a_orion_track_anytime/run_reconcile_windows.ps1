param(
    [string]$PythonExe = 'D:\python\python.exe',
    [string]$Cases = '044,083,084',
    [string]$Questions = '3',
    [string]$Cores = '5',
    [string]$Methods = 'old,peer_v4,repair_v6',
    [string]$Modes = 'warm',
    [double]$Seconds = 30,
    [double]$TotalSeconds = 900,
    [int]$MaxEvaluations = 16,
    [string]$Workers = 'auto',
    [int]$Shards = 1,
    [int]$ShardIndex = 0,
    [string]$SeedManifest = '',
    [string]$Out = ''
)
$ErrorActionPreference = 'Stop'
$Repo = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path -LiteralPath $PythonExe)) { throw "Python not found: $PythonExe" }
if ($Shards -lt 1 -or $ShardIndex -lt 0 -or $ShardIndex -ge $Shards) { throw 'Invalid shard parameters' }
if ($Out -eq '') { $Out = 'research_a_orion_track_anytime/results/reconcile_local_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '_shard' + $ShardIndex }
Push-Location $Repo
try {
    if ($SeedManifest -eq '') {
        $Sorted = @($Cases.Split(',') | ForEach-Object { [int]($_.Replace('case_', '')) } | Sort-Object -Unique)
        $Assigned = @()
        for ($i = 0; $i -lt $Sorted.Count; $i++) {
            if (($i % $Shards) -eq $ShardIndex) { $Assigned += ('{0:D3}' -f $Sorted[$i]) }
        }
        if ($Assigned.Count -eq 0) { Write-Output 'No cases assigned to this shard.'; return }
        $ValidationOut = $Out + '_validated_seeds'
        & $PythonExe -u -m research_a_orion_track_anytime.reconcile_revalidate --cases ($Assigned -join ',') --questions $Questions --cores $Cores --out $ValidationOut
        if ($LASTEXITCODE -ne 0) { throw 'Official seed revalidation failed. No search launched.' }
        $SeedManifest = Join-Path $ValidationOut 'seed_manifest.json'
    }
    if (-not (Test-Path -LiteralPath $SeedManifest)) { throw 'Freshly re-evaluated seed manifest not found.' }
    & $PythonExe -u -m research_a_orion_track_anytime.reconcile_runner --cases $Cases --questions $Questions --cores $Cores --methods $Methods --modes $Modes --seconds $Seconds --total-seconds $TotalSeconds --max-evaluations $MaxEvaluations --workers $Workers --shards $Shards --shard-index $ShardIndex --seed-manifest $SeedManifest --out $Out
    if ($LASTEXITCODE -ne 0) { throw 'Execution failed: inspect recorded errors; retain existing plans.' }
} finally { Pop-Location }
