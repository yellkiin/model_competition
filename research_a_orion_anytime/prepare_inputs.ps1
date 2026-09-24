param([string[]]$Cases = @('001','002','044'), [string]$Remote = 'origin')
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
# Explicit opt-in only. Never download another problem or all LFS objects.
$include = @()
foreach ($c in $Cases) {
    $name = ('case_{0:D3}.json' -f [int]$c)
    $include += ('题目/A题/通用神经网络处理器下的多核调度问题  附件/data/' + $name)
}
git lfs pull $Remote "--include=$($include -join ',')" '--exclude='
if ($LASTEXITCODE -ne 0) { throw 'Selective A LFS retrieval failed. Local agent should locate the existing A archive and extract ONLY these cases without overwriting source/config/evaluator files.' }
