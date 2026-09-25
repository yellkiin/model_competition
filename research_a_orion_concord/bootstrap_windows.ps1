param([string]$WorkRoot='D:\orion_concord', [string]$Revision='feat/orion-concord-graph600-20260925')
$ErrorActionPreference='Stop'
$repo=Join-Path $WorkRoot 'repo'
if (Test-Path $repo) { throw "Use an empty WorkRoot or the existing prepared checkout; this script does not switch a running workspace." }
New-Item -ItemType Directory -Force -Path $WorkRoot | Out-Null
$env:GIT_LFS_SKIP_SMUDGE='1'
git clone --depth 1 --filter=blob:none --no-checkout --branch $Revision https://github.com/yellkiin/model_competition.git $repo
if ($LASTEXITCODE) { throw 'Git clone failed; use the existing authorized Git/gh connection.' }
git -C $repo sparse-checkout init --cone
git -C $repo sparse-checkout set research_a_orion_concord research_a_orion_anytime research_a_orion_track_structure research_a_orion_track_memory research_a_orion_track_anytime research_a_orion_review_3pc '题目/A题' '调研/A题_文献库'
git -C $repo checkout
if ($LASTEXITCODE) { throw 'Checkout did not complete.' }
Write-Output "Prepared code and references: $repo"
