param(
    [Parameter(Mandatory=$true)][string]$Url,
    [Parameter(Mandatory=$true)][string]$Key,
    [ValidateSet('html_meta','field_quotes','csl_json')][string]$Format='html_meta'
)
$ErrorActionPreference='Stop'
$paperRoot=(Resolve-Path (Join-Path $PSScriptRoot '../论文')).Path
$folder=Join-Path $paperRoot ('参考来源/'+$Key)
if (Test-Path -LiteralPath $folder) { throw "来源快照已存在：$folder" }
New-Item -ItemType Directory -Path $folder | Out-Null
$extension=if ($Format -eq 'csl_json') {'.json'} elseif ($Url -match '\.pdf(?:\?|$)') {'.pdf'} else {'.html'}
$source=Join-Path $folder ('source'+$extension)
try {
    $response=Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 60 -OutFile $source -PassThru -Headers @{'User-Agent'='GMCM-Reference-Collector/1.0'}
    if ($response.StatusCode -ne 200 -or (Get-Item -LiteralPath $source).Length -eq 0) { throw "来源获取失败：$Url" }
    $rel='参考来源/'+$Key+'/source'+$extension
    $hash=(Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
    $receipt=[ordered]@{
      schema_version='1.0'; requested_url=$Url; final_url=$response.BaseResponse.RequestMessage.RequestUri.AbsoluteUri;
      status=[int]$response.StatusCode; retrieved_utc=(Get-Date).ToUniversalTime().ToString('o');
      content_type=($response.Headers['Content-Type'] -split ';')[0]; sha256=$hash; capture_path=$rel
    }
    $receiptPath=Join-Path $folder 'receipt.json'
    $receipt | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $receiptPath -Encoding utf8
    $receiptHash=(Get-FileHash -LiteralPath $receiptPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $draft=[ordered]@{
      url=$Url;authority='';authority_reason='';capture_path=$rel;capture_sha256=$hash;
      receipt_path=('参考来源/'+$Key+'/receipt.json');receipt_sha256=$receiptHash;format=$Format;
      review=@{reviewed=$false;tool_ref='';observation=''}
    }
    [ordered]@{source_draft=$draft;status='REVIEW_REQUIRED'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $folder 'draft.json') -Encoding utf8
    Write-Output "$Key $($response.StatusCode) $((Get-Item -LiteralPath $source).Length) $($response.BaseResponse.RequestMessage.RequestUri.AbsoluteUri)"
} catch {
    Remove-Item -LiteralPath $folder -Force -Recurse
    throw
}
