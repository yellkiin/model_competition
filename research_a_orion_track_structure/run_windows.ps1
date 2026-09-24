[CmdletBinding()]
param(
    [string]$Cases = '001,016,024,044,048,064',
    [string]$Questions = '1,2,3',
    [string]$Cores = '2,5',
    [double]$Seconds = 300,
    [double]$WallSeconds = 1800,
    [int]$MaxEvaluations = 8,
    [string]$Workers = 'auto',
    [int]$Shards = 1,
    [int]$ShardIndex = 0,
    [string]$Python = 'D:\python\python.exe',
    [string]$Official = '',
    [string]$Out = '',
    [string]$WarmSpec = '',
    [string]$SeedIndex = ''
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Python not found: $Python. Ask the local Agent to adapt; no environment is installed automatically."
}
$Version = (& $Python -c 'import sys; print(str(sys.version_info.major)+"."+str(sys.version_info.minor))').Trim()
if ($LASTEXITCODE -ne 0 -or $Version -ne '3.12') {
    throw "Expected existing Python 3.12.x, got $Version. Stop and let the local Agent confirm adaptation."
}
$Repo = Split-Path -Parent $PSScriptRoot
$RunArgs = @('-X','utf8','-u','-m','research_a_orion_track_structure.run',
    '--cases',$Cases,'--questions',$Questions,'--cores',$Cores,
    '--seconds',"$Seconds",'--wall-seconds',"$WallSeconds",
    '--max-evaluations',"$MaxEvaluations",'--workers',$Workers,
    '--shards',"$Shards",'--shard-index',"$ShardIndex")
if ($Official) { $RunArgs += @('--official',$Official) }
if ($Out) { $RunArgs += @('--out',$Out) }
if ($WarmSpec) { $RunArgs += @('--warm-spec',$WarmSpec) }
if ($SeedIndex) { $RunArgs += @('--seed-index',$SeedIndex) }
$ExitCode = 1
Push-Location $Repo
try {
    & $Python @RunArgs
    $ExitCode = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $ExitCode
