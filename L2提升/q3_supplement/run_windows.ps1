param(
    [ValidateRange(0,2)][int]$ShardIndex,
    [string[]]$BaseRoots = @(),
    [string]$BaseManifest = '',
    [string]$Python = 'D:\python\python.exe',
    [string]$Official = '',
    [string]$Out = '',
    [int]$Workers = 0,
    [int[]]$Cores = @(1,2,3,4,5),
    [string[]]$Cases = @(),
    [int]$Seconds = 120,
    [double]$Hours = 4,
    [double]$MinGain = 0.001,
    [ValidateSet('bank_only','selective','explore')][string]$Policy = 'bank_only',
    [switch]$RepairMissingPairs
)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
if (-not (Test-Path $Python)) { throw "Use an existing Python 3.12 x64 interpreter and pass -Python. Not found: $Python" }
if (-not $BaseManifest -and $BaseRoots.Count -eq 0) { throw 'Pass this host actual final Trident raw result directory via -BaseRoots, or explicit -BaseManifest. Summary tables alone are not plans.' }
if (-not $Out) { $Out = "L2提升\q3_supplement\runs\l2_patch01_shard_$ShardIndex" }
$env:PYTHONUTF8 = '1'
$cmd = @('-m','L2提升.q3_supplement.run','run','--shard-index',"$ShardIndex",'--out',$Out,'--backend','trident',
 '--workers',"$Workers",'--seconds',"$Seconds",'--hours',"$Hours",'--min-gain',"$MinGain",'--policy',$Policy)
foreach ($root in $BaseRoots) { $cmd += @('--base-root',$root) }
if ($BaseManifest) { $cmd += @('--base-manifest',$BaseManifest) }
if ($Official) { $cmd += @('--official',$Official) }
$cmd += '--cores'; foreach ($n in $Cores) { $cmd += "$n" }
if ($Cases.Count -gt 0) { $cmd += '--cases'; $cmd += $Cases }
if ($RepairMissingPairs) { $cmd += '--repair-missing-pairs' }
& $Python @cmd
exit $LASTEXITCODE
