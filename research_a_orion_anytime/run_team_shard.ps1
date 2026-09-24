[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidateSet(0,1)][int]$ShardIndex,
    [Parameter(Mandatory=$true)][string]$Official,
    [string]$Python='D:\python\python.exe',
    [ValidateSet(1,2)][int]$Workers=1,
    [string]$Out='',
    [string]$Gate='',
    [string]$DeadlineUtc='2026-09-24T17:43:48.3137853+00:00'
)
$ErrorActionPreference='Stop'
$Repo=Split-Path -Parent $PSScriptRoot
$Stop=[DateTimeOffset]::Parse($DeadlineUtc)
$MainStop=$Stop.AddHours(-1)
if ([DateTimeOffset]::UtcNow -ge $MainStop) {throw 'The shared main-computation deadline has expired. Do not reset it.'}
if (!$Out) {$Out="research_a_orion_anytime\runs\team_day01_shard$ShardIndex"}
if (![IO.Path]::IsPathRooted($Out)) {$Out=Join-Path $Repo $Out}
$Root=[IO.Path]::GetFullPath($Out)
$Allowed=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'runs'))+[IO.Path]::DirectorySeparatorChar
if (!$Root.StartsWith($Allowed,[StringComparison]::OrdinalIgnoreCase)) {throw 'Output must be a separate directory under research_a_orion_anytime/runs.'}
$Official=(Resolve-Path -LiteralPath $Official).Path
if ($Gate) {$Gate=(Resolve-Path -LiteralPath $Gate).Path}
New-Item -ItemType Directory -Path $Root -Force | Out-Null
$ClockFile=Join-Path $Root 'research_day_clock.json'
if (Test-Path -LiteralPath $ClockFile) {
    $Saved=Get-Content -LiteralPath $ClockFile -Raw -Encoding UTF8 | ConvertFrom-Json
    if ([DateTimeOffset]::Parse($Saved.stop_utc) -ne $Stop -or $Saved.shard_index -ne $ShardIndex -or $Saved.shards -ne 2) {throw 'Saved team deadline or shard assignment differs. Do not overwrite this run.'}
} else {
    @{start_utc=[DateTimeOffset]::UtcNow.ToString('o');stop_utc=$Stop.ToString('o');main_stop_utc=$MainStop.ToString('o');shards=2;shard_index=$ShardIndex} | ConvertTo-Json | Set-Content -LiteralPath $ClockFile -Encoding UTF8
}
$CampaignRoot=Join-Path $Root 'auto'
$Manifest=Join-Path $CampaignRoot 'campaign.json'
$Hours=($MainStop-[DateTimeOffset]::UtcNow).TotalHours-0.02
if (Test-Path -LiteralPath $Manifest) {$Hours=(Get-Content -LiteralPath $Manifest -Raw -Encoding UTF8 | ConvertFrom-Json).identity.args.hours}
if ($Hours -le 0 -or $Hours -gt 12) {throw 'Invalid remaining campaign time.'}
$Stage=if ($Gate) {'formal'} else {'auto'}
$Stamp=[DateTimeOffset]::UtcNow.ToString('yyyyMMdd_HHmmss')
$Stdout=Join-Path $Root "launcher_stdout_$Stamp.txt"
$Stderr=Join-Path $Root "launcher_stderr_$Stamp.txt"
$ArgsList=@('-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $PSScriptRoot 'experiments.ps1'),
    '-Stage',$Stage,'-Python',$Python,'-Official',$Official,'-Out',$CampaignRoot,
    '-Workers',[string]$Workers,'-Hours',$Hours.ToString('R',[Globalization.CultureInfo]::InvariantCulture),
    '-Shards','2','-ShardIndex',[string]$ShardIndex)
if ($Gate) {$ArgsList+=@('-Gate',$Gate)}
$QuotedArgs=@($ArgsList | ForEach-Object {if ($_.Contains('"')) {throw 'A command argument contains a quotation mark.'}; '"'+$_+'"'})
$Child=Start-Process -FilePath 'powershell.exe' -ArgumentList $QuotedArgs -WorkingDirectory $Repo -WindowStyle Hidden -PassThru -RedirectStandardOutput $Stdout -RedirectStandardError $Stderr
$Status=[ordered]@{status='running';pid=$Child.Id;started_utc=[DateTimeOffset]::UtcNow.ToString('o');team_deadline_utc=$Stop.ToString('o');main_deadline_utc=$MainStop.ToString('o');shards=2;shard_index=$ShardIndex;stage=$Stage;out=$CampaignRoot;stdout=$Stdout;stderr=$Stderr;gate=$Gate}
$Status | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Root 'team_status.json') -Encoding UTF8
Write-Host "Started shard $ShardIndex/2, PID $($Child.Id). Main deadline: $($MainStop.ToString('o'))"
Write-Host "stdout: $Stdout"
Write-Host "stderr: $Stderr"
$Expired=$false
try {
    while (!$Child.WaitForExit(1000)) {
        if ([DateTimeOffset]::UtcNow -ge $MainStop) {
            $Expired=$true
            & taskkill.exe /PID $Child.Id /T /F | Out-Null
            $Child.WaitForExit()
            break
        }
    }
} finally {
    if (!$Child.HasExited) {& taskkill.exe /PID $Child.Id /T /F | Out-Null; $Child.WaitForExit()}
}
$Child.Refresh()
$Status.status=if ($Expired) {'absolute_deadline_reached'} elseif ($Child.ExitCode -eq 0) {'process_completed'} else {'process_failed'}
$Status['exit_code']=$Child.ExitCode
$Status['finished_utc']=[DateTimeOffset]::UtcNow.ToString('o')
$Status | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Root 'team_status.json') -Encoding UTF8
Write-Host "Shard process ended: $($Status.status), exit=$($Child.ExitCode). Read formal_status.json and final_report; process exit alone is not complete coverage."
if ($Expired) {exit 124}
exit $Child.ExitCode