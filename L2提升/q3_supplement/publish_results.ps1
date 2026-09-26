param([ValidateRange(0,2)][int]$ShardIndex,[string]$RunRoot,[string]$Python='D:\python\python.exe',[string]$Round='l2_patch01')
$ErrorActionPreference='Stop'
Set-Location (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
$repo=(Get-Location).Path
if (-not $RunRoot) { $RunRoot="L2提升\q3_supplement\runs\${Round}_shard_$ShardIndex" }
$dest="L2提升\q3_supplement\team_results\$Round\shard_$ShardIndex"
& $Python -m L2提升.q3_supplement.export --root $RunRoot --out $dest
if ($LASTEXITCODE -ne 0) { throw 'Export failed. Keep original results.' }
Get-Command gh -ErrorAction Stop | Out-Null
Get-Command git -ErrorAction Stop | Out-Null
gh auth status
if ($LASTEXITCODE -ne 0) { throw 'Local package is ready. Authorize GitHub CLI before creating a result PR.' }
$stamp=Get-Date -Format 'yyyyMMdd-HHmmss'
$branch="results/l2-patch-$Round-shard-$ShardIndex-$stamp"
$work=Join-Path ([IO.Path]::GetTempPath()) ("orion-l2-publish-"+[guid]::NewGuid().ToString('N'))
git fetch origin main
if ($LASTEXITCODE -ne 0) { throw 'git fetch failed' }
git worktree add -b $branch $work origin/main
if ($LASTEXITCODE -ne 0) { throw 'Cannot create independent publication worktree' }
$target=Join-Path $work $dest
New-Item -ItemType Directory -Path $target -Force | Out-Null
Get-ChildItem -LiteralPath $dest | Where-Object { $_.Name -ne 'evidence.zip' } | Copy-Item -Destination $target -Recurse
Push-Location $work
try {
 git add -- $dest
 if ($LASTEXITCODE -ne 0) { throw 'git add failed' }
 git commit -m "results: Q3 L2 supplement $Round shard $ShardIndex"
 if ($LASTEXITCODE -ne 0) { throw 'git commit failed' }
 git push -u origin $branch
 if ($LASTEXITCODE -ne 0) { throw 'git push failed' }
 gh pr create --repo yellkiin/model_competition --head $branch --base main --title "Q3 L2 supplement $Round shard $ShardIndex" --body "Q3-only supplemental plans and actual metrics over Trident #38. Q1/Q2 unchanged. Read report/report.json and PUBLICATION.json for scope, changed keys and pending same-plan pairs. Full evidence ZIP retained locally for manual transfer. No automatic merge."
 if ($LASTEXITCODE -ne 0) { throw 'PR creation failed; branch remains available.' }
} finally { Pop-Location }
Write-Output "Complete raw evidence is local: $dest\evidence.zip. It was not uploaded automatically."
