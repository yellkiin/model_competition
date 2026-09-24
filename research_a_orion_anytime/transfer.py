"""Pack a result root and relocate its internal references on another machine.

No original graphs, official evaluators, or literature are included. The old
absolute output-root prefix in JSON strings is rewritten after safe extraction.
The content hashes of inputs, algorithms and selected plans remain unchanged.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import zipfile
from .worker import atomic_json


def rewrite(value,old,new):
    if isinstance(value,dict):return {k:rewrite(v,old,new) for k,v in value.items()}
    if isinstance(value,list):return [rewrite(v,old,new) for v in value]
    if isinstance(value,str):
        # Windows and POSIX output-root prefixes are supported; no substring replacement.
        v=value.replace('\\','/');o=old.replace('\\','/').rstrip('/')
        if v==o or v.startswith(o+'/'):return new.rstrip('/')+v[len(o):]
    return value


def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('command',choices=['pack','unpack']);p.add_argument('--root',required=True);p.add_argument('--zip',required=True)
    a=p.parse_args(argv);root=Path(a.root).resolve();archive=Path(a.zip).resolve()
    if a.command=='pack':
        if not (root/'campaign.json').exists():raise ValueError('Pack only a campaign output root')
        archive.parent.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
            z.writestr('TRANSFER.json',json.dumps({'old_root':str(root),'schema':1}))
            for f in sorted(root.rglob('*')):
                if f.is_file() and f!=archive and f.suffix not in ('.tmp',):z.write(f,Path('run')/f.relative_to(root))
    else:
        if root.exists() and any(root.iterdir()):raise ValueError('Unpack into a new empty output root')
        root.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(archive) as z:
            meta=json.loads(z.read('TRANSFER.json'));old=meta['old_root']
            for name in z.namelist():
                if name=='TRANSFER.json' or name.endswith('/'):continue
                rel=Path(name)
                if rel.parts[0]!='run' or '..' in rel.parts or rel.is_absolute():raise ValueError('Unsafe archive path')
                target=root.joinpath(*rel.parts[1:])
                if not target.is_relative_to(root):raise ValueError('Archive escapes output root')
                target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(name))
        for f in root.rglob('*.json'):
            if f.name.endswith('_plan.json') or f.name=='current_plan.json':continue
            val=json.loads(f.read_text(encoding='utf-8-sig'));changed=rewrite(val,old,str(root).replace('\\','/'))
            if changed!=val:atomic_json(f,changed)
        atomic_json(root/'transfer_receipt.json',dict(old_root=old,new_root=str(root),note='Do not resume on another interpreter; collect/verify using local original inputs'))
    print(str(archive if a.command=='pack' else root))

if __name__=='__main__':raise SystemExit(main())
