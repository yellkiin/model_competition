#!/usr/bin/env python3
"""Compatibility CLI for the complete shared workflow deployment inventory."""
import argparse
import sys
sys.dont_write_bytecode = True
import json
from pathlib import Path
from workflow_deployment import deploy, protected

if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2])
    p.add_argument('--project',type=Path)
    p.add_argument('--mirrors-only',action='store_true')
    p.add_argument('--mode',choices=('shared','legacy','maintenance'),default='shared')
    p.add_argument('--runtime',choices=('codex','claude'))
    p.add_argument('--input',action='append',default=[])
    p.add_argument('--purpose',choices=('production','demo'),default='production')
    a=p.parse_args()
    r=deploy(a.root,a.project,a.mirrors_only,mode=a.mode,runtime=a.runtime,inputs=a.input,purpose=a.purpose)
    print(json.dumps({k:v for k,v in r.items() if k!='copies'},ensure_ascii=False))
    raise SystemExit(r['status']!='PASS')
