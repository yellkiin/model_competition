from pathlib import Path
import csv,gzip,json,statistics,collections,sys

ROOT=Path(r'E:\20hw_myskill_distribution\workshop_v1')
OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'数据/原始/A题官方附件/code'))
from schedule_step3 import _build_graph_views

def read_csv(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

rows=[]
for base in read_csv(ROOT/'求解/正式实验/逐例分析.csv'):
    if int(base['cores'])!=5:continue
    case=base['case']; cand=base['q3_candidate']
    p=ROOT/'求解/正式实验/候选评估'/case/'n5'/cand/'q3.json.gz'
    with gzip.open(p,'rt',encoding='utf-8') as f:r=json.load(f)
    graph=json.loads((ROOT/'数据/原始/A题官方附件/data'/f'{case}.json').read_text(encoding='utf-8'))
    pipe_totals=collections.Counter(); fixed_compute_lb=0; core_compute=[]
    for core in r['per_core_timeline']:
        pipe=collections.Counter()
        for op in core['ops']:
            if op['op'] not in ('COPY_IN','COPY_OUT'):
                pipe[op['pipe']]+=op['duration'];pipe_totals[op['pipe']]+=op['duration']
        v=max(pipe.values(),default=0);core_compute.append(v);fixed_compute_lb=max(fixed_compute_lb,v)
    # Free reassignment lower bound: aggregate per-pipe original compute and zero-copy DAG critical path.
    lb_total=max(pipe_totals.values(),default=0)/5
    _,_,preds,succs=_build_graph_views(graph['ops'],graph['edges'])
    ops={o['id']:o for o in graph['ops']};pending={k:len(v) for k,v in preds.items()}
    ready=collections.deque(k for k,v in pending.items() if not v);ends={};critical=0
    while ready:
        oid=ready.popleft();o=ops[oid]
        dur=0 if o['op'] in ('COPY_IN','COPY_OUT') else max(1,o['cycles'])
        ends[oid]=max((ends[i] for i in preds[oid]),default=0)+dur;critical=max(critical,ends[oid])
        for nxt in succs[oid]:
            pending[nxt]-=1
            if not pending[nxt]:ready.append(nxt)
    assert len(ends)==len(ops)
    global_compute_lb=max(lb_total,critical)
    seen=collections.Counter();seen_cores=collections.defaultdict(set);key_size={};first_insert={}
    repeat_miss_bytes=0;race_miss_bytes=0;compulsory_miss_bytes=0;first_core_hit_bytes=0;same_core_repeat_hit_bytes=0
    for e in r['cache_events']:
        key=e['tensor_id'];size=e['size_bytes'];time=e['time']
        if e['event']=='insert':
            first_insert.setdefault(key,time);continue
        if e['event'] not in ('hit','miss'):continue
        core=e['core_id'];key_size[key]=size
        if e['event']=='miss':
            if not seen[key]:compulsory_miss_bytes+=size
            elif key not in first_insert:race_miss_bytes+=size
            else:repeat_miss_bytes+=size
        elif core not in seen_cores[key]:first_core_hit_bytes+=size
        else:same_core_repeat_hit_bytes+=size
        seen[key]+=1;seen_cores[key].add(core)
    read_bytes=r['cache_stats']['hit_bytes']+r['cache_stats']['miss_bytes']
    compulsory=sum(key_size.values());reuse=read_bytes-compulsory
    movement=r['data_movement_bytes'];write_bytes=movement['scheduled_copy_bytes']-read_bytes
    assert write_bytes>=0
    # Relaxed fixed-plan bound, even with arbitrarily successful retention and timing:
    # per-core compute; compulsory read plus all write DDR volume; remaining read L2 volume.
    # Using compulsory-only DDR bound and ALL reads / combined bandwidth gives valid relaxations.
    cold_ddr_lb=(compulsory+write_bytes)/60
    both_read_lb=(read_bytes+write_bytes)/(60+250)
    fixed_relaxed_lb=max(fixed_compute_lb,cold_ddr_lb,both_read_lb)
    T=r['makespan'];T0=int(base['q3_matched_no_l2_cycles'])
    row=dict(case=case,candidate=cand,T_no_l2=T0,T_l2=T,actual_time_reduction=1-T/T0,
      hit_rate=r['cache_stats']['hit_rate'],read_bytes=read_bytes,write_bytes=write_bytes,
      compulsory_read_bytes=compulsory,reuse_byte_fraction=reuse/read_bytes if read_bytes else 0,
      compulsory_miss_bytes=compulsory_miss_bytes,race_miss_bytes=race_miss_bytes,repeated_miss_bytes=repeat_miss_bytes,
      first_access_in_core_hit_bytes=first_core_hit_bytes,same_core_repeat_hit_bytes=same_core_repeat_hit_bytes,
      max_core_compute_cycles=fixed_compute_lb,global_pipe_compute_lb=lb_total,zero_copy_critical_path=critical,
      global_compute_lb=global_compute_lb,current_compute_utilization=fixed_compute_lb/T,
      global_compute_lb_ratio=global_compute_lb/T,
      same_assignment_further_reduction_ceiling=1-fixed_compute_lb/T,
      any_assignment_reduction_ceiling=1-global_compute_lb/T,
      cold_ddr_lb=cold_ddr_lb,fixed_relaxed_lb=fixed_relaxed_lb,
      same_assignment_l2_total_reduction_ceiling_vs_no_l2=1-fixed_relaxed_lb/T0,
      spill_added_copy_bytes=movement['spill_added_copy_bytes'],partition_added_copy_bytes=movement['partition_added_copy_bytes'],
      core_compute_cycles=core_compute)
    rows.append(row)
with (OUT/'five_core_potential.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
summary={
    'n':len(rows),
    'actual_time_reduction_mean':statistics.mean(x['actual_time_reduction'] for x in rows),
    'compute_bound_ratios':{str(t):sum(x['global_compute_lb_ratio']>=t for x in rows) for t in (.8,.9,.95,.98,.99)},
    'fixed_assignment_compute_bound_ratios':{str(t):sum(x['current_compute_utilization']>=t for x in rows) for t in (.8,.9,.95,.98,.99)},
    'mean_global_compute_lb_ratio':statistics.mean(x['global_compute_lb_ratio'] for x in rows),
    'median_global_compute_lb_ratio':statistics.median(x['global_compute_lb_ratio'] for x in rows),
    'mean_fixed_compute_ratio':statistics.mean(x['current_compute_utilization'] for x in rows),
    'median_fixed_compute_ratio':statistics.median(x['current_compute_utilization'] for x in rows),
    'zero_hit_cases':sum(x['hit_rate']==0 for x in rows),
    'reuse_fraction_mean':statistics.mean(x['reuse_byte_fraction'] for x in rows),
    'read_totals':{k:sum(x[k] for x in rows) for k in ('read_bytes','write_bytes','compulsory_read_bytes','race_miss_bytes','repeated_miss_bytes','first_access_in_core_hit_bytes','same_core_repeat_hit_bytes')},
    'largest_optimistic_global_improvement':sorted(rows,key=lambda x:x['global_compute_lb_ratio'])[:20],
}
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in summary.items() if k!='largest_optimistic_global_improvement'},ensure_ascii=False,indent=2))
print('POTENTIAL',[(x['case'],round(x['global_compute_lb_ratio'],4),round(x['current_compute_utilization'],4),round(x['hit_rate'],4),x['candidate']) for x in summary['largest_optimistic_global_improvement']])
print('REPRESENTATIVE',[x for x in rows if x['case'] in ('case_001','case_002','case_044','case_050','case_056','case_083')])
