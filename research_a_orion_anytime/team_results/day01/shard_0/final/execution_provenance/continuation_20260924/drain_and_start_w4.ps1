$ErrorActionPreference='Stop'
$Repo='D:\桌面\model_competition_orion_anytime'
$Source=Join-Path $Repo 'research_a_orion_anytime\runs\team_day01_shard0_w2'
$Next=Join-Path $Repo 'research_a_orion_anytime\runs\team_day01_shard0_w4'
if(Test-Path -LiteralPath $Next){throw 'Four-worker output already exists. Do not duplicate.'}
$Status=Get-Content -LiteralPath (Join-Path $Source 'team_status.json') -Raw -Encoding UTF8|ConvertFrom-Json
$Parent=Get-Process -Id $Status.pid
$Info=Get-CimInstance Win32_Process -Filter "ProcessId=$($Status.pid)"
if($Status.pid -ne 94880 -or !$Info.CommandLine.Contains('resume_day01.py')){throw 'Unexpected active continuation process'}
if(Test-Path -LiteralPath (Join-Path $Status.out 'pairs')){throw 'Current refinement phase already ended'}
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class OrionDrainNative {
 [DllImport("ntdll.dll")] public static extern int NtSuspendProcess(IntPtr handle);
 [DllImport("ntdll.dll")] public static extern int NtResumeProcess(IntPtr handle);
}
'@
$Suspended=$false;$Stopped=$false
try {
 $Code=[OrionDrainNative]::NtSuspendProcess($Parent.Handle)
 if($Code -ne 0){throw "Cannot pause job dispatch: $Code"}
 $Suspended=$true
 $Children=@(Get-CimInstance Win32_Process -Filter "Name='python.exe'"|Where-Object {$_.ParentProcessId -eq $Status.pid})
 $Pending=@(Get-ChildItem -LiteralPath (Join-Path $Status.out 'refinement') -Recurse -Filter request.json -File|Where-Object {!(Test-Path -LiteralPath (Join-Path $_.DirectoryName 'summary.json'))})
 if($Pending.Count -ne $Children.Count -or $Children.Count -gt 2){throw 'Not at a clean two-job dispatch boundary; resume original dispatcher'}
 New-Item -ItemType Directory -Path $Next|Out-Null
 $Jobs=@(foreach($Child in $Children){
  $Match=@($Pending|Where-Object {$Child.CommandLine.Contains($_.FullName)})
  if($Match.Count -ne 1){throw 'Cannot identify solver request'}
  $Request=Get-Content -LiteralPath $Match[0].FullName -Raw -Encoding UTF8|ConvertFrom-Json
  $Proc=Get-Process -Id $Child.ProcessId -ErrorAction SilentlyContinue
  $Started=if($Proc){[DateTimeOffset]$Proc.StartTime}else{[DateTimeOffset]$Child.CreationDate}
  [pscustomobject]@{pid=$Child.ProcessId;folder=$Match[0].DirectoryName;started=$Started;cap=[double]$Request.seconds;proc=$Proc;done=$false;hard_timeout=$false;process_seconds=0.0;exit_code=$null}
 })
 Write-Output "Dispatcher paused; allowing $($Jobs.Count) current solvers to finish under original caps."
 while(@($Jobs|Where-Object {!$_.done}).Count -gt 0){
  foreach($Job in $Jobs|Where-Object {!$_.done}){
   $Job.proc.Refresh()
   if(!$Job.proc.HasExited -and ([DateTimeOffset]::UtcNow-$Job.started).TotalSeconds -ge $Job.cap){
    $Job.hard_timeout=$true;Stop-Process -Id $Job.pid -Force;$Job.proc.WaitForExit()
   }
   if($Job.proc.HasExited){$Job.done=$true;$Job.process_seconds=([DateTimeOffset]::UtcNow-$Job.started).TotalSeconds;$Job.exit_code=$Job.proc.ExitCode}
  }
  if(@($Jobs|Where-Object {!$_.done}).Count -gt 0){Start-Sleep -Milliseconds 25}
 }
 $Record=[ordered]@{stop_epoch=[DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()/1000.0;stop_utc=[DateTimeOffset]::UtcNow.ToString('o');reason='User clarified: current solver jobs finish normally, then remaining refinement uses four workers';old_workers=2;new_workers=4;source_root=$Status.out;jobs=@($Jobs|Select-Object pid,folder,cap,hard_timeout,process_seconds,exit_code)}
 $RecordPath=Join-Path $Next 'worker_switch.json'
 $Record|ConvertTo-Json -Depth 5|Set-Content -LiteralPath $RecordPath -Encoding UTF8
 & 'D:\python\python.exe' (Join-Path $PSScriptRoot 'finalize_drained_jobs.py') $RecordPath
 if($LASTEXITCODE -ne 0){throw 'Drain finalization failed'}
 Stop-Process -Id $Parent.Id -Force;$Parent.WaitForExit();$Stopped=$true
 Copy-Item -LiteralPath (Join-Path $Source 'research_day_clock.json') -Destination (Join-Path $Next 'research_day_clock.json')
 $ArgsList=@('-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $PSScriptRoot 'run_continuation_w4.ps1'),'-RunRoot',$Next,'-SwitchRecord',$RecordPath)
 $Quoted=@($ArgsList|ForEach-Object {'"'+$_+'"'})
 $New=Start-Process -FilePath 'powershell.exe' -ArgumentList $Quoted -WorkingDirectory $Repo -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $Next 'supervisor_stdout.txt') -RedirectStandardError (Join-Path $Next 'supervisor_stderr.txt')
 Write-Output "Four-worker supervisor started: $($New.Id)"
} finally {
 if($Suspended -and !$Stopped -and !$Parent.HasExited){[OrionDrainNative]::NtResumeProcess($Parent.Handle)|Out-Null}
}
