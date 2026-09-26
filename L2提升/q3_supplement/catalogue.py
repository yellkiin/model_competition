"""Locate actual final #38 plans/results; summaries alone are not new scores."""
from __future__ import annotations
from pathlib import Path
import re,tarfile
from .common import ROOT,PROPOSAL,read,write,csv_read


def target(path):
    text=Path(path).as_posix();matches=re.findall(r'(case_\d{3})_q([0-3])_n([1-5])',text)
    if matches:
        c,q,n=matches[-1];return c,int(q),int(n)
    m=re.search(r'(?:^|/)q([0-3])/n([1-5])/(case_\d{3})_multicore_res\.json$',text)
    return (m[3],int(m[1]),int(m[2])) if m else None


def resolve(value,folder):
    if not value:return None
    p=Path(str(value).replace('\\','/'))
    for choice in (p,folder/p,ROOT/p):
        if choice.is_file():return str(choice.resolve())
    return None


def scan(roots):
    """Scan only final job / exported plan layouts, not candidate attempts.

    Ambiguous different final plans require an explicit manifest. Do not silently
    choose a previous run by directory name, mtime, or best reported scalar.
    """
    records={};aux={};issues=[]
    for root in map(Path,roots):
        if not root.is_dir():raise FileNotFoundError(f'Extract the existing #38 result package first: {root}')
        for summary in root.rglob('summary.json'):
            if {'attempts','evaluations','failures','sensitivity','mechanisms','diagnostics'} & set(summary.relative_to(root).parts):continue
            s=read(summary);key=(s.get('case'),s.get('q'),s.get('n'))
            if not isinstance(key[0],str) or key[1] not in (0,2,3) or key[2] not in range(1,6):continue
            folder=summary.parent
            plan=next((p for p in (folder/'plan.json',folder/'selected/plan.json') if p.is_file()),None)
            if plan is None:continue
            if s.get('makespan') is None or s.get('status') not in ('ok','PASS',None):continue
            result=next((p for p in (folder/'result.json.gz',folder/'selected/result.json.gz',folder/'selected/q3.json.gz',folder/'response.json',folder/'selected/result.json') if p.is_file()),None)
            if result is None:
                for field in ('result_file','result','response'):
                    got=resolve(s.get(field),folder)
                    if got:result=Path(got);break
            item={'case':key[0],'q':key[1],'n':key[2],'plan':str(plan.resolve()),
                  'q3_result':str(result.resolve()) if result else None,'old_makespan':int(s['makespan']),
                  'old_added_copy_bytes':s.get('added_copy_bytes'),'source_summary':str(summary.resolve()),
                  'reference_t1':s.get('baseline',s.get('reference')) if isinstance(s.get('baseline',s.get('reference')),(int,float)) else None}
            is_pair='pairs' in summary.relative_to(root).parts
            if is_pair:
                k=target(folder/'plan.json')
                if k:aux[k[0],k[2],'pair']=item
                continue
            if key[1]!=3:
                aux[key[0],key[2],key[1]]=item;continue
            inline=folder/'same_plan_no_l2_result.json.gz';inline_plan=folder/'same_plan_no_l2_plan.json'
            if s.get('pair_status')=='ok' and inline.is_file() and inline_plan.is_file():
                item.update(no_l2_result=str(inline.resolve()),no_l2_plan=str(inline_plan.resolve()))
            pair=s.get('pair') or s.get('paired') or {}
            if isinstance(pair,dict) and pair.get('status')=='ok':
                pair_result=resolve(pair.get('result_file',pair.get('response')),folder)
                pair_plan=resolve(pair.get('plan_file',pair.get('plan')),folder)
                if pair_result and pair_plan:item.update(no_l2_result=pair_result,no_l2_plan=pair_plan)
            accept(records,key,item,issues)
        for plan in root.glob('**/q3/n*/*_multicore_res.json'):
            if {'attempts','evaluations','sensitivity','diagnostics'} & set(plan.relative_to(root).parts):continue
            key=target(plan)
            if key and key not in records:
                records[key]={'case':key[0],'q':3,'n':key[2],'plan':str(plan.resolve()),'old_makespan':None,'q3_result':None}
    for (c,q,n),r in records.items():
        if not r.get('reference_t1') and (c,1,0) in aux:r['reference_t1']=aux[c,1,0]['old_makespan']
        if (c,n,2) in aux:r['old_q2_best']=aux[c,n,2]['old_makespan']
        pair=aux.get((c,n,'pair'))
        if pair and pair['q3_result'] and not r.get('no_l2_result'):
            r.update(no_l2_result=pair['q3_result'],no_l2_plan=pair['plan'])
    if issues:raise ValueError('Conflicting final plans: '+str(issues[:8])+'. Pass only the chosen final roots, or use --base-manifest.')
    return sorted(records.values(),key=lambda r:(r['case'],r['n']))


def accept(records,key,item,issues):
    if key in records:
        old=records[key]
        if read(old['plan'])!=read(item['plan']):issues.append({'key':key,'first':old['plan'],'second':item['plan']});return
        if old.get('old_makespan') is not None and item.get('old_makespan') is not None and old['old_makespan']!=item['old_makespan']:
            issues.append({'key':key,'reason':'same plan conflicting scalar'});return
        if not old.get('q3_result') and item.get('q3_result'):records[key]=item
    else:records[key]=item


def explicit(path):
    p=Path(path);data=csv_read(p) if p.suffix.lower()=='.csv' else read(p)
    rows=data if isinstance(data,list) else data['records'];out=[];seen=set()
    for r in rows:
        r=dict(r);r['n']=int(r['n']);r['q']=int(r.get('q') or 3)
        if r['q']!=3:continue
        if not re.fullmatch(r'case_\d{3}',r['case']) or not 1<=r['n']<=5:raise ValueError('Invalid Q3 target in manifest')
        key=r['case'],r['n']
        if key in seen:raise ValueError('Repeated Q3 target in base manifest')
        seen.add(key)
        for f in ('plan','q3_result','no_l2_result','no_l2_plan'):
            if r.get(f):
                r[f]=resolve(r[f],p.parent)
                if not r[f]:raise FileNotFoundError(f'Missing {f} for {key}')
        if not r.get('plan'):raise ValueError('A real plan path is required')
        for f in ('old_makespan','old_added_copy_bytes','reference_t1','old_q2_best'):
            if r.get(f) not in (None,''):r[f]=int(float(r[f]))
            else:r[f]=None
        out.append(r)
    return out


def published(destination,proposal=PROPOSAL):
    """Extract 500 lightweight final plans only, never arbitrary archive paths."""
    dest=Path(destination);by={};notes=[];proposal=Path(proposal)
    archive=proposal/'问题三_优化计划_500组.tar.xz';table=proposal/'selected_results.csv'
    if archive.is_file() and table.is_file():
        scores={(r['case'],int(r['cores'])):r for r in csv_read(table)}
        with tarfile.open(archive,'r:xz') as tar:
            for member in tar:
                m=re.search(r'(?:^|/)n([1-5])/(case_\d{3})_multicore_res\.json$',member.name)
                if not m or not member.isfile():continue
                n,c=int(m[1]),m[2];f=tar.extractfile(member)
                import json
                plan=json.loads(f.read().decode('utf-8-sig'))
                if set(plan)!={'node_to_subgraph','core_schedules'} or len(plan['core_schedules'])!=n:raise ValueError('Malformed published plan')
                path=dest/'portfolio'/f'n{n}'/f'{c}.json';write(path,plan);row=scores.get((c,n))
                by.setdefault((c,n),[]).append({'path':str(path.resolve()),'name':'portfolio_published',
                  'makespan':int(row['makespan']) if row else None,'source':'workshop_v1_portfolio_archive'})
    else:notes.append('Portfolio archive/table unavailable: no portfolio scores/plans fabricated; new construction is optional.')
    v1=ROOT/'L2提升/orion_20260926/incumbents_v1/jobs'
    for p in v1.glob('case_*_q3_n*/plan.json'):
        key=target(p)
        if not key:continue
        s=read(p.parent/'summary.json') if (p.parent/'summary.json').is_file() else {}
        by.setdefault((key[0],key[2]),[]).append({'path':str(p.resolve()),'name':'v1_published',
           'makespan':s.get('makespan',s.get('selected_makespan')),'source':'orion_strong_start_v1'})
    if not v1.exists():notes.append('Published v1 plan directory unavailable; adapted weak-unit proposals remain available.')
    for items in by.values():items.sort(key=lambda x:(x.get('makespan') is None,x.get('makespan') or 0,x['name']))
    return by,notes
