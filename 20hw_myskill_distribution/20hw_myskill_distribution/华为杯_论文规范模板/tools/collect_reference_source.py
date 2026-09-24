"""Capture a reference's source over HTTP; leave source/relevance reviews blank."""
from __future__ import annotations

# Shared execution is explicit; direct legacy/maintenance CLIs must declare mode.
if __name__ == "__main__":
    import sys as _workflow_sys
    _workflow_sys.dont_write_bytecode = True
    from pathlib import Path as _WorkflowPath
    _workflow_sys.path.insert(0, str(_WorkflowPath(__file__).resolve().parents[2] / "华为杯_求解规范/tools"))
    from workspace_cli import require_cli_mode
    require_cli_mode(__file__)

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.request import Request, urlopen

from reference_evidence import inside, sha, source_metadata


def collect(paper_root, url, output, fmt='html_meta'):
    root = Path(paper_root).resolve()
    folder = inside(root, str(output))
    if folder.exists():
        raise ValueError('保留已有来源快照；请使用新的输出目录')
    headers = {'User-Agent':'GMCM-Reference-Collector/1.0'}
    if fmt == 'csl_json':
        headers['Accept'] = 'application/vnd.citationstyles.csl+json'
    with urlopen(Request(url,headers=headers), timeout=45) as response:
        data = response.read()
        status = response.status
        final_url = response.url
        mime = response.headers.get_content_type()
    if status != 200 or not data:
        raise ValueError('来源未成功获取：'+url)
    folder.mkdir(parents=True)
    ext = '.pdf' if mime=='application/pdf' else '.json' if fmt=='csl_json' else '.html' if 'html' in mime else '.txt'
    path = folder/('source'+ext)
    path.write_bytes(data)
    receipt = {'schema_version':'1.0','requested_url':url,'final_url':final_url,'status':status,
               'retrieved_utc':datetime.now(timezone.utc).isoformat(),'content_type':mime,
               'sha256':sha(path),'capture_path':path.relative_to(root).as_posix()}
    receipt_path = folder/'receipt.json'
    receipt_path.write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    draft = {'url':url,'authority':'','authority_reason':'',
             'capture_path':path.relative_to(root).as_posix(),'capture_sha256':sha(path),
             'receipt_path':receipt_path.relative_to(root).as_posix(),'receipt_sha256':sha(receipt_path),
             'format':fmt,'review':{'reviewed':False,'tool_ref':'','observation':''}}
    # Field quotes/PDF pages need explicit locators supplied after actual reading.
    metadata = source_metadata(path,draft)[0] if fmt!='field_quotes' else {}
    result = {'source_draft':draft,'extracted_metadata':metadata,'status':'REVIEW_REQUIRED'}
    (folder/'draft.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--paper-root',type=Path,required=True)
    p.add_argument('--url',required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--format',choices=['html_meta','csl_json','field_quotes'],default='html_meta')
    a=p.parse_args()
    print(json.dumps(collect(a.paper_root,a.url,a.output,a.format),ensure_ascii=False,indent=2))
