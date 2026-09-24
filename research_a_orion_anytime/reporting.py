"""Per-case ratios, coverage-aware tables, and self-contained SVG line plots."""
from __future__ import annotations
import csv
import html
import math
from pathlib import Path
import statistics
from .solver import read
from .worker import atomic_json,audit
from .core import Graph,Config,fingerprint
from .supervisor import sha


def mean(xs):return statistics.mean(xs) if xs else None

def gmean(xs):return math.exp(mean([math.log(x) for x in xs])) if xs and all(x>0 for x in xs) else None


def prefix_best(summary,seconds=None,evaluations=None):
    p=Path(summary['job'])/'progress.json'
    if not p.is_file():return None
    s=read(p);good=[a for a in s['attempts'] if a['status']=='ok']
    if seconds is not None:good=[a for a in good if a['completed_seconds']<=seconds]
    if evaluations is not None:good=[a for a in good if a['index']<=evaluations]
    return min((a['makespan'] for a in good),default=None)


def svg_lines(path,title,series,complete):
    allv=[v for _,values in series for _,v in values if v is not None]
    if not allv:return
    ymax=max(1,max(allv)*1.1);w,h=720,410;l,r,t,b=75,30,65,75
    def x(n):return l+(n-1)*(w-l-r)/4
    def y(v):return h-b-v*(h-t-b)/ymax
    lines=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
           '<rect width="100%" height="100%" fill="white"/>',
           f'<text x="{l}" y="26" font-size="18">{html.escape(title)}</text>',
           f'<text x="{l}" y="47" font-size="12">'+('100 official cases, arithmetic mean of per-case ratios' if complete else 'SUBSET / INCOMPLETE: do not report as 100-case result')+'</text>',
           f'<path d="M{l},{t} V{h-b} H{w-r}" stroke="black" fill="none"/>']
    for n in range(1,6):lines.append(f'<text x="{x(n)-4}" y="{h-b+22}">{n}</text>')
    for i in range(6):
        v=ymax*i/5;lines.append(f'<text x="15" y="{y(v)+5}">{v:.2f}</text>')
    for j,(label,values) in enumerate(series):
        pts=' '.join(f'{x(n):.2f},{y(v):.2f}' for n,v in values if v is not None)
        dash='' if j==0 else ' stroke-dasharray="7 5"'
        lines.append(f'<polyline points="{pts}" stroke="black" stroke-width="2" fill="none"{dash}/>')
        lines.append(f'<text x="{l+j*260}" y="{h-20}" font-size="12">'+html.escape(('solid: ' if j==0 else 'dashed: ')+label)+'</text>')
    lines.append(f'<text x="{w/2-50}" y="{h-44}">NPU cores</text></svg>')
    Path(path).write_text('\n'.join(lines),encoding='utf8')


def collect(index_path,destination,official=None,verify=False,require_complete=False):
    index=read(index_path);out=Path(destination);out.mkdir(parents=True,exist_ok=True)
    chosen={tuple(x['key']):read(x['summary']) for x in index['chosen']}
    pairs={tuple(x['key']):read(x['summary']) for x in index.get('pairs',[])}
    expected={tuple(x) for x in index['expected']}
    signatures={tuple(s['signature'][k] for k in ('algorithm','official','config')) for s in list(chosen.values())+list(pairs.values()) if 'signature' in s}
    if len(signatures)>1:raise ValueError('Cannot combine different source/config versions')
    baselines={c:s for (c,q,n),s in chosen.items() if q==0 and s['status']=='ok'}
    rows=[];failures=[];checks=[];gcache={}
    for key in sorted(expected):
        c,q,n=key;s=chosen.get(key,{})
        row=dict(case=c,q=q,n=n,status=s.get('status','missing'),makespan=s.get('makespan'),baseline=baselines.get(c,{}).get('makespan'),
                 speedup=None,added_copy_bytes=s.get('added_copy_bytes'),partition_added_copy_bytes=s.get('partition_added_copy_bytes'),
                 spill_added_copy_bytes=s.get('spill_added_copy_bytes'),cache_hit_rate=s.get('cache_hit_rate'),
                 solve_seconds=s.get('end_to_end_solve_seconds',s.get('total_job_seconds',s.get('process_seconds'))),construction_seconds=s.get('construction_seconds'),evaluations=s.get('evaluations'),
                 no_l2_makespan=None,no_l2_added_copy_bytes=None,cache_speedup=None,pair_status=None,
                 lower=s.get('certificate',{}).get('global_lower'),ratio_upper=s.get('certificate',{}).get('approximation_ratio_upper'))
        if row['status']=='ok' and row['baseline'] and row['makespan']:
            row['speedup']=row['baseline']/row['makespan']
        if q==3:
            pair=pairs.get(key,{})
            row['pair_status']=pair.get('status','missing')
            if pair.get('status')=='ok' and pair['plan_hash']==s.get('plan_hash'):
                row.update(no_l2_makespan=pair['makespan'],no_l2_added_copy_bytes=pair['added_copy_bytes'],
                           cache_speedup=pair['makespan']/row['makespan'] if row['makespan'] else None)
            elif pair.get('status')=='ok':raise ValueError('Cache counterfactual uses a different plan')
        if row['status']!='ok' or q==3 and row['pair_status']!='ok':failures.append(list(key))
        if verify and s.get('status')=='ok':
            root=Path(official);config=next(p for p in (root/'data/config.txt',root/'config.txt') if p.exists())
            gp=root/'data'/f'{c}.json'
            if sha(gp)!=s['signature']['graph'] or sha(config)!=s['signature']['config']:raise ValueError('Verification inputs differ from run')
            if c not in gcache:gcache={c:Graph(read(gp))}
            g=gcache[c];cfg=Config.read(config);plan=read(s['plan']);result=read(s['result'])
            if fingerprint(plan)!=s['plan_hash']:raise ValueError('Plan content changed')
            test=audit(g,plan,result['official_result'],q,cfg)
            if not test['ok']:raise ValueError(f'Independent audit failed for {key}: {test}')
            target=out/'plans'/f'q{q}'/f'n{n}'/f'{c}_multicore_res.json';atomic_json(target,plan)
            if q==3 and row['pair_status']=='ok':
                test2=audit(g,plan,read(pairs[key]['result'])['official_result'],2,cfg)
                if not test2['ok']:raise ValueError('Counterfactual audit failed')
            checks.append(dict(case=c,q=q,n=n,ok=True,plan_hash=s['plan_hash']))
        rows.append(row)
    with (out/'per_case.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,list(rows[0]) if rows else ['case']);writer.writeheader();writer.writerows(rows)
    grouped={}
    for q in (1,2,3):
        for n in range(1,6):
            rs=[r for r in rows if r['q']==q and r['n']==n]
            # Q1/Q2 one-core points are the prescribed original baseline, not an optimized run.
            if n==1 and q in (1,2):
                vals=[1.0 for _ in baselines];pairs_v=[];no_l2=[]
            else:
                vals=[r['speedup'] for r in rs if r['speedup'] is not None]
                pairs_v=[r['cache_speedup'] for r in rs if r['cache_speedup'] is not None]
                no_l2=[r['baseline']/r['no_l2_makespan'] for r in rs if r['baseline'] and r['no_l2_makespan']]
            grouped[f'q{q}_n{n}']=dict(count=len(vals),mean_speedup=mean(vals),geomean_speedup=gmean(vals),
                        min_speedup=min(vals) if vals else None,cache_pair_count=len(pairs_v),mean_same_plan_cache_speedup=mean(pairs_v),
                        same_plan_no_l2_mean_speedup=mean(no_l2))
    formal={(f'case_{i:03d}',0,1) for i in range(1,101)}
    formal|={(f'case_{i:03d}',q,n) for i in range(1,101) for q in (1,2,3) for n in (2,3,4,5)}
    formal|={(f'case_{i:03d}',3,1) for i in range(1,101)}
    complete=expected==formal and not failures
    report=dict(formal_complete=complete,expected=len(expected),valid=sum(r['status']=='ok' for r in rows),
                failures_or_missing=failures,groups=grouped,independent_checks=len(checks),
                memory_scope='official Step3 peaks checked, not independent allocation replay',
                policy=index.get('policy'),signatures=[list(s) for s in signatures])
    atomic_json(out/'report.json',report);atomic_json(out/'verification.json',checks)
    for q in (1,2):svg_lines(out/f'question_{q}.svg',f'Question {q}: speedup',[(f'Q{q}',[(n,grouped[f'q{q}_n{n}']['mean_speedup']) for n in range(1,6)])],complete)
    svg_lines(out/'question_3.svg','Question 3: identical-plan L2 comparison',[
        ('with L2',[(n,grouped[f'q3_n{n}']['mean_speedup']) for n in range(1,6)]),
        ('same plan, no L2',[(n,grouped[f'q3_n{n}']['same_plan_no_l2_mean_speedup']) for n in range(1,6)])],complete)
    if require_complete and not complete:raise ValueError('Formal 100-case export is incomplete; see report.json')
    return report
