param(
 [string]$Branch='integration/orion-trident-publish-20260925',
 [string]$Base='main',
 [string]$Repository='yellkiin/model_competition'
)
$ErrorActionPreference='Stop'
function Native([string]$Exe,[string[]]$Arguments) { & $Exe @Arguments; if ($LASTEXITCODE -ne 0) { throw "$Exe exited $LASTEXITCODE" } }
Write-Warning 'PR #38 already exists. This helper is only for recovery/offline packages; production hosts should fetch the existing branch.'
$source=$PSScriptRoot
$repo=(& git -C $source rev-parse --show-toplevel).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Put the package inside an existing authorized clone.' }
Native 'gh' @('auth','status')
Native 'git' @('-C',$repo,'fetch','--filter=blob:none','--no-tags','origin',$Base)
$temp=Join-Path ([IO.Path]::GetTempPath()) ('orion-trident-code-'+[guid]::NewGuid().ToString('N'))
Native 'git' @('-C',$repo,'worktree','add','--no-checkout','-b',$Branch,$temp,"origin/$Base")
Native 'git' @('-C',$temp,'sparse-checkout','set','--no-cone','/research_a_orion_trident/')
Native 'git' @('-C',$temp,'reset','--mixed','HEAD')
$target=Join-Path $temp 'research_a_orion_trident'
if (Test-Path $target) { throw 'Target directory already exists: inspect and choose an incremental update; no overwrite is performed.' }
New-Item -ItemType Directory -Path $target | Out-Null
$exclude=@('runs','inputs','results','__pycache__','session_clock.json')
Get-ChildItem -LiteralPath $source -Force | Where-Object {$_.Name -notin $exclude} | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $target -Recurse }
Push-Location $temp
try {
 Native 'git' @('add','--','research_a_orion_trident')
 Native 'git' @('commit','-m','feat(A): independent Trident SMF integration, real evidence and three-host campaign [skip ci]')
 Native 'git' @('push','-u','origin',$Branch)
 Native 'gh' @('pr','create','--repo',$Repository,'--base',$Base,'--head',$Branch,'--title','ORION Trident：独立三线整合、实测修正与三机600秒实验','--body-file','research_a_orion_trident/PR_BODY.md')
} finally { Pop-Location }
Write-Output "Publication worktree retained: $temp"
