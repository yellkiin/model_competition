param(
    [string]$Python = 'D:\python\python.exe',
    [ValidateRange(0,2)][int]$ShardIndex = 0,
    [string]$Out = '',
    [string]$Prepared = 'research_a_orion_fusion\runs\prepared_round01',
    [string]$Official = '',
    [string]$Reference = 'research_a_orion_anytime\team_results\day01\combined_final',
    [string]$BaselinePlans = '',
    [string[]]$ExtraPlans = @(),
    [int]$Workers = 0,
    [double]$Seconds = 120,
    [double]$LargeSeconds = 300,
    [int]$Calls = 96,
    [double]$Hours = 8,
    [string]$DeadlineUtc = '',
    [string]$Components = 'sm',
    [string]$FifoModule = '',
    [switch]$PilotOnly
)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path $Python)) { throw "Python missing: $Python. Pass an existing Python 3.12 x64 interpreter; do not alter another running experiment." }
if (-not $Out) { $Out = "research_a_orion_fusion\runs\round01_shard_$ShardIndex" }
$env:PYTHONUTF8 = '1'
& $Python -c "import struct,sys; assert sys.version_info >= (3,12) and struct.calcsize('P') == 8, 'Python >=3.12 x64 required'"
if ($LASTEXITCODE -ne 0) { throw 'Interpreter does not meet the startup requirement.' }
$prep = @('-m','research_a_orion_fusion.campaign','prepare','--out',$Prepared,'--reference',$Reference,'--shards','3')
if ($BaselinePlans) { $prep += @('--baseline-plans',$BaselinePlans) }
& $Python @prep
if ($LASTEXITCODE -ne 0) { throw 'Reference inputs are incomplete; read the concrete missing path, retrieve only that data, then repeat.' }
$cmd = @('-m','research_a_orion_fusion.campaign','run','--manifest',"$Prepared\manifest.json",'--out',$Out,
    '--shard-index',"$ShardIndex",'--workers',"$Workers",'--reserve','0.25','--seconds',"$Seconds",
    '--large-seconds',"$LargeSeconds",'--calls',"$Calls",'--hours',"$Hours",'--components',$Components)
if ($Official) { $cmd += @('--official',$Official) }
if ($FifoModule) { $cmd += @('--fifo-module',$FifoModule) }
foreach ($item in $ExtraPlans) { $cmd += @('--extra-plans',$item) }
if ($DeadlineUtc) {
    $epoch = [DateTimeOffset]::Parse($DeadlineUtc).ToUnixTimeSeconds()
    $cmd += @('--deadline-epoch',"$epoch")
}
if ($PilotOnly) { $cmd += '--pilot-only' }
& $Python @cmd
exit $LASTEXITCODE
