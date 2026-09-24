"""Snapshot unchanged official inputs and all formal candidate evaluation artifacts."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED, ZIP_STORED
import hashlib
import json

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'求解/提交源'
OUT.mkdir(exist_ok=True)
INPUT=ROOT/'数据/原始/A题官方附件/data'
RUNS=ROOT/'求解/正式实验/候选评估'

def sha(path):
    d=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1<<20),b''):d.update(chunk)
    return d.hexdigest()

def make(name,files):
    target=OUT/name
    if target.exists(): target.unlink()
    with ZipFile(target,'w') as z:
        for path in files:
            rel=path.relative_to(ROOT).as_posix()
            kind=ZIP_STORED if path.suffix=='.gz' else ZIP_DEFLATED
            z.write(path,rel,compress_type=kind,compresslevel=6 if kind==ZIP_DEFLATED else None)
    return {'path':target.relative_to(ROOT).as_posix(), 'sha256':sha(target),
            'files':len(files),'bytes':target.stat().st_size}

inputs=sorted(p for p in INPUT.iterdir() if p.is_file())
assert len(inputs)==101 and sum(p.name.startswith('case_') for p in inputs)==100
runs=sorted(p for p in RUNS.rglob('*') if p.is_file() and p.suffix in ('.json','.gz'))
assert sum(p.name.endswith('.receipt.json') for p in runs)==2005
assert sum(p.name.endswith('.json.gz') for p in runs)==2005
result={'input':make('官方输入.zip',inputs),'evaluations':make('正式候选评估.zip',runs)}
(OUT/'归档来源.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps(result,ensure_ascii=False))
