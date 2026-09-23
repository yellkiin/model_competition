param(
    [string]$Python = 'D:\python\python.exe',
    [string]$Out = '',
    [int]$Workers = 2,
    [double]$WallSeconds = 1800,
    [double]$JobSeconds = 120,
    [double]$EvalSeconds = 45,
    [int]$Budget = 6,
    [int]$Shards = 1,
    [int]$Shard = 0,
    [int[]]$Cases = @(),
    [int[]]$Cores = @(2,5),
    [string]$Archive = '',
    [switch]$Resume
)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw 'Python path not found. Pass -Python with an existing Python 3.10+ interpreter; do not reinstall a working environment.'
}
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUNBUFFERED = '1'
$InvokeArgs = @('-X','utf8','-u','-m','research_a_aster_rbc.run',
    '--workers',"$Workers",'--wall-seconds',"$WallSeconds",'--job-seconds',"$JobSeconds",
    '--eval-seconds',"$EvalSeconds",'--budget',"$Budget",'--shards',"$Shards",'--shard',"$Shard")
$InvokeArgs += '--cores'
foreach ($Core in $Cores) { $InvokeArgs += "$Core" }
if ($Cases.Count -gt 0) {
    $InvokeArgs += '--cases'
    foreach ($Case in $Cases) { $InvokeArgs += "$Case" }
}
if ($Out) { $InvokeArgs += @('--out',$Out) }
if ($Archive) { $InvokeArgs += @('--archive',$Archive) }
if ($Resume) { $InvokeArgs += '--resume' }
Push-Location $Root
try {
    & $Python @InvokeArgs
    if ($LASTEXITCODE -ne 0) { throw "ASTER exited with code $LASTEXITCODE; preserve existing results and read job.log." }
} finally { Pop-Location }
