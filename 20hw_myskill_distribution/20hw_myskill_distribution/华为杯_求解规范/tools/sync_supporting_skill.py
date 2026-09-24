"""Compatibility entrypoint: supporting gates require the complete workflow."""
from pathlib import Path
import sys
sys.dont_write_bytecode = True
import argparse
import json
from workflow_deployment import deploy as deploy_workflow

def deploy(template_root,project_root=None,*,mode='shared',runtime=None,inputs=(),purpose='production'):
    result=deploy_workflow(template_root,project_root,mode=mode,runtime=runtime,inputs=inputs,purpose=purpose)
    print(json.dumps({k:v for k,v in result.items() if k!='copies'},ensure_ascii=False))
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--template-root',type=Path,default=Path(__file__).resolve().parents[2])
    p.add_argument('--project-root',type=Path)
    p.add_argument('--mode',choices=('shared','legacy'),default='shared')
    p.add_argument('--runtime',choices=('codex','claude'))
    p.add_argument('--input',action='append',default=[])
    p.add_argument('--purpose',choices=('production','demo'),default='production')
    a=p.parse_args()
    result=deploy(a.template_root,a.project_root,mode=a.mode,runtime=a.runtime,inputs=a.input,purpose=a.purpose)
    raise SystemExit(result['status']!='PASS')
