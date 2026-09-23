param(
    [ValidateSet('prepare','run','collect','sensitivity')][string]$Stage = 'run',
    [string]$Python = 'D:\python\python.exe',
    [string]$Out = 'research_a_next\runs\pilot',
    [int]$Workers = 2,
    [double]$Minutes = 30,
    [int]$ShardIndex = 0,
    [int]$ShardCount = 1,
    [string]$Archive = '',
    [string]$BaselineCatalog = ''
)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) { throw "Python not found: $Python. Follow LOCAL_AGENT.md." }
$env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'; $env:PYTHONUNBUFFERED='1'
$arguments=@('-X','utf8','-u','-m','research_a_next.run',$Stage,'--out',$Out)
if ($Stage -eq 'prepare') {
    if ($Archive) { $arguments += @('--archive',$Archive) }
    if ($BaselineCatalog) { $arguments += @('--baseline-catalog',$BaselineCatalog) }
} elseif ($Stage -eq 'run') {
    $arguments += @('--workers',"$Workers",'--minutes',"$Minutes",'--shard-index',"$ShardIndex",'--shard-count',"$ShardCount")
} elseif ($Stage -eq 'sensitivity') {
    if (-not $PSBoundParameters.ContainsKey('Minutes')) { $Minutes = 10 }
    $arguments=@('-X','utf8','-u','-m','research_a_next.sensitivity','--source',$Out,'--out',"${Out}_sensitivity",'--minutes',"$Minutes")
}
& $Python @arguments
if ($LASTEXITCODE -ne 0) { throw "A experiment stopped with exit $LASTEXITCODE. Preserve output and read LOCAL_AGENT.md." }
