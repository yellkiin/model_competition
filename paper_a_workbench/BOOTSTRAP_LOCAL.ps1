param(
 [string]$Repository='yellkiin/model_competition',
 [string]$Repo='E:\orion_paper_repo',
 [string]$Template='E:\20hw_myskill_distribution',
 [string]$Home='E:\ORION_Paper_Agent',
 [string]$Python='D:\python\python.exe',
 [string]$TemplateRevision='48cedcc9f0053b6afdc7e2db11cc5b45519b8337'
)
$ErrorActionPreference='Stop'
function Run([string]$Exe,[string[]]$Arguments) {
 & $Exe @Arguments
 if ($LASTEXITCODE -ne 0) { throw "$Exe exited $LASTEXITCODE" }
}
if (-not (Test-Path -LiteralPath $Python)) {
 $cmd=Get-Command python -ErrorAction SilentlyContinue
 if ($cmd) { $Python=$cmd.Source } else { throw 'Select an existing Python 3.11+ interpreter with -Python.' }
}
Run $Python @('-c','import sys; assert sys.version_info >= (3,11), "Python 3.11+ required"')
if (-not (Test-Path -LiteralPath $Repo)) {
 Run 'gh' @('auth','status')
 Run 'gh' @('repo','clone',$Repository,$Repo,'--','--filter=blob:none','--no-checkout')
}
Run 'git' @('-C',$Repo,'rev-parse','--git-dir')
Run 'git' @('-C',$Repo,'fetch','--filter=blob:none','--no-tags','origin',$TemplateRevision)
$entry=Join-Path $PSScriptRoot 'workbench.py'
if (-not (Test-Path (Join-Path $Template 'AGENTS.md'))) {
 $Template=Join-Path (Split-Path $Home -Parent) 'ORION_Paper_Template_Source'
 Run $Python @($entry,'template-source','--repo',$Repo,'--revision',$TemplateRevision,'--out',$Template)
}
Run $Python @($entry,'probe','--template',$Template)
Run $Python @($entry,'install','--template',$Template,'--home',$Home)
Run $Python @((Join-Path $Home 'paper_a_workbench\workbench.py'),'sync','--repo',$Repo,
 '--profile',(Join-Path $Home 'paper_a_workbench\SOURCE_PROFILE.json'),'--home',$Home,'--fetch','--lfs')
Write-Output "Open Codex in $Home and execute ORION_论文总控提示词.md. The old template/workshop are unchanged."
