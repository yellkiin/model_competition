"""Export the Q3 supplement; large raw data remain local unless explicitly copied."""
from pathlib import Path
import argparse,shutil,zipfile
from .common import read,write


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True);p.add_argument('--out',required=True);a=p.parse_args()
    root,out=Path(a.root).resolve(),Path(a.out).resolve()
    if root==out or root in out.parents:raise ValueError('Export outside the active run directory')
    out.mkdir(parents=True,exist_ok=True)
    if (out/'evidence.zip').exists():raise FileExistsError('Use a new publication directory; existing evidence will not be overwritten')
    if (root/'report').is_dir():shutil.copytree(root/'report',out/'report',dirs_exist_ok=True)
    index=[]
    with zipfile.ZipFile(out/'evidence.zip','w',zipfile.ZIP_DEFLATED,compresslevel=3) as z:
        for path in root.rglob('*'):
            if path.is_file() and '.tmp' not in path.name and '__pycache__' not in path.parts:
                z.write(path,'run/'+path.relative_to(root).as_posix())
        for p in sorted(root.glob('jobs/*/summary.json')):
            s=read(p)
            if s['changed'] and s['status']=='ok':
                plan=p.parent/'plan.json';dest=out/'changed_plans'/f"n{s['n']}"/f"{s['case']}_multicore_res.json"
                dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(plan,dest)
                index.append({'case':s['case'],'n':s['n'],'plan':dest.relative_to(out).as_posix(),
                              'new_makespan':s['makespan'],'old_makespan':s['old_makespan'],'pair_status':s['pair_status']})
        z.writestr('README.txt','Q3 supplement only. Old Q1/Q2 remain unchanged. Requests retain original source paths; saved accepted outputs are relative to each job. Do not rerun transferred output directories. New Q3 ratios require matching same-plan no-L2 results.\n')
    write(out/'PUBLICATION.json',{'scope':'Q3 patch over Trident #38','archive':'evidence.zip','changed_plans':index,
          'automatic_upload':False,'notes':'Commit small report/changed plan files. Transfer large evidence.zip manually unless explicitly requested otherwise.'})
    print(out)
if __name__=='__main__':main()
