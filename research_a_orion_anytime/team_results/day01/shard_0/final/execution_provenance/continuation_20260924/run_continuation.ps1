[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$RunRoot,[Parameter(Mandatory=$true)][string]$SwitchRecord)
$ErrorActionPreference='Stop'
$Repo='D:\桌面\model_competition_orion_anytime'
$Source=Join-Path $Repo 'research_a_orion_anytime\runs\team_day01_shard0\auto'
$Python='D:\python\python.exe'
$Script=Join-Path $PSScriptRoot 'resume_day01.py'
$Auto=Join-Path $RunRoot 'auto'
$MainStop=[DateTimeOffset]::Parse('2026-09-24T16:43:48.3137853+00:00')
$TeamStop=[DateTimeOffset]::Parse('2026-09-24T17:43:48.3137853+00:00')
$Stdout=Join-Path $RunRoot 'launcher_stdout.txt'
$Stderr=Join-Path $RunRoot 'launcher_stderr.txt'
$env:PYTHONUTF8='1';$env:PYTHONHASHSEED='0'
$Arguments=@('-u',$Script,'--source',$Source,'--out',$Auto,'--switch-record',$SwitchRecord,'--workers','2')
$Quoted=@($Arguments|ForEach-Object {if($_.Contains('"')){throw 'Invalid quotation mark in argument'};'"'+$_+'"'})
$Child=Start-Process -FilePath $Python -ArgumentList $Quoted -WorkingDirectory $Repo -WindowStyle Hidden -PassThru -RedirectStandardOutput $Stdout -RedirectStandardError $Stderr
$Status=[ordered]@{status='running';pid=$Child.Id;started_utc=[DateTimeOffset]::UtcNow.ToString('o');team_deadline_utc=$TeamStop.ToString('o');main_deadline_utc=$MainStop.ToString('o');shards=2;shard_index=0;workers=2;stage='continuation';out=$Auto;stdout=$Stdout;stderr=$Stderr;source=$Source;switch_record=$SwitchRecord}
$Status|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $RunRoot 'team_status.json') -Encoding UTF8
$Expired=$false
try {
 while(!$Child.WaitForExit(1000)) {
  if([DateTimeOffset]::UtcNow -ge $MainStop){$Expired=$true;& taskkill.exe /PID $Child.Id /T /F | Out-Null;$Child.WaitForExit();break}
 }
} finally {
 if(!$Child.HasExited){& taskkill.exe /PID $Child.Id /T /F | Out-Null;$Child.WaitForExit()}
}
$Child.Refresh()
$Status.status=if($Expired){'absolute_deadline_reached'}elseif($Child.ExitCode -eq 0){'process_completed'}else{'process_failed'}
$Status['exit_code']=$Child.ExitCode;$Status['finished_utc']=[DateTimeOffset]::UtcNow.ToString('o')
$Status|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $RunRoot 'team_status.json') -Encoding UTF8
