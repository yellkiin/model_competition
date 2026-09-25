param(
 [string]$Python='D:\python\python.exe',
 [Parameter(Mandatory=$true)][string]$RunRoot,
 [ValidateRange(0,2)][int]$ShardIndex=0,
 [string]$Round='unified_round01',
 [string]$Repository='yellkiin/model_competition'
)
$ErrorActionPreference='Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
function Native([string]$Exe,[string[]]$Arguments) { & $Exe @Arguments; if ($LASTEXITCODE -ne 0) { throw "$Exe exited $LASTEXITCODE" } }
$repo=(& git rev-parse --show-toplevel).Trim();if ($LASTEXITCODE -ne 0) { throw 'Use an existing authorized clone.' }
Native 'gh' @('auth','status')
$stamp=[DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss')
$branch="results/orion-$Round-shard-$ShardIndex-$stamp";$tag="orion-$Round-shard-$ShardIndex-$stamp"
$publication=Join-Path ([IO.Path]::GetTempPath()) ('unified-export-'+[guid]::NewGuid().ToString('N'))
Native $Python @('-m','research_a_orion_unified.export_results','--root',$RunRoot,'--out',$publication,'--include-all-candidates','--part-mib','40')
$manifest=Get-Content -Raw (Join-Path $publication 'PUBLICATION.json') | ConvertFrom-Json
Native 'git' @('fetch','--filter=blob:none','origin','main')
$worktree=Join-Path ([IO.Path]::GetTempPath()) ('unified-results-'+[guid]::NewGuid().ToString('N'))
Native 'git' @('worktree','add','--no-checkout','-b',$branch,$worktree,'origin/main')
Native 'git' @('-C',$worktree,'sparse-checkout','set','--no-cone','/research_a_orion_unified/')
Native 'git' @('-C',$worktree,'reset','--mixed','HEAD')
$relative="research_a_orion_unified/team_results/$Round/shard_$ShardIndex";$target=Join-Path $worktree $relative
New-Item -ItemType Directory -Force -Path $target | Out-Null
$rawNames=@($manifest.archive_parts | ForEach-Object {$_.path})
Get-ChildItem -LiteralPath $publication -Force | Where-Object {$_.Name -notin $rawNames} | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $target -Recurse }
Push-Location $worktree
try {
 Native 'git' @('add','--',$relative)
 Native 'git' @('commit','-m',"results(A): Unified $Round shard $ShardIndex tables and actual plans [skip ci]")
 Native 'git' @('push','-u','origin',$branch)
 # Large raw evidence belongs in Release assets, not a multi-gigabyte Git push.
 Native 'gh' @('release','create',$tag,'--repo',$Repository,'--target',$branch,'--prerelease','--title',"Unified $Round shard $ShardIndex raw records",'--notes',"Actual original evaluator responses, candidates, traces and failures. Completion is stated by PUBLICATION.json; no automatic merge.")
 foreach ($part in $manifest.archive_parts) { Native 'gh' @('release','upload',$tag,(Join-Path $publication $part.path),'--repo',$Repository) }
 $releaseText=& gh api "repos/$Repository/releases/tags/$tag";if ($LASTEXITCODE -ne 0) { throw 'Release readback failed.' }
 $release=$releaseText | ConvertFrom-Json
 foreach ($part in $manifest.archive_parts) {
   $asset=@($release.assets | Where-Object {$_.name -eq $part.path})
   if ($asset.Count -ne 1 -or $asset[0].state -ne 'uploaded' -or $asset[0].size -ne $part.bytes) { throw "Asset receipt mismatch: $($part.path)" }
 }
 $assets=@{tag=$tag;release_url=$release.html_url;assets=@($release.assets | Select-Object id,name,size,state,browser_download_url)}
 $assets | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 (Join-Path $target 'RAW_ASSETS.json')
 $manifest | Add-Member -NotePropertyName raw_location -NotePropertyValue @{kind='GitHub Release';tag=$tag;index='RAW_ASSETS.json'} -Force
 $manifest | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 (Join-Path $target 'PUBLICATION.json')
 Native 'git' @('add','--',$relative)
 Native 'git' @('commit','-m',"docs(A): record uploaded raw asset receipts for Unified shard $ShardIndex [skip ci]")
 Native 'git' @('push','origin',$branch)
 Native 'gh' @('pr','create','--repo',$Repository,'--base','main','--head',$branch,'--title',"Unified $Round 主机 $ShardIndex：实际成绩与论文数据",'--body',"Only $relative is changed. Per-case results, half-minute curves, selected plans, source/cost fields and real raw Release assets are included. Read PUBLICATION.json for actual completion. No automatic merge.")
} finally { Pop-Location }
Write-Output "Review worktree: $worktree; raw export retained: $publication"
