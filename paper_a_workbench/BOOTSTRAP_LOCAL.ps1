param(
 [string]$ProjectRoot=(Get-Location).Path,
 [string]$Repository='yellkiin/model_competition',
 [string]$Repo='',
 [string]$Template='',
 [Alias('Home')][string]$AgentRoot='',
 [string]$DataRoot='C:\Users\LEGION\Desktop\数据',
 [string]$Python='',
 [string]$TemplateRevision='48cedcc9f0053b6afdc7e2db11cc5b45519b8337'
)
$ErrorActionPreference='Stop'
function Run([string]$Exe,[string[]]$Arguments) {
 & $Exe @Arguments
 if ($LASTEXITCODE -ne 0) { throw "$Exe exited $LASTEXITCODE" }
}
$ProjectRoot=(Resolve-Path -LiteralPath $ProjectRoot).Path
if (-not $Repo) { $Repo=Join-Path $ProjectRoot '.orion_paper_cache\repository' }
if (-not $AgentRoot) { $AgentRoot=Join-Path $ProjectRoot 'ORION_Paper_Agent' }
if (-not [IO.Path]::IsPathRooted($Repo)) { $Repo=Join-Path $ProjectRoot $Repo }
if (-not [IO.Path]::IsPathRooted($AgentRoot)) { $AgentRoot=Join-Path $ProjectRoot $AgentRoot }
if (-not $Python) {
 $cmd=Get-Command python -ErrorAction SilentlyContinue
 if ($cmd) { $Python=$cmd.Source } else { throw 'Select an existing Python 3.11+ interpreter with -Python.' }
}
Run $Python @('-c','import sys; assert sys.version_info >= (3,11), "Python 3.11+ required"')
if (-not (Test-Path -LiteralPath $Repo)) {
 Run 'gh' @('auth','status')
 New-Item -ItemType Directory -Force -Path (Split-Path $Repo -Parent) | Out-Null
 Run 'gh' @('repo','clone',$Repository,$Repo,'--','--filter=blob:none','--no-checkout')
}
Run 'git' @('-C',$Repo,'rev-parse','--git-dir')
$entry=Join-Path $PSScriptRoot 'workbench.py'
$session=Join-Path $AgentRoot '.orion_paper\SESSION.json'
if (-not (Test-Path -LiteralPath $session)) {
 $find=@($entry,'locate-template','--project-root',$ProjectRoot)
 if ($Template) { $find+=@('--template',$Template) }
 $located=& $Python @find
 if ($LASTEXITCODE -ne 0) { throw 'Template location failed' }
 $location=($located | Out-String | ConvertFrom-Json)
 $Template=$location.selected
 if (-not $Template) {
  Run 'git' @('-C',$Repo,'fetch','--filter=blob:none','--no-tags','origin',$TemplateRevision)
  $Template=Join-Path $ProjectRoot ('.orion_paper_cache\template-'+$TemplateRevision.Substring(0,12))
  if (-not (Test-Path -LiteralPath $Template)) {
   Run $Python @($entry,'template-source','--repo',$Repo,'--revision',$TemplateRevision,'--out',$Template)
  }
 }
 Run $Python @($entry,'probe','--template',$Template)
 Run $Python @($entry,'install','--template',$Template,'--home',$AgentRoot,'--project-root',$ProjectRoot,'--repo',$Repo,'--data-root',$DataRoot)
} else {
 # Resume only the explicit agent root. There is no search for an earlier workshop.
 Write-Output "Using the recorded production session: $session"
}
$entry=Join-Path $AgentRoot 'paper_a_workbench\workbench.py'
$profile=Join-Path $AgentRoot 'paper_a_workbench\SOURCE_PROFILE.json'
$current=Get-Content -LiteralPath $session -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not $PSBoundParameters.ContainsKey('DataRoot') -and $current.local_data_root) { $DataRoot=$current.local_data_root }
if ($current.snapshot) {
 Write-Output 'Existing source snapshot retained. Use ORION_论文更新提示词.md to adopt newer sources explicitly.'
} else {
 Run $Python @($entry,'sync','--repo',$Repo,'--profile',$profile,'--home',$AgentRoot,'--fetch','--lfs')
 Run $Python @($entry,'prepare-theory','--home',$AgentRoot)
}
Run $Python @($entry,'scan-local','--home',$AgentRoot,'--root',$DataRoot)
Write-Output "Read and execute $AgentRoot\ORION_论文总控提示词.md. The project root is $ProjectRoot."
