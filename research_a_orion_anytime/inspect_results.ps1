[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$Root)
$ErrorActionPreference='Stop'
$Rows=@(Get-ChildItem -LiteralPath $Root -Recurse -Filter summary.json -File | ForEach-Object {
 try {
  $s=Get-Content -LiteralPath $_.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
  [pscustomobject]@{case=$s.case;q=$s.q;n=$s.n;status=$s.status;T=$s.makespan;calls=$s.evaluations;
    wall=$s.process_seconds;first_valid=$s.first_valid_seconds;ratio_upper=$s.certificate.approximation_ratio_upper;
    stopped=$s.stopped;path=$_.DirectoryName}
 } catch { Write-Warning "Unreadable summary: $($_.FullName)" }
})
$Rows | Group-Object status | Select-Object Name,Count | Format-Table -AutoSize
$Rows | Where-Object {$_.status -ne 'ok'} | Format-Table case,q,n,status,path -AutoSize
Write-Host 'Largest certified ratio U/L (upper bounds, not proof of that much improvable performance):'
$Rows | Where-Object {$_.status -eq 'ok'} | Sort-Object ratio_upper -Descending | Select-Object -First 12 | Format-Table case,q,n,T,wall,ratio_upper,stopped -AutoSize
Write-Host 'Read progress.json and stderr.txt for the corresponding job. Do not modify official evaluators or delete failed records.'
