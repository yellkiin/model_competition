"""Three-host Q3 supplement. No Q1 or independent Q2 optimization is scheduled."""
from __future__ import annotations
from collections import deque
from pathlib import Path
import argparse,importlib,json,os,subprocess,sys,time
from .common import ROOT,read,write
from .catalogue import scan,explicit,published
from .report import finish,collect


def official(value):
    folder=Path(value).resolve() if value else next((ROOT/'题目/A题').glob('*附件'))
    config=folder/'data/config.txt'
    if not config.is_file() or not (folder/'code/evaluation_validation.py').is_file():raise FileNotFoundError('A attachment must contain code/ and data/config.txt')
    return folder,config


def run_jobs(jobs,out,deadline,backend,max_workers):
    resource=importlib.import_module('research_a_orion_'+backend+'.resources')
    controller=resource.Admission(max_workers,.25);pending=deque();running=[];results=[]
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    for req in jobs:
        folder=Path(req['out']);old=folder/'request.json';summary=folder/'summary.json'
        if old.is_file() and read(old)!=req:raise ValueError('Changed request; choose a new output directory')
        if summary.is_file():results.append(read(summary));continue
        if old.is_file() and (folder/'progress.json').is_file():
            s=read(folder/'progress.json');execution={'reason':'recovered_saved_checkpoint','wall_seconds':s.get('elapsed_seconds',0),'unobserved_tail':True}
            results.append(finish(req,execution));continue
        if req.get('skip_no_material_candidate'):
            write(folder/'request.json',req)
            results.append(finish(req,{'reason':'no_material_published_candidate','wall_seconds':0,'new_evaluator_calls':0}));continue
        pending.append(req)
    last=0;sample=None;log=(out/'resources.jsonl').open('a',encoding='utf8')
    try:
        while pending or running:
            now=time.time()
            if now-last>=1 or sample is None:
                sample=controller.update(running);last=now
                log.write(json.dumps({'epoch':now,'active_workers':len(running),**sample})+'\n');log.flush()
            while pending and len(running)<sample['target_workers'] and now<deadline:
                req=pending.popleft();folder=Path(req['out']);folder.mkdir(parents=True,exist_ok=True)
                write(folder/'request.json',req);launch=time.time()
                write(folder/'launch.json',{**req,'launch_epoch':launch})
                stream=(folder/'worker.log').open('w',encoding='utf8')
                proc=subprocess.Popen([sys.executable,'-X','utf8','-m','L2提升.q3_supplement.worker',str(folder/'launch.json')],
                      cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,start_new_session=os.name!='nt',env={**os.environ,'PYTHONUTF8':'1'})
                running.append({'proc':proc,'request':req,'stream':stream,'launch':launch,'peak_rss':0})
            for item in running[:]:
                proc=item['proc'];req=item['request'];why=None
                if proc.poll() is None:
                    if time.time()>=deadline:why='campaign_deadline'
                    elif time.time()-item['launch']>=req['seconds']:why='configuration_time_limit'
                    if why:resource.terminate(proc)
                if proc.poll() is not None:
                    item['stream'].close();running.remove(item)
                    execution={'reason':why or ('finished' if proc.returncode==0 else 'worker_error'),
                       'wall_seconds':time.time()-item['launch'],'peak_rss_bytes':item['peak_rss'],'returncode':proc.returncode,
                       'time_limit_seconds':req['seconds']}
                    write(Path(req['out'])/'execution.json',execution);r=finish(req,execution);results.append(r)
                    print(f"{r['case']} n{r['n']}: {r['old_makespan']} -> {r['makespan']}; changed={r['changed']} pair={r['pair_status']}",flush=True)
            if pending and time.time()>=deadline:
                while pending:
                    req=pending.popleft();write(Path(req['out'])/'request.json',req)
                    results.append(finish(req,{'reason':'not_started_deadline','wall_seconds':0}))
            if pending or running:time.sleep(.15)
    finally:
        for item in running:resource.terminate(item['proc']);item['stream'].close()
        log.close()
    return results


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
    a=sub.add_parser('run');a.add_argument('--base-root',action='append',default=[]);a.add_argument('--base-manifest')
    a.add_argument('--out',required=True);a.add_argument('--official');a.add_argument('--backend',choices=('trident','unified'),default='trident')
    a.add_argument('--shard-index',type=int,choices=(0,1,2),required=True);a.add_argument('--cases',nargs='+');a.add_argument('--cores',nargs='+',type=int,choices=range(1,6),default=[1,2,3,4,5])
    a.add_argument('--seconds',type=float,default=120);a.add_argument('--hours',type=float,default=4);a.add_argument('--max-calls',type=int,default=8)
    a.add_argument('--workers',type=int,default=0);a.add_argument('--min-gain',type=float,default=.001)
    a.add_argument('--policy',choices=('bank_only','selective','explore'),default='bank_only')
    a.add_argument('--repair-missing-pairs',action='store_true');a.add_argument('--q2-transfer-threshold',type=float,default=.03)
    a=sub.add_parser('collect');a.add_argument('roots',nargs='+');a.add_argument('--out',required=True);a.add_argument('--q2-transfer-threshold',type=float,default=.03)
    args=p.parse_args(argv)
    if args.action=='collect':print(json.dumps(collect(args.roots,args.out,args.q2_transfer_threshold),ensure_ascii=False,indent=2));return 0
    if not 0<args.seconds<=600 or args.hours<=0 or args.workers<0 or args.max_calls<1 or not 0<=args.min_gain<1:p.error('Invalid budget, worker or minimum improvement threshold')
    out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=True)
    options={k:v for k,v in vars(args).items() if k not in ('action','workers','hours')}
    specfile=out/'campaign.json'
    if specfile.is_file():
        campaign=read(specfile)
        if campaign['options']!=options:raise ValueError('Changed method/source/budget: use a new output directory')
    else:
        if not args.base_root and not args.base_manifest:p.error('Provide actual existing Trident final result root(s) or explicit plan manifest')
        records=explicit(args.base_manifest) if args.base_manifest else scan(args.base_root)
        shardfile=ROOT/('research_a_orion_'+args.backend)/'SHARDS.json'
        shards=read(shardfile)['shards'];allowed=set(shards[args.shard_index]['cases'])
        if args.cases:allowed&={('case_'+f'{int(c):03d}') if c.isdigit() else c for c in args.cases}
        records=[r for r in records if r['case'] in allowed and r['n'] in args.cores]
        if not records:raise ValueError('No selected Q3 plans found in this host shard; inspect roots or explicit manifest')
        wanted={(c,n) for c in allowed for n in args.cores};found={(r['case'],r['n']) for r in records}
        bank,notes=published(out/'candidate_bank')
        if args.policy=='bank_only' and not bank:raise FileNotFoundError('No actual published L2 candidate plans found. Restore the portfolio tar.xz or v1 incumbent directory; no scores are fabricated.')
        for r in records:r['published']=bank.get((r['case'],r['n']),[])
        campaign={'options':options,'backend':args.backend,'seconds':args.seconds,'min_gain':args.min_gain,'policy':args.policy,
                  'records':records,'missing_base_keys':sorted(wanted-found),'candidate_bank_notes':notes,
                  'base_method':'Trident #38','scope':'Q3 only; native engine/auditor selected explicitly'}
        write(specfile,campaign)
    if not (out/'clock.json').is_file():write(out/'clock.json',{'deadline_epoch':time.time()+args.hours*3600})
    deadline=read(out/'clock.json')['deadline_epoch'];of,cfg=official(args.official);jobs=[]
    for record in campaign['records']:
        graph=of/'data'/f"{record['case']}.json"
        if not graph.is_file():raise FileNotFoundError(f'Restore only missing A graph for this shard: {graph}')
        with graph.open('rb') as f:
            if f.read(90).startswith(b'version https://git-lfs.github.com'):raise ValueError('Restore real A input, not LFS pointer: '+str(graph))
        jobs.append({**record,'out':str(out/'jobs'/f"{record['case']}_q3_n{record['n']}"),
            'official':str(of),'config':str(cfg),'graph':str(graph),'backend':args.backend,'seconds':args.seconds,
            'max_calls':args.max_calls,'min_gain':args.min_gain,'policy':args.policy,'search':args.policy!='bank_only',
            'explore_portfolio':args.policy=='explore','repair_missing_pairs':args.repair_missing_pairs,
            'skip_no_material_candidate':args.policy=='bank_only' and record.get('old_makespan') is not None and not args.repair_missing_pairs and not any(x.get('makespan') is None or x['makespan']<=record['old_makespan']*(1-args.min_gain) for x in record['published'])})
    def opportunity(r):
        vals=[x['makespan'] for x in r['published'] if x.get('makespan')]
        return (min(vals)/r['old_makespan'] if vals and r.get('old_makespan') else 2,r['case'],r['n'])
    jobs.sort(key=opportunity)
    run_jobs(jobs,out,deadline,args.backend,args.workers)
    report=collect([out],out/'report',args.q2_transfer_threshold)
    report['missing_base_keys']=campaign['missing_base_keys'];write(out/'report/report.json',report)
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if not report['missing_patch_keys'] and not report['missing_base_keys'] and not report['local_errors'] else 1
if __name__=='__main__':raise SystemExit(main())
