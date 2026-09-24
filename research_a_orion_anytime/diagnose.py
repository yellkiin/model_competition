"""Measured failure/proxy diagnostics; never automatically increases search budget."""
import argparse,json,statistics
from pathlib import Path
from .run import read_json
from .worker import atomic_json

def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('root');a=p.parse_args(argv)
    rows=[]
    for path in Path(a.root).glob('jobs/*/summary.json'):
        s=read_json(path);pred={c['plan_hash']:c['proxy'].get('score') for c in s.get('constructor_candidates',[])}
        evaluated=[x for x in s.get('attempts',[]) if x['status']=='ok']
        proxy_pairs=[(pred[x['plan_hash']],x['makespan']) for x in evaluated if pred.get(x['plan_hash'])]
        errors=[x for x in s.get('attempts',[]) if x['status'] not in ('ok','certified_pruned')]
        advice=[]
        if any(x['status']=='timeout' for x in errors):advice.append('TIMEOUT: rerun failed only with workers=1 in a new budget directory; do not globally enlarge search')
        if s.get('status') not in ('ok','not_started_budget'):advice.append('INVALID: read response traceback and construction errors; preserve official input/code; use construct alternative or one-core fallback in a new run')
        if s.get('spill_added_copy_bytes',0)>0:advice.append('SPILL: compare component_order versus component_pack; inspect live intervals and try frontier split; do not treat total Task bytes as peak')
        if s.get('q')==3 and s.get('cache_hit_rate',0) and s.get('cache_speedup',1)<1.01:advice.append('CACHE: hits are off critical path or readers issue before fill; use actual COPY issue/end records, not LRU assumptions')
        if len(evaluated)>=2 and evaluated[-1]['makespan']>=evaluated[0]['makespan']:advice.append('NO GAIN: compare best-so-far trajectory, improve the constructor or bottleneck neighbourhood; do not assume more evaluations are useful')
        disagreement=sum((x[0]-y[0])*(x[1]-y[1])<0 for i,x in enumerate(proxy_pairs) for y in proxy_pairs[i+1:])
        rows.append({'case':s['case'],'q':s['q'],'n':s['n'],'status':s['status'],'failed_attempts':errors,
                     'proxy_rank_disagreements_on_evaluated_constructors':disagreement,
                     'evaluated_constructor_count':len(proxy_pairs),'actions':advice})
    atomic_json(Path(a.root)/'diagnostics.json',{'rows':rows,'note':'Selection-biased evaluated subset; no claim of full proxy ranking accuracy.'})
    print(json.dumps(rows,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
