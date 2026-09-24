[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$RepositoryRoot,
    [string]$Branch='feat/a-orion-anytime-20260924',
    [string]$Worktree='', [switch]$Draft
)
$ErrorActionPreference='Stop'
$Repo=(Resolve-Path -LiteralPath $RepositoryRoot).Path
$Source=$PSScriptRoot
if (!(Get-Command git -ErrorAction SilentlyContinue)) { throw 'Git is required' }
if (!(Get-Command gh -ErrorAction SilentlyContinue)) { throw 'GitHub CLI is required for publishing only; install it locally and authenticate with gh auth login. Do not paste credentials into logs or prompts.' }
$Remote=(& git -C $Repo remote get-url origin).Trim()
if ($LASTEXITCODE -ne 0 -or $Remote -notmatch 'github\.com[:/]yellkiin/model_competition(?:\.git)?$') { throw "Unexpected origin; refusing to publish to $Remote" }
& gh auth status --hostname github.com
if ($LASTEXITCODE -ne 0) { throw 'No usable GitHub CLI authentication; local user must authenticate. No PR was created.' }
if (!$Worktree) { $Worktree=Join-Path (Split-Path $Repo -Parent) ('model_competition_orion_anytime_'+(Get-Date -Format 'yyyyMMdd_HHmmss')) }
if (Test-Path -LiteralPath $Worktree) { throw 'Worktree path already exists; select a new empty path. Existing work is never overwritten.' }
$PreviousSkip=$env:GIT_LFS_SKIP_SMUDGE
try {
    $env:GIT_LFS_SKIP_SMUDGE='1'
    & git -C $Repo fetch origin main
    if ($LASTEXITCODE -ne 0) { throw 'Fetch failed; no changes made to the active branch' }
    & git -C $Repo worktree add -b $Branch $Worktree origin/main
    if ($LASTEXITCODE -ne 0) { throw 'Worktree creation failed. Choose a unique branch name; do not force or reset an existing branch.' }
    $Target=Join-Path $Worktree 'research_a_orion_anytime'
    if (Test-Path -LiteralPath $Target) { throw 'Target directory already tracked/present. Review manually; do not overwrite other work.' }
    New-Item -ItemType Directory -Path $Target | Out-Null
    # Explicitly exclude results, input graphs, bytecode and all other AI directories.
    Get-ChildItem -LiteralPath $Source -File -Force | Where-Object {
        $_.Extension -in @('.py','.md','.ps1','.yml','.json') -or $_.Name -in @('.gitignore','.gitattributes')
    } | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $Target }
    & git -C $Worktree add -- research_a_orion_anytime
    if ($LASTEXITCODE -ne 0) { throw 'Staging failed' }
    $Changed=@(& git -C $Worktree diff --cached --name-only)
    if ($Changed.Count -eq 0 -or @($Changed | Where-Object {$_ -notlike 'research_a_orion_anytime/*'}).Count -gt 0) { throw 'Unexpected staged file set' }
    & git -C $Worktree diff --cached --check
    if ($LASTEXITCODE -ne 0) { throw 'Patch whitespace check failed' }
    & git -C $Worktree commit -m 'feat(a): add isolated ORION anytime scheduler and gated half-day campaign'
    if ($LASTEXITCODE -ne 0) { throw 'Commit failed; local agent should inspect git identity without changing global settings' }
    & git -C $Worktree push -u origin $Branch
    if ($LASTEXITCODE -ne 0) { throw 'Push failed; do not claim that a PR exists' }
    $args=@('pr','create','--repo','yellkiin/model_competition','--base','main','--head',$Branch,
            '--title','A ORION Anytime: staged/window refinement and bounded pilot-to-100 campaign',
            '--body-file',(Join-Path $Target 'PR_BODY.md'))
    if ($Draft) {$args+='--draft'}
    & gh @args
    if ($LASTEXITCODE -ne 0) { throw 'Branch pushed, PR creation failed. Inspect the real error; do not publish a guessed URL.' }
    Write-Host "Dedicated worktree retained: $Worktree"
} finally { $env:GIT_LFS_SKIP_SMUDGE=$PreviousSkip }
