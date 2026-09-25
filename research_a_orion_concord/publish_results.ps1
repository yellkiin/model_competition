param([ValidateRange(0,2)][int]$Shard=0,[string]$Python='D:\python\python.exe',
 [string]$WorkRoot='D:\orion_concord',[string]$Round='round01')
$ErrorActionPreference='Stop'
$repo=Split-Path $PSScriptRoot -Parent
$run=Join-Path $WorkRoot "runs\$Round\shard_$Shard"
$stamp=Get-Date -Format 'yyyyMMdd_HHmmss'
$package=Join-Path $WorkRoot "publication\${Round}_shard_${Shard}_$stamp"
$branch="results/concord-${Round}-shard-${Shard}-$stamp"
$relative="research_a_orion_concord/team_results/$Round/shard_$Shard/$stamp"
Push-Location $repo
try {
 & $Python -m research_a_orion_concord.package pack --roots $run --out $package
 if ($LASTEXITCODE) { throw 'Result archive failed; existing evidence remains in the run directory.' }
 git switch -c $branch
 if ($LASTEXITCODE) { throw 'Choose a new result branch; do not overwrite another result branch.' }
 New-Item -ItemType Directory -Force -Path $relative | Out-Null
 Copy-Item -Recurse -Path (Join-Path $package '*') -Destination $relative
 git add -- $relative
 git commit -m "results(concord): $Round shard $Shard original responses and paper data [skip ci]"
 if ($LASTEXITCODE) { throw 'Commit failed.' }
 git push -u origin $branch
 if ($LASTEXITCODE) { throw 'Push failed; keep local result commit.' }
 gh pr create --repo yellkiin/model_competition --base feat/orion-concord-graph600-20260925 --head $branch --title "Concord $Round shard $Shard results" --body "Actual original responses, selected plans, failures, graph-budget clocks and paper data at $relative. Read collection.json for completeness. No automatic merge."
 if ($LASTEXITCODE) { throw 'Result branch pushed; PR creation needs the current gh authorization.' }
} finally { Pop-Location }
