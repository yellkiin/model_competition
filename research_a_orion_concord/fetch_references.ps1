param([ValidateRange(0,2)][int]$Shard=0,[string]$WorkRoot='D:\orion_concord')
$ErrorActionPreference='Stop'
$manifest=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'SHARDS.json') -Raw | ConvertFrom-Json
$cases=$manifest.shards."$Shard".cases
$tags=@('orion-structure-results-20260925-0455','anytime-reconcile-20260925-1012')
foreach ($tag in $tags) {
 $target=Join-Path $WorkRoot "archives\$tag";New-Item -ItemType Directory -Force -Path $target | Out-Null
 $json=gh api "repos/yellkiin/model_competition/releases/tags/$tag"
 if ($LASTEXITCODE) { throw "Read the saved source release index for $tag; keep current working experiments intact." }
 $release=$json | ConvertFrom-Json
 foreach ($asset in $release.assets) {
  if ($asset.name -notmatch '\.zip$' -or $asset.name -match 'snapshot|log|report|code') { continue }
  $matchesCase=$false
  foreach ($case in $cases) {
   $number=$case.Replace('case_','')
   if ($asset.name -match "case[-_]?$number") { $matchesCase=$true;break }
  }
  if ($matchesCase -and !(Test-Path (Join-Path $target $asset.name))) {
   gh release download $tag --repo yellkiin/model_competition --pattern $asset.name --dir $target
   if ($LASTEXITCODE) { throw "Download failed: $($asset.name). Reuse a local raw-result archive instead." }
  }
 }
}
Write-Output "Newer result archives for this shard: $(Join-Path $WorkRoot 'archives')"
