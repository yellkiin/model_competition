[CmdletBinding()]
param(
 [string]$Python='D:\python\python.exe', [string]$Official='',
 [string]$Out='research_a_orion_anytime\runs\research_day',
 [ValidateSet(1,2)][int]$Workers=2, [string]$Archive='', [switch]$RestoreInputs,
 [int]$Shards=1, [int]$ShardIndex=0, [switch]$SkipMechanisms,
 [double]$Seconds=30, [double]$LargeSeconds=180, [int]$Calls=24, [int]$RefineSeconds=30, [string]$DeadlineUtc=''
)
$ErrorActionPreference='Stop'
$Repo=Split-Path -Parent $PSScriptRoot
Push-Location $Repo
try {
 $Root=[IO.Path]::GetFullPath($Out)
 New-Item -ItemType Directory -Path $Root -Force | Out-Null
 $Clock=Join-Path $Root 'research_day_clock.json'
 if (Test-Path -LiteralPath $Clock) {
   $Saved=Get-Content -LiteralPath $Clock -Raw | ConvertFrom-Json
   $Stop=[DateTimeOffset]::Parse($Saved.stop_utc)
   if ($DeadlineUtc -and [DateTimeOffset]::Parse($DeadlineUtc) -ne $Stop) {throw 'Persisted team deadline differs. Do not reset a running research day.'}
 } else {
   $Stop=[DateTimeOffset]::UtcNow.AddHours(12)
   if ($DeadlineUtc) { $TeamStop=[DateTimeOffset]::Parse($DeadlineUtc); if ($TeamStop -lt $Stop) {$Stop=$TeamStop} }
   @{start_utc=[DateTimeOffset]::UtcNow.ToString('o');stop_utc=$Stop.ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath $Clock -Encoding UTF8
 }
 $Common=@{Python=$Python;Official=$Official;Workers=$Workers;Archive=$Archive;RestoreInputs=$RestoreInputs;Shards=$Shards;ShardIndex=$ShardIndex;Seconds=$Seconds;LargeSeconds=$LargeSeconds;Calls=$Calls;RefineSeconds=$RefineSeconds}
 $Left=($Stop-[DateTimeOffset]::UtcNow).TotalHours
 if ($Left -le 0) {throw 'The persisted research-day deadline has expired. It is not silently reset.'}
 $Auto=Join-Path $Root 'auto'
 # A repeated invocation must preserve the original --hours policy. The inner
 # watchdog consults its own persisted absolute deadline on resume.
 $AutoHours=11.0
 if (!(Test-Path -LiteralPath (Join-Path $Auto 'campaign.json'))) {$AutoHours=[Math]::Min(11.0,$Left-0.02)}
 else {$AutoHours=(Get-Content -LiteralPath (Join-Path $Auto 'campaign.json') -Raw | ConvertFrom-Json).identity.args.hours}
 & (Join-Path $PSScriptRoot 'experiments.ps1') @Common -Stage auto -Out $Auto -Hours $AutoHours
 if (!$SkipMechanisms -and $Shards -eq 1) {
   foreach ($Stage in @('mechanisms','sensitivity')) {
     $Left=($Stop-[DateTimeOffset]::UtcNow).TotalHours
     if ($Left -lt 0.05) {Write-Warning "No time left for $Stage; do not claim this optional experiment completed.";break}
     $PhaseOut=Join-Path $Root $Stage
     $PhaseHours=[Math]::Min(0.4,$Left-0.02)
     if (Test-Path -LiteralPath (Join-Path $PhaseOut 'campaign.json')) {$PhaseHours=(Get-Content -LiteralPath (Join-Path $PhaseOut 'campaign.json') -Raw | ConvertFrom-Json).identity.args.hours}
     & (Join-Path $PSScriptRoot 'experiments.ps1') @Common -Stage $Stage -Out $PhaseOut -Hours $PhaseHours -Index (Join-Path $Auto 'final_index.json') -ReoptimizeGrid
   }
 }
 Write-Host "Research-day root: $Root"
 Write-Host 'Check formal_complete and all phase status files before describing the experiment as complete.'
} finally {Pop-Location}
