param(
  [string]$Python = 'D:\python\python.exe',
  [Parameter(Mandatory=$true)][string]$RunRoot,
  [ValidateRange(0,2)][int]$ShardIndex = 0,
  [string]$Round = 'round03_smf23',
  [string]$Branch = ''
)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
function Invoke-Native([string]$Exe, [string[]]$Arguments) {
  & $Exe @Arguments
  if ($LASTEXITCODE -ne 0) { throw "$Exe failed with exit code $LASTEXITCODE" }
}
$repo = (& git rev-parse --show-toplevel).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Run within the model_competition repository.' }
$publish = "research_a_orion_fusion/team_results/$Round/shard_$ShardIndex"
Invoke-Native $Python @('-m','research_a_orion_fusion.export_results','--root',$RunRoot,'--out',$publish,'--include-all-candidates')
Invoke-Native 'gh' @('auth','status')
$stamp = [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss')
if (-not $Branch) { $Branch = "results/orion-$Round-shard-$ShardIndex-$stamp" }
$temp = Join-Path ([System.IO.Path]::GetTempPath()) ("orion-publication-"+[guid]::NewGuid().ToString('N'))
Invoke-Native 'git' @('fetch','origin','main')
Invoke-Native 'git' @('worktree','add','-b',$Branch,$temp,'origin/main')
$target=Join-Path $temp $publish
New-Item -ItemType Directory -Force -Path $target | Out-Null
Copy-Item -Recurse -Force (Join-Path $repo "$publish/*") $target
Push-Location $temp
try {
  Invoke-Native 'git' @('add','--',$publish)
  Invoke-Native 'git' @('commit','-m',"results(A): publish ORION SMF $Round shard $ShardIndex")
  Invoke-Native 'git' @('push','-u','origin',$Branch)
  Invoke-Native 'gh' @('pr','create','--repo','yellkiin/model_competition','--base','main','--head',$Branch,
    '--title',"ORION SMF $Round 主机 $ShardIndex：实际结果与论文数据",
    '--body',"Only $publish is changed. Actual coverage, failures, 30-second traces, selected plans, original responses and paper CSVs are included. Completion is stated by shard_status.json/manifest, not inferred from publication. No automatic merge.")
} finally { Pop-Location }
Write-Output "Publication worktree retained at $temp"
