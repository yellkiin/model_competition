"""An overlay of Q3 records; Q1/Q2 are never rewritten or reconstructed."""
from __future__ import annotations
from pathlib import Path
from collections import defaultdict
from statistics import mean
import math,shutil
from .common import read,write,csv_write,plan_key


def finish(req,execution):
    folder=Path(req['out']);p=folder/'progress.json';s=read(p) if p.is_file() else {}
    base=s.get('baseline');best=s.get('best');chosen=None;changed=False
    if base:
        gain=1-best['makespan']/base['makespan'] if best else 0.
        if best and gain>=req['min_gain'] and plan_key(read(folder/best['plan']))!=plan_key(read(folder/base['plan'])):
            chosen=best;changed=True
        else:chosen=base
    row={'case':req['case'],'q':3,'n':req['n'],'backend':req['backend'],'base_method':'Trident #38',
         'status':'ok' if chosen else ('retained_existing' if execution.get('reason')=='no_material_published_candidate' else 'old_record_retained_no_new_result'),'changed':changed,
         'old_makespan':base['makespan'] if base else req.get('old_makespan'),
         'makespan':chosen['makespan'] if chosen else req.get('old_makespan'),
         'selected_name':chosen['name'] if chosen else 'existing_record',
         'added_copy_bytes':chosen['added_copy_bytes'] if chosen else req.get('old_added_copy_bytes'),
         'raw_best_makespan':best['makespan'] if best else None,'reference_t1':req.get('reference_t1'),
         'old_q2_best':req.get('old_q2_best'),'search_policy':req['policy'],'minimum_gain':req['min_gain'],
         'pair_status':'pending','execution':execution,'attempts':len(s.get('attempts',[])),
         'new_q3_calls':sum(a.get('status')=='ok' and not a.get('reused') for a in s.get('attempts',[])),
         'notes':s.get('notes',[]),'worker_error':s.get('error')}
    if chosen:
        write(folder/'plan.json',read(folder/chosen['plan']));shutil.copyfile(folder/chosen['response'],folder/'result.json.gz')
        row.update(plan='plan.json',result='result.json.gz')
        raw=read(folder/'result.json.gz')['official_result'];row['cache_hit_rate']=raw.get('cache_stats',{}).get('hit_rate')
        row.update(raw.get('data_movement_bytes',{}));row['lower']=chosen.get('certificate',{}).get('global_lower')
    else:
        row.update(plan=req['plan'],result=req.get('q3_result'))
        if req.get('q3_result'):
            raw=read(req['q3_result']);raw=raw.get('official_result',raw)
            if raw.get('problem')!=3 or raw.get('num_cores')!=req['n'] or (row['old_makespan'] is not None and raw.get('makespan')!=row['old_makespan']):
                raise ValueError('Inherited Q3 metadata conflicts with the selected old record')
            row.update(makespan=raw['makespan'],old_makespan=raw['makespan'],cache_hit_rate=raw.get('cache_stats',{}).get('hit_rate'))
            row.update(raw.get('data_movement_bytes',{}))
    if row['old_makespan'] and row['makespan']:row['time_reduction']=1-row['makespan']/row['old_makespan']
    pair=s.get('pair') or {}
    if pair.get('status')=='ok' and chosen and (folder/pair['plan']).is_file():
        if plan_key(read(folder/pair['plan']))==plan_key(read(folder/'plan.json')):
            row.update(pair_status='ok',no_l2_makespan=pair['makespan'],no_l2_added_copy_bytes=pair['added_copy_bytes'],
                       pair_reused=pair.get('reused',False),new_pair_seconds=pair.get('new_evaluation_seconds'),
                       same_plan_cache_ratio=pair['makespan']/row['makespan'])
    if not changed and row['pair_status']!='ok' and req.get('no_l2_result') and req.get('no_l2_plan'):
        if plan_key(read(req['no_l2_plan']))==plan_key(read(req['plan'])):
            pr=read(req['no_l2_result']);raw=pr.get('official_result',pr)
            if raw.get('scene')=='B' and raw.get('problem')!=3 and raw.get('num_cores')==req['n'] and raw.get('makespan') and row.get('makespan'):
                row.update(pair_status='inherited_exact_plan',pair_reused=True,no_l2_makespan=raw['makespan'],
                    no_l2_added_copy_bytes=raw['data_movement_bytes']['added_copy_bytes'],
                    same_plan_cache_ratio=raw['makespan']/row['makespan'],existing_pair_reference=req['no_l2_result'])
    write(folder/'summary.json',row);return row


def collect(roots,out,q2_threshold=.03):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);records={};trajectory=[];attempts=[];expected=set();policies=set();missing_base=[]
    for root in map(Path,roots):
        if (root/'campaign.json').is_file():
            c=read(root/'campaign.json');policies.add((c['backend'],c['seconds'],c['min_gain'],c['policy']))
            expected.update((x['case'],x['n']) for x in c['records']);missing_base.extend(c.get('missing_base_keys',[]))
        for p in sorted(root.glob('jobs/case_*_q3_n*/summary.json')):
            s=read(p);key=s['case'],s['n']
            if key in records:raise ValueError('Duplicate patch key; do not select post-hoc best across runs: '+str(key))
            records[key]=s
            r={k:v for k,v in s.items() if not isinstance(v,(dict,list))};r['wall_seconds']=s['execution'].get('wall_seconds')
            if r.get('reference_t1') and r.get('makespan'):r['speedup']=r['reference_t1']/r['makespan']
            records[key]=r
            if (p.parent/'progress.json').is_file():
                st=read(p.parent/'progress.json');events=st.get('events',[]);end=s['execution'].get('wall_seconds',st.get('elapsed_seconds',0))
                for t in range(0,601,30):
                    ev=[e for e in events if e['seconds']<=min(t,end)];best=ev[-1] if ev else None
                    raw=best['makespan'] if best else None;published=r.get('old_makespan')
                    if raw and published and 1-raw/published>=r['minimum_gain']:published=raw
                    trajectory.append({'case':s['case'],'n':s['n'],'seconds':t,'search_best':raw,
                         'published_if_stopped':published,'source':best['name'] if best else None,
                         'kind':'held_after_stop' if t>end else 'observed','wall_seconds':end})
                attempts.extend({'case':s['case'],'n':s['n'],**{k:v for k,v in a.items() if k!='traceback'}} for a in st.get('attempts',[]))
    if len(policies)>1:raise ValueError('Different patch policies; report separate experiments')
    rows=list(records.values());changes=[r for r in rows if r['changed']];transfer=[]
    for r in changes:
        if r.get('no_l2_makespan') and r.get('old_q2_best') and 1-r['no_l2_makespan']/r['old_q2_best']>=q2_threshold:
            transfer.append({**r,'q2_candidate_gain':1-r['no_l2_makespan']/r['old_q2_best'],
                             'action':'Existing same-plan Q2 result is a transfer candidate; no Q2 search or automatic replacement.'})
    curves=[]
    for n in range(1,6):
        rs=[r for r in rows if r['n']==n];vals=[r['speedup'] for r in rs if r.get('speedup')]
        curves.append({'n':n,'records':len(rs),'changed':sum(r['changed'] for r in rs),
          'speedup_denominator_count':len(vals),'mean_speedup':mean(vals) if vals else None,
          'mean_old_to_new_ratio':mean([r['old_makespan']/r['makespan'] for r in rs if r.get('makespan') and r.get('old_makespan')]) if any(r.get('makespan') and r.get('old_makespan') for r in rs) else None,
          'verified_pair_count':sum(r['pair_status'] in ('ok','inherited_exact_plan') for r in rs)})
    csv_write(out/'q3_overlay.csv',rows);csv_write(out/'changes_only.csv',changes);csv_write(out/'curves.csv',curves)
    csv_write(out/'time_quality_30s.csv',trajectory);csv_write(out/'attempts.csv',attempts)
    csv_write(out/'q2_transfer_opportunities.csv',transfer)
    report={'q1_q2_searches':0,'records':len(rows),'changed':len(changes),'retained':len(rows)-len(changes),
        'new_q3_successful_calls':sum(r['new_q3_calls'] for r in rows),
        'new_no_l2_pairs':sum(r['pair_status']=='ok' and not r.get('pair_reused') for r in rows),
        'reused_pairs':sum(bool(r.get('pair_reused')) for r in rows),
        'pending_pairs':[(r['case'],r['n']) for r in rows if r['pair_status'] not in ('ok','inherited_exact_plan')],
        'missing_patch_keys':sorted(expected-set(records)),'missing_base_keys':sorted(missing_base),'q2_transfer_candidates':len(transfer),
        'scope':'supplemental Q3 overlay; not a new full Q1/Q2 experiment','full_q3_500':len(rows)==500 and not missing_base,
        'retained_original_rows_without_new_validation':sum(r['status']=='retained_existing' for r in rows),
        'local_errors':[{'case':r['case'],'n':r['n'],'status':r['status']} for r in rows if r['status'] not in ('ok','retained_existing')],
        'publication_threshold':next(iter(policies))[2] if policies else None}
    write(out/'report.json',report);return report
