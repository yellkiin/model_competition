param([switch]$Full)
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
py -3.13 -m venv "$Root/research_fd/.venv"
if ($LASTEXITCODE -ne 0) { throw 'Python 3.13 venv creation failed; choose an installed 3.11-3.13 interpreter.' }
$Py = "$Root/research_fd/.venv/Scripts/python.exe"
& $Py -m pip install --upgrade pip
& $Py -m pip install -r "$Root/research_fd/requirements_d.txt"
if ($LASTEXITCODE -ne 0) { throw 'Core dependency installation failed.' }
if ($Full) {
 & $Py -m pip install -r "$Root/research_fd/requirements_d_optional.txt"
 if ($LASTEXITCODE -ne 0) { throw 'Optional dependency installation failed.' }
}
Write-Output "Python: $Py"
