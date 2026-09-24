[CmdletBinding()]
param(
  [ValidateSet('start','prepare','check')][string]$Action = 'start',
  [ValidateSet('codex','claude')][string]$Runtime = 'codex',
  [string[]]$Input,
  [string]$WorkspaceRoot,
  [switch]$Offline,
  [switch]$NoPersistUserEnvironment
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$TemplateRoot = $PSScriptRoot
$CatalogPath = Join-Path $TemplateRoot '华为杯_求解规范/环境/软件目录.json'
$Catalog = Get-Content -Raw -LiteralPath $CatalogPath | ConvertFrom-Json
if (-not [Environment]::Is64BitOperatingSystem -or [Environment]::OSVersion.Version.Major -lt 10) {
  throw '正式环境准备仅支持 Windows 10/11 x64。'
}

function Test-WorkflowPython([string]$Candidate) {
  if (-not $Candidate -or $Candidate -match '(?i)WindowsApps') { return $null }
  if (-not (Test-Path -LiteralPath $Candidate -PathType Leaf)) { return $null }
  $probe = 'import json,sys,struct,venv,ensurepip; print(json.dumps(dict(executable=sys.executable, version=list(sys.version_info[:3]), bits=struct.calcsize("P")*8)))'
  try {
    $raw = & $Candidate -I -c $probe 2>$null
    if ($LASTEXITCODE -ne 0) { return $null }
    $value = $raw | ConvertFrom-Json
    if ($value.bits -ne 64 -or $value.version[0] -ne 3 -or $value.version[1] -lt 10 -or $value.version[1] -ge 14) { return $null }
    return (Resolve-Path -LiteralPath $value.executable).Path
  } catch { return $null }
}

function Find-WorkflowPython {
  $candidates = [System.Collections.Generic.List[string]]::new()
  foreach ($command in Get-Command python.exe, python3.exe -All -ErrorAction SilentlyContinue) { $candidates.Add($command.Source) }
  if (Get-Command py.exe -ErrorAction SilentlyContinue) {
    foreach ($line in (& py.exe -0p 2>$null)) {
      if ($line -match '(?<path>[A-Za-z]:\\.*python(?:\.exe)?)\s*$') { $candidates.Add($Matches.path) }
    }
  }
  foreach ($base in @((Join-Path $env:LOCALAPPDATA 'Programs/Python'), (Join-Path $env:LOCALAPPDATA 'HuaweiCupWorkflow'))) {
    if (Test-Path -LiteralPath $base) {
      Get-ChildItem -LiteralPath $base -Filter python.exe -File -Recurse -ErrorAction SilentlyContinue | ForEach-Object { $candidates.Add($_.FullName) }
    }
  }
  foreach ($candidate in $candidates) { $valid = Test-WorkflowPython $candidate; if ($valid) { return $valid } }
  return $null
}

function Add-UserPath([string[]]$Entries) {
  $before = [Environment]::GetEnvironmentVariable('Path','User')
  if ($null -eq $before) { $before = '' }
  $parts = [System.Collections.Generic.List[string]]::new()
  $seen = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
  foreach ($item in ($before -split ';')) { if ($item.Trim() -and $seen.Add($item.Trim().Trim('"'))) { $parts.Add($item) } }
  foreach ($item in $Entries) { if ($seen.Add($item.Trim().Trim('"'))) { $parts.Add($item) } }
  $after = $parts -join ';'
  if ($after -ne $before) { [Environment]::SetEnvironmentVariable('Path',$after,'User') }
  $env:Path = (($Entries + ($env:Path -split ';')) | Select-Object -Unique) -join ';'
  return @{ before = $before; after = $after; changed = ($before -ne $after) }
}

function Install-WorkflowPython {
  if ($Offline) { throw '离线模式未发现兼容 Python，不能继续。' }
  $recordDir = Join-Path $env:LOCALAPPDATA 'HuaweiCupWorkflow/bootstrap'
  New-Item -ItemType Directory -Force -Path $recordDir | Out-Null
  $recordPath = Join-Path $recordDir ('python-' + [Guid]::NewGuid().ToString('N') + '.json')
  $events = [System.Collections.Generic.List[object]]::new()
  function Add-BootstrapEvent([hashtable]$Event) {
    $Event.time = [DateTimeOffset]::UtcNow.ToString('o')
    $events.Add([pscustomobject]$Event)
    $record = [ordered]@{ schema_version='1.0'; status='running'; events=$events }
    [IO.File]::WriteAllText($recordPath,($record | ConvertTo-Json -Depth 8),[Text.UTF8Encoding]::new($false))
  }
  $artifact = $Catalog.python.artifact
  $cache = Join-Path $env:LOCALAPPDATA 'HuaweiCupWorkflow/cache/downloads'
  New-Item -ItemType Directory -Force -Path $cache | Out-Null
  $installer = Join-Path $cache ($artifact.sha256.Substring(0,16) + '-' + $artifact.filename)
  $valid = (Test-Path -LiteralPath $installer -PathType Leaf) -and ((Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLower() -eq $artifact.sha256)
  if (-not $valid) {
    if (Test-Path -LiteralPath $installer) {
      Move-Item -LiteralPath $installer -Destination ($installer + '.rejected-' + [Guid]::NewGuid().ToString('N'))
      Add-BootstrapEvent @{action='cache_rejected'; reason='publisher_sha256_mismatch'}
    }
    $downloaded = $false
    foreach ($url in $artifact.urls) {
      foreach ($attempt in 1..2) {
        $part = $installer + '.part-' + [Guid]::NewGuid().ToString('N')
        try {
          Invoke-WebRequest -Uri $url -OutFile $part -MaximumRedirection 5 -TimeoutSec 90
          if ((Get-FileHash -LiteralPath $part -Algorithm SHA256).Hash.ToLower() -ne $artifact.sha256) { throw '发布方 SHA-256 校验失败' }
          $bytes = [IO.File]::ReadAllBytes($part); if ($bytes.Length -lt 2 -or $bytes[0] -ne 0x4d -or $bytes[1] -ne 0x5a) { throw '下载内容不是 PE 安装程序' }
          Move-Item -LiteralPath $part -Destination $installer
          Add-BootstrapEvent @{action='download'; source=$url; attempt=$attempt; status='satisfied'; sha256=$artifact.sha256}
          $downloaded = $true; break
        } catch {
          if (Test-Path -LiteralPath $part) { Move-Item -LiteralPath $part -Destination ($part + '.rejected') }
          Add-BootstrapEvent @{action='download'; source=$url; attempt=$attempt; status='failed'; error=$_.Exception.Message}
        }
      }
      if ($downloaded) { break }
    }
    if (-not $downloaded) { throw 'Python 安装包的可信镜像和官方源均失败。' }
  } else { Add-BootstrapEvent @{action='cache_reuse'; status='satisfied'; sha256=$artifact.sha256} }
  $target = Join-Path $env:LOCALAPPDATA ('HuaweiCupWorkflow/python-' + $Catalog.python.new_version)
  $log = Join-Path $cache ('python-install-' + [Guid]::NewGuid().ToString('N') + '.log')
  $installArgs = '/quiet InstallAllUsers=0 TargetDir="' + $target + '" PrependPath=0 Include_pip=1 Include_launcher=0 Include_test=0 Shortcuts=0 /log "' + $log + '"'
  $process = Start-Process -FilePath $installer -ArgumentList $installArgs -Wait -PassThru -WindowStyle Hidden
  if ($process.ExitCode -ne 0) { throw "Python 安装失败，退出码 $($process.ExitCode)，日志：$log" }
  $python = Test-WorkflowPython (Join-Path $target 'python.exe')
  if (-not $python) { throw 'Python 安装完成但功能验证失败。' }
  if (-not $NoPersistUserEnvironment) { Add-UserPath @($target,(Join-Path $target 'Scripts')) | Out-Null }
  Add-BootstrapEvent @{action='python_install'; status='satisfied'; version=$Catalog.python.new_version; target=$target; installer_log=$log}
  $record = [ordered]@{ schema_version='1.0'; status='satisfied'; events=$events }
  [IO.File]::WriteAllText($recordPath,($record | ConvertTo-Json -Depth 8),[Text.UTF8Encoding]::new($false))
  $env:Path = ($target,(Join-Path $target 'Scripts'),$env:Path) -join ';'
  return $python
}

$Python = Find-WorkflowPython
if (-not $Python) {
  if ($Action -eq 'check') { throw '未发现兼容 Python；只读 check 不会安装软件。请运行 Start-HuaweiCup.ps1 -Action start。' }
  $Python = Install-WorkflowPython
}
$Workshop = Join-Path $TemplateRoot '华为杯_求解规范/tools/workshop.py'
if ($Action -eq 'start') {
  $arguments = @('-B',$Workshop,'start','--template-root',$TemplateRoot,'--runtime',$Runtime)
  foreach ($item in $Input) { $arguments += @('--input',$item) }
  if ($Offline) { $arguments += '--offline' }
  if ($NoPersistUserEnvironment) { $arguments += '--no-persist-user-environment' }
} else {
  if (-not $WorkspaceRoot) { throw "Action=$Action 需要 -WorkspaceRoot 明确指定工作区。" }
  $arguments = @('-B',$Workshop,($(if ($Action -eq 'prepare') {'env'} else {'check'})),'--workspace-root',$WorkspaceRoot,'--runtime',$Runtime)
  if ($Action -eq 'prepare') {
    $arguments += @('prepare','--base-python',$Python)
    if ($Offline) { $arguments += '--offline' }
    if ($NoPersistUserEnvironment) { $arguments += '--no-persist-user-environment' }
  }
}
& $Python @arguments
exit $LASTEXITCODE
