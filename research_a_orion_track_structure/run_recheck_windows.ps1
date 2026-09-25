[CmdletBinding()]
param(
    [string]$Python = 'D:\python\python.exe',
    [string]$Cases = '016,024,044,048,064,001,059',
    [string]$Questions = '1,2,3',
    [string]$Cores = '2,5',
    [string]$Methods = 'old,published,corrected',
    [ValidateSet('cold_start','warm_start')][string]$Mode = 'cold_start',
    [double]$Seconds = 30,
    [int]$MaxEvaluations = 8,
    [double]$WallSeconds = 1800,
    [double]$PairSeconds = 120,
    [string]$Workers = 'auto',
    [int]$Shards = 1,
    [int]$ShardIndex = 0,
    [int]$Rep = 0,
    [string]$SeedRoot = '',
    [string]$SeedSpec = '',
    [string]$Out = ''
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) { throw 'Existing Python not found; adapt the local interpreter without changing other experiments.' }
$Version = (& $Python -c 'import sys; print(str(sys.version_info.major)+"."+str(sys.version_info.minor))').Trim()
if ($LASTEXITCODE -ne 0 -or $Version -ne '3.12') { throw "Expected existing Python 3.12.x, got $Version. Confirm a local environment adaptation before running." }
if ($Shards -lt 1 -or $ShardIndex -lt 0 -or $ShardIndex -ge $Shards) { throw 'Invalid sharding parameters.' }
if ($Mode -eq 'warm_start' -and -not $SeedRoot -and -not $SeedSpec) { throw 'Warm starts require completed fresh fixed-plan replay directories.' }
if (-not $Out) { $Out = 'research_a_orion_track_structure/results/local_recheck_' + (Get-Date -Format 'yyyyMMdd_HHmmss') }
$Repo = Split-Path -Parent $PSScriptRoot
$RunArgs = @('-X','utf8','-u','-m','research_a_orion_track_structure.recheck_run','--cases',$Cases,'--questions',$Questions,'--cores',$Cores,'--methods',$Methods,'--mode',$Mode,'--seconds',"$Seconds",'--max-evaluations',"$MaxEvaluations",'--wall-seconds',"$WallSeconds",'--pair-seconds',"$PairSeconds",'--workers',$Workers,'--shards',"$Shards",'--shard-index',"$ShardIndex",'--rep',"$Rep",'--out',$Out)
if ($SeedRoot) { $RunArgs += @('--seed-root',$SeedRoot) }
if ($SeedSpec) { $RunArgs += @('--seed-spec',$SeedSpec) }
$Code = 1
Push-Location $Repo
try { & $Python @RunArgs; $Code = $LASTEXITCODE } finally { Pop-Location }
exit $Code
