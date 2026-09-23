"""One-command CPU experiment driver. No API keys, GPU or repository edits required."""
import argparse,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input');p.add_argument('--out',default=str(ROOT/'research_fd/outputs/d_local'));p.add_argument('--size',choices=['small','80'],default='small');p.add_argument('--seconds',type=float,default=10);p.add_argument('--backend',choices=['none','highs','cpsat'],default='highs');p.add_argument('--radio',action='store_true');p.add_argument('--seed',type=int,default=7);a=p.parse_args()
out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
def run(*args):subprocess.run([sys.executable,'-m','research_fd.d_experiments',*map(str,args)],cwd=ROOT,check=True)
source=Path(a.input).resolve() if a.input else out/'instance.json'
if not a.input:run('synthetic','--out',source,'--seed',a.seed,'--nodes',4 if a.size=='small' else 15,'--boxes',12 if a.size=='small' else 80)
run('transport','--input',source,'--out',out/'transport','--seed',a.seed,'--seconds',a.seconds,'--backend',a.backend)
if a.radio:
    run('radio','--input',source,'--plan',out/'transport/best_plan.json','--out',out/'radio','--mode','fixed','--grid',3,'--sample-step',40,'--seconds',a.seconds,'--max-sessions',6000)
    plan=out/'radio/joint_plan.json'
    if plan.exists():
        for k in (2,3):
            for policy in ('strict','duplicate'):run('partition','--input',source,'--plan',plan,'--out',out/f'partition_{policy}_{k}.json','--groups',k,'--policy',policy)
print('Results:',out)
