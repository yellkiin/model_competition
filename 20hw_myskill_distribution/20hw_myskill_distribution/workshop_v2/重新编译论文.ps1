# 在本工作区编译现有论文；不运行求解、哈希、环境冒烟或重新创建工作区。
$ErrorActionPreference = 'Stop'
$workspaceRoot = $PSScriptRoot
$projectRoot = [IO.Path]::GetFullPath((Join-Path $workspaceRoot '..\..'))
$texRoot = Join-Path $projectRoot '.orion_paper_cache\tex_runtime\TinyTeX\TinyTeX'
$paperAlias = Join-Path $workspaceRoot 'paper_build'
$paperDirectory = Join-Path $workspaceRoot '论文'
if (-not (Test-Path -LiteralPath $paperAlias)) {
    New-Item -ItemType Junction -Path $paperAlias -Target $paperDirectory | Out-Null
}
if (-not (Test-Path -LiteralPath (Join-Path $texRoot 'bin\windows\xelatex.exe'))) {
    throw '当前项目的 TinyTeX 尚未就绪。请使用已有兼容 XeLaTeX 编译论文/论文.tex。'
}
$freeLetters = @('R','S','U','V','W','X','Y','Z' | Where-Object {
    -not [IO.Directory]::Exists("${_}:\") -and -not (Get-PSDrive -Name $_ -ErrorAction SilentlyContinue)
})
if ($freeLetters.Count -lt 2) { throw '需要两个空闲临时盘符以兼容中文路径。' }
$workDrive = $freeLetters[0] + ':'
$texDrive = $freeLetters[1] + ':'
$previousLocation = Get-Location
$savedEnvironment = @{}
foreach ($name in @('PATH','PYTHONUTF8','XDG_CONFIG_HOME','TEXMFHOME','TEXMFOUTPUT','TEXMF_OUTPUT_DIRECTORY')) {
    $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}
try {
    & subst.exe $workDrive $workspaceRoot
    if ($LASTEXITCODE) { throw '无法建立工作区临时路径。' }
    & subst.exe $texDrive $texRoot
    if ($LASTEXITCODE) { throw '无法建立排版环境临时路径。' }
    $buildPath = "$workDrive\paper_build"
    $texBin = "$texDrive\bin\windows"
    $pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
    $pythonBin = if ($pythonCommand) { Split-Path $pythonCommand.Source } else { '' }
    $env:PATH = "$pythonBin;$texBin;$env:PATH"
    $env:PYTHONUTF8 = '1'
    $env:XDG_CONFIG_HOME = "$buildPath/config"
    $env:TEXMFHOME = "$buildPath/texmf-home"
    $env:TEXMFOUTPUT = "$buildPath/"
    $env:TEXMF_OUTPUT_DIRECTORY = "$buildPath/"
    Set-Location -LiteralPath $buildPath
    Copy-Item -LiteralPath '参考文献.bib' -Destination 'references.bib' -Force
    & "$texBin\xelatex.exe" -shell-escape -interaction=nonstopmode -halt-on-error -jobname=paper '论文.tex' *> compile.log
    if ($LASTEXITCODE) { throw '首次编译失败，见论文/compile.log。' }
    & "$texBin\bibtex.exe" 'paper' *> bibtex_compile.log
    if ($LASTEXITCODE) { throw '参考文献编译失败，见论文/bibtex_compile.log。' }
    1..2 | ForEach-Object {
        & "$texBin\xelatex.exe" -shell-escape -interaction=nonstopmode -halt-on-error -jobname=paper '论文.tex' *> compile.log
        if ($LASTEXITCODE) { throw '编译失败，见论文/compile.log。' }
    }
    foreach ($extension in @('aux','toc','bbl','log','gmcmevaluation','gmcmlayout','gmcmprose')) {
        Copy-Item -LiteralPath ('paper.' + $extension) -Destination ('论文.' + $extension) -Force
    }
    Copy-Item -LiteralPath 'paper.pdf' -Destination '论文_PR52复审版_20260926.pdf' -Force
    Write-Output (Join-Path $paperDirectory '论文_PR52复审版_20260926.pdf')
}
finally {
    Set-Location -LiteralPath $previousLocation.Path
    foreach ($name in $savedEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($name, $savedEnvironment[$name], 'Process')
    }
    & subst.exe $workDrive /d
    & subst.exe $texDrive /d
}
