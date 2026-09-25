"""Archive complete runs and paper data in 40 MiB chunks; restore and collect."""
from __future__ import annotations
import argparse
import shutil
import tempfile
import zipfile
from pathlib import Path
from .io import write,read,utc
from .prepare import SplitReader

def pack(root,out):
    root=Path(root).resolve();out=Path(out).resolve()
    if out.is_relative_to(root):raise ValueError('Archive output must be outside its input run')
    out.mkdir(parents=True,exist_ok=False)
    members=[]
    with tempfile.TemporaryDirectory() as tmp:
        zpath=Path(tmp)/'results.zip'
        with zipfile.ZipFile(zpath,'w',zipfile.ZIP_DEFLATED,compresslevel=1) as z:
            for p in sorted(root.rglob('*')):
                if not p.is_file() or p.name.endswith('.tmp') or '__pycache__' in p.parts:continue
                rel=p.relative_to(root);z.write(p,str(Path('run')/rel));members.append(str(rel))
        parts=[]
        with zpath.open('rb') as f:
            while True:
                data=f.read(40*1024**2)
                if not data:break
                name=f'results.zip.part{len(parts)+1:03d}';(out/name).write_bytes(data)
                parts.append(dict(name=name,bytes=len(data)))
    for name in ('collection.json','per_case.csv','trajectory.csv','diagnostic_queue.csv','campaign.json'):
        if (root/name).exists():shutil.copy2(root/name,out/name)
    if (root/'paper_data').exists():shutil.copytree(root/'paper_data',out/'paper_data')
    write(out/'ARCHIVE.json',dict(schema=1,created_utc=utc(),parts=parts,members=members,
        root=str(root),format='continuous ZIP bytes; plans, original responses, requests, failures and events'))
    return out/'ARCHIVE.json'

def restore(index,out):
    index=Path(index);out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    with zipfile.ZipFile(SplitReader([index.parent/r['name'] for r in read(index)['parts']])) as z:
        for name in z.namelist():
            p=Path(name)
            if p.parts[0]!='run' or '..' in p.parts or p.is_absolute():raise ValueError('Invalid archive member')
            dest=out/Path(*p.parts[1:]);dest.parent.mkdir(parents=True,exist_ok=True)
            if not name.endswith('/'):
                with z.open(name) as src,dest.open('wb') as f:shutil.copyfileobj(src,f)
    return out

def combine(roots,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=False);seen=set()
    for root in map(Path,roots):
        for graph in (root/'graphs').glob('case_*'):
            if graph.name in seen:raise ValueError(f'Duplicate graph across hosts: {graph.name}')
            seen.add(graph.name);shutil.copytree(graph,out/'graphs'/graph.name)
    from .report import collect
    return collect(out,expected_cases=[f'case_{i:03d}' for i in range(1,101)],detailed=True)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['pack','restore','combine'])
    p.add_argument('--roots',nargs='+',required=True);p.add_argument('--out',required=True);a=p.parse_args()
    if a.command=='pack':print(pack(a.roots[0],a.out))
    elif a.command=='restore':print(restore(a.roots[0],a.out))
    else:print(combine(a.roots,a.out))
if __name__=='__main__':main()
