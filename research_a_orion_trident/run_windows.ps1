param(
    [string]$Python = 'D:\python\python.exe',
    [ValidateRange(0,2)][int]$ShardIndex = 0,
    [string]$Assets = '',
    [string]$Out = '',
    [int]$Workers = 0,
    [ValidateRange(1,600)][int]$Seconds = 600,
    [double]$Hours = 12,
    [string]$DeadlineUtc = '',
    [ValidateSet('s','m','f','sm','sf','mf','smf')][string]$Components = 'smf',
    [string[]]$ExtraPlans = @(),
    [switch]$FetchInputs,
    [switch]$PilotOnly,
    [switch]$SkipMechanisms
)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
function Native([string]$Exe,[string[]]$Arguments) {
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Exe exited $LASTEXITCODE; retain its concrete records." }
}
if (-not (Test-Path -LiteralPath $Python)) { throw "Select an existing 64-bit Python 3.12 interpreter with -Python; do not alter active experiments." }
Native $Python @('-c', 'import struct,sys; assert sys.version_info[:2] == (3,12) and struct.calcsize("P")==8, "Use existing CPU-only Python 3.12.x x64"')
$env:PYTHONUTF8='1';$env:OMP_NUM_THREADS='1';$env:OPENBLAS_NUM_THREADS='1';$env:MKL_NUM_THREADS='1'
if (-not $Assets) { $Assets="research_a_orion_trident/runs/assets_shard_$ShardIndex" }
if (-not $Out) { $Out="research_a_orion_trident/runs/round01/shard_$ShardIndex" }
if ($FetchInputs) {
    Native $Python @('-m','research_a_orion_trident.bootstrap','--shard-index',"$ShardIndex",'--out',$Assets,'--fetch','--literature')
    Native $Python @('-m','research_a_orion_trident.study_inputs','--out',"$Assets/studies",'--fetch')
}
$receipt=Join-Path $Assets 'INPUT_RECEIPT.json'
if (-not (Test-Path $receipt)) { throw "Run once with -FetchInputs, or use bootstrap.py to install the original files in $Assets." }
$official=Join-Path $Assets 'official';$reference=Join-Path $Assets 'reference';$plans=Join-Path $Assets 'reference_plans'
Native $Python @('-m','research_a_orion_trident.restore_seeds','--official',$official,'--out',"$Assets/peer_seeds")
$prepared=Join-Path $Assets 'prepared'
Native $Python @('-m','research_a_orion_trident.campaign','prepare','--reference',$reference,'--baseline-plans',$plans,'--out',$prepared,'--shards','3','--study-materials',"$Assets/studies/materials")
$cmd=@('-m','research_a_orion_trident.campaign','run','--manifest',"$prepared/manifest.json",'--out',$Out,
 '--official',$official,'--shard-index',"$ShardIndex",'--workers',"$Workers",'--reserve','0.25',
 '--seconds',"$Seconds",'--large-seconds',"$Seconds",'--calls','2048','--hours',"$Hours",'--components',$Components,
 '--source-policy','work_adaptive','--stop-gap','0.0025','--ablation-limit','6','--diagnostic-seconds','120',
 '--extra-plans',"$Assets/peer_seeds",'--extra-plans',"$Assets/studies",'--extra-plans','research_a_orion_trident/evidence/available_seeds')
foreach ($item in $ExtraPlans) { $cmd+=@('--extra-plans',$item) }
if ($DeadlineUtc) { $cmd+=@('--deadline-epoch',"$([DateTimeOffset]::Parse($DeadlineUtc).ToUnixTimeSeconds())") }
if ($PilotOnly) { $cmd+='--pilot-only' }
if ($SkipMechanisms) { $cmd+='--skip-mechanisms' }
& $Python @cmd
$code=$LASTEXITCODE
Write-Output "Results: $Out; exit=$code. Partial runs retain valid plans and missing-job records."
exit $code
