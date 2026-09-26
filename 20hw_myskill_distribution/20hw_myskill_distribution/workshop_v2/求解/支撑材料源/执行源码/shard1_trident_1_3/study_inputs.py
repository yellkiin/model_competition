"""Read the three studies and their actual selected plans from pinned Git refs."""
from __future__ import annotations
import argparse, json, subprocess
from pathlib import Path
from .io import ROOT,read,write
from .bootstrap import PIN

RECONCILE='e14a01a3237c340c7be56f1e1e94869a51e16e8e'
STUDIES=[
 'research_a_orion_track_structure/results/safe_refine_20260925/review/per_case.csv',
 'research_a_orion_track_structure/results/safe_refine_20260925/review/REPORT.md',
 'research_a_orion_track_memory/results/coherent_v4_20260925/per_case.csv',
 'research_a_orion_track_memory/results/coherent_v4_20260925/REPORT.md',
 'research_a_orion_track_memory/results/fivecore_final_20260924/per_case.csv',
 'research_a_orion_track_memory/results/fivecore_final_20260924/REPORT.md']


def run(out,git_root=None,fetch=False):
    out=Path(out).resolve();repo=Path(git_root or ROOT);out.mkdir(parents=True,exist_ok=True)
    if fetch:
        for ref in (PIN,RECONCILE):subprocess.run(['git','fetch','--filter=blob:none','--no-tags','origin',ref],cwd=repo,check=True)
    missing=[];saved=[]
    def get(ref,path):
        p=subprocess.run(['git','show',ref+':'+path],cwd=repo,capture_output=True)
        if p.returncode:
            missing.append({'ref':ref,'path':path,'error':p.stderr.decode('utf8','replace')[:500]});return None
        target=out/'materials'/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(p.stdout)
        saved.append({'ref':ref,'path':path});return p.stdout
    for path in STUDIES:get(PIN,path)
    prefix='research_a_orion_track_anytime/results/reconcile_20260925_1012/'
    payload=get(RECONCILE,prefix+'AVAILABLE_SEEDS.json')
    entries=[]
    if payload:
        for row in json.loads(payload):
            value=get(RECONCILE,row['plan_file'])
            if value is None:continue
            destination=out/'plans'/f"{row['case']}_q{row['q']}_n{row['n']}.json";destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(value)
            entries.append({**row,'plan_file':str(destination.resolve()),'source_ref':RECONCILE,'source_seed_seconds':None})
    get(RECONCILE,'research_a_orion_track_anytime/RECONCILIATION_COMPARISON.md')
    # Missing historical raw plans remain explicit; reported scores are targets,
    # not synthetic seeds. Production is still protected by the day01 archive.
    write(out/'AVAILABLE_SEEDS.json',entries);write(out/'STUDY_RECEIPT.json',{'saved':saved,'missing':missing})
    return {'plans':len(entries),'materials':len(saved),'missing':missing}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',required=True);p.add_argument('--git-root');p.add_argument('--fetch',action='store_true');a=p.parse_args()
    print(json.dumps(run(a.out,a.git_root,a.fetch),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
