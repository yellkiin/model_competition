"""Bounded per-case sequence: fresh fixed plans -> equal-seed warm -> cold -> extension."""
from __future__ import annotations
import argparse,json,os,shutil,subprocess,sys,time
from pathlib import Path
from datetime import datetime,timezone
from .recheck_evidence import ROOT,read,csvwrite
from research_a_orion_anytime.worker import atomic_json


def main():
    p=argparse.ArgumentParser();p.add_argument('--case',required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--wall-seconds',type=float,default=1500)
    a=p.parse_args();c=f'{int(a.case):03d}';out=a.out.resolve();out.mkdir(parents=True,exist_ok=False);start=time.monotonic();deadline=start+a.wall_seconds
    snapshots=out/'source';snapshots.mkdir()
    for f in ('plugin_recheck.py','recheck_worker.py','recheck_run.py','recheck_evidence.py','recheck_case.py','plugin.py','worker.py','run.py'):
        shutil.copy2(Path(__file__).parent/f,snapshots/f)
    manifest=dict(case=c,utc=datetime.now(timezone.utc).isoformat(),wall_seconds=a.wall_seconds,head_commit=os.environ.get('RECHECK_HEAD_SHA'),github_run=os.environ.get('GITHUB_RUN_ID'),scope='one representative real graph; old/new arms on this same machine',python=sys.version)
    atomic_json(out/'suite_manifest.json',manifest);phases=[]
    def fixed(q,n,source_n=None,label=None):
        name=label or f'formal_{c}_q{q}_n{n}';d=out/'fixed'/name;d.mkdir(parents=True,exist_ok=True)
        req=dict(case=c,q=q,n=n,label=name,out=str(d))
        if source_n is not None:req['source_n']=source_n
        atomic_json(d/'replay_request.json',req)
        if deadline-time.monotonic()<180:return
        with (d/'stdout.log').open('wb') as log:
            proc=subprocess.run([sys.executable,'-u','-m','research_a_orion_track_structure.recheck_evidence',str(d/'replay_request.json')],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=180)
        if (d/'summary.json').exists():phases.append(read(d/'summary.json'))
        print('FIXED',name,phases[-1].get('new_makespan') if phases else None,flush=True)
    if c=='044':
        # Case IDs here select research counterfactuals, never an algorithm strategy.
        fixed(2,3,label='044_final_n3');fixed(2,5,3,'044_final_n3_padded_n5')
    for q in (0,1,2,3):
        for n in ((1,) if q==0 else (2,5)):fixed(q,n)
    csvwrite(out/'replay_compare.csv',phases)
    def run(name,mode,qs='1,2,3',ns='2,5',seconds=30,cap=8,workers='1',seed_spec=None):
        remaining=deadline-time.monotonic()
        if remaining<seconds+120:
            phases.append(dict(phase=name,status='not_started',reason='round_deadline'));return
        dest=out/name
        cmd=[sys.executable,'-u','-m','research_a_orion_track_structure.recheck_run','--cases',c,'--questions',qs,'--cores',ns,'--methods','old,published,corrected','--mode',mode,'--seconds',str(seconds),'--max-evaluations',str(cap),'--workers',workers,'--wall-seconds',str(max(1,remaining-10)),'--pair-seconds','120','--out',str(dest)]
        if mode=='warm_start':cmd+=['--seed-root',str(out/'fixed')]
        if seed_spec:cmd+=['--seed-spec',str(seed_spec)]
        t=time.monotonic();proc=subprocess.run(cmd,cwd=ROOT)
        phases.append(dict(phase=name,exit_code=proc.returncode,seconds=time.monotonic()-t,path=name))
        atomic_json(out/'suite_progress.json',dict(phases=phases,elapsed_seconds=time.monotonic()-start))
    if c=='044':
        spec=out/'cross_core_seed_spec.json';atomic_json(spec,{'044_q2_n5':str(out/'fixed/044_final_n3_padded_n5')})
        run('warm_cross_core','warm_start','2','5',seed_spec=spec)
    run('warm30','warm_start')
    run('cold30_cap8','cold_start',workers='2')
    if c=='016':run('cold300_q1','cold_start','1','5',300,256,'1')
    run('cold300_q2','cold_start','2','5',300,256,'1')
    if c=='064':run('cold300_q1','cold_start','1','5',300,256,'1')
    atomic_json(out/'suite_summary.json',dict(**manifest,elapsed_seconds=time.monotonic()-start,phases=phases,formal_complete=False))

if __name__=='__main__':main()
