param(
 [ValidateRange(0,2)][int]$Shard=0,
 [string]$Python='D:\python\python.exe',
 [string]$WorkRoot='D:\orion_concord',
 [string]$Catalog='',
 [ValidateSet('gate','full','targeted')][string]$Phase='gate',
 [string[]]$Cases=@(), [string[]]$Keys=@(),
 [ValidateRange(1,600)][int]$Seconds=600,
 [int]$WallSeconds=43200, [string]$Workers='auto',
 [switch]$Resume, [switch]$NoDiagnostics, [switch]$WithStudies
)
$ErrorActionPreference='Stop'
if (!(Test-Path -LiteralPath $Python)) { throw "Select an existing CPU-only Python 3.12.x with -Python." }
$version=& $Python -c 'import sys; print(str(sys.version_info.major)+"."+str(sys.version_info.minor))'
if ($version.Trim() -ne '3.12') { throw "Select existing Python 3.12.x; current is $version. Keep other running environments intact." }
$repo=Split-Path $PSScriptRoot -Parent
if (!$Catalog) { $Catalog=Join-Path $WorkRoot "inputs\shard_$Shard\seeds\catalog.json" }
$out=Join-Path $WorkRoot "runs\round01\shard_$Shard"
$env:PYTHONUTF8='1';$env:OMP_NUM_THREADS='1';$env:OPENBLAS_NUM_THREADS='1';$env:MKL_NUM_THREADS='1'
$argsList=@('-u','-m','research_a_orion_concord.run','--manifest',(Join-Path $PSScriptRoot 'SHARDS.json'),
 '--shard',"$Shard",'--catalog',$Catalog,'--out',$out,'--seconds',"$Seconds",'--wall-seconds',"$WallSeconds",'--workers',$Workers,'--phase',$Phase)
if ($Cases.Count) { $argsList+=@('--cases')+$Cases }
if ($Keys.Count) { $argsList+=@('--keys')+$Keys }
if ($Resume) { $argsList+='--resume' }
if ($NoDiagnostics) { $argsList+='--no-diagnostics' }
if ($WithStudies) { $argsList+='--with-studies' }
Push-Location $repo
try { & $Python @argsList; if ($LASTEXITCODE -ne 0) { throw "Run ended with code $LASTEXITCODE; retain the recorded partial result." } }
finally { Pop-Location }
