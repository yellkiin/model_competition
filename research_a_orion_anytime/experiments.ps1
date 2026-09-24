[CmdletBinding()]
param(
    [ValidateSet('auto','pilot','formal','mechanisms','sensitivity')][string]$Stage='auto',
    [string]$Python='D:\python\python.exe',
    [string]$Official='', [string]$Out='research_a_orion_anytime\runs\auto',
    [ValidateSet(1,2)][int]$Workers=2, [double]$Hours=11.5,
    [double]$Seconds=30, [double]$LargeSeconds=180, [int]$Calls=24,
    [int]$RefineSeconds=30, [int]$Shards=1, [int]$ShardIndex=0,
    [string]$Archive='', [switch]$RestoreInputs,
    [string]$Gate='', [string]$Index='', [switch]$ReoptimizeGrid
)
$ErrorActionPreference='Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding
$OutputEncoding = [Console]::OutputEncoding
if (!(Test-Path -LiteralPath $Python)) { throw "Missing interpreter: $Python. See setup_windows.ps1." }
if ($Hours -le 0 -or $Hours -gt 12) { throw 'Hours must be in (0,12].' }
$Repo=Split-Path -Parent $PSScriptRoot
if (!$Archive -and (Test-Path -LiteralPath (Join-Path $Repo 'A题.zip'))) {$Archive=Join-Path $Repo 'A题.zip'}
Push-Location $Repo
try {
    $env:PYTHONUTF8='1'; $env:PYTHONHASHSEED='0'
    $raw=& $Python -m research_a_orion_anytime.run probe
    if ($LASTEXITCODE -ne 0) { throw 'Environment probe failed' }
    $probe=($raw -join "`n") | ConvertFrom-Json
    if (!$probe.reference_compatible) { throw 'Use 64-bit CPython 3.12.x on Windows; configure an isolated interpreter and pass -Python.' }
    if ($null -ne $probe.available_memory_gib -and $probe.available_memory_gib -lt 4) { throw 'Available memory below conservative 4 GiB admission threshold' }
    $Workers=[Math]::Min($Workers,[int]$probe.recommended_workers)
    $argv=@('-u','-m','research_a_orion_anytime.watchdog',$Stage,'--out',$Out,'--workers',"$Workers",'--hours',"$Hours",
            '--seconds',"$Seconds",'--large-seconds',"$LargeSeconds",'--calls',"$Calls",'--refine-seconds',"$RefineSeconds",
            '--shards',"$Shards",'--shard-index',"$ShardIndex")
    if ($Official) {$argv+=@('--official',$Official)}
    if ($Archive) {$argv+=@('--archive',$Archive)}
    if ($RestoreInputs) {$argv+='--restore-inputs'}
    if ($Gate) {$argv+=@('--gate',$Gate)}
    if ($Index) {$argv+=@('--index',$Index)}
    if ($ReoptimizeGrid) {$argv+='--reoptimize-grid'}
    & $Python @argv
    if ($LASTEXITCODE -ne 0) { throw "Campaign stopped with exit code $LASTEXITCODE. Keep outputs; inspect gate.json, capacity_admission.json, stderr.txt and watchdog_status.json. This is not a completed 100-case result." }
} finally { Pop-Location }
