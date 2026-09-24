"""Re-audit saved results and export official two-field plans without original data."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from .core import Graph, Config, fingerprint
from .run import read_json, locate_official, file_hash, collect
from .worker import audit, atomic_json


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--roots',nargs='+',required=True);p.add_argument('--official');p.add_argument('--out',required=True)
    p.add_argument('--require-complete',action='store_true')
    a=p.parse_args(argv);official,config=locate_official(a.official);cfg=Config.read(config)
    dest=Path(a.out).resolve(); rows=[]; sources={}; cache={}
    # collect refuses conflicting duplicates before any export.
    report=collect(a.roots,dest/'report')
    for root in a.roots:
        for path in sorted(Path(root).glob('jobs/*/summary.json')):
            s=read_json(path);key=(s['case'],s['q'],s['n'],s['mode'])
            if s['status']!='ok' or key in sources:continue
            gp=official/'data'/(s['case']+'.json')
            if file_hash(gp)!=s['identity']['graph_sha256'] or file_hash(config)!=s['identity']['config_sha256']:
                raise ValueError('Original graph/config differ from experiment record')
            if s['case'] not in cache:cache[s['case']]=Graph(read_json(gp))
            g=cache[s['case']];plan=read_json(path.parent/'plan.json');best=read_json(path.parent/'best.json')
            if fingerprint(plan)!=s['plan_hash']:raise ValueError('Plan identity mismatch')
            check=audit(g,plan,best['official_result'],s['q'],cfg)
            if not check['ok']:raise ValueError(f'Reaudit failed: {key}: {check}')
            target=dest/'plans'/s['mode']/f"q{s['q']}"/f"n{s['n']}"/(s['case']+'_multicore_res.json')
            atomic_json(target,plan); sources[key]=path
            paired_ok=None
            if s['q']==3:
                paired=path.parent/'same_plan_no_l2.json'
                if paired.is_file() and (r:=read_json(paired))['status']=='ok':
                    paired_ok=audit(g,plan,r['official_result'],2,cfg)['ok']
                    if s.get('paired_plan_hash')!=s['plan_hash']:raise ValueError('Counterfactual plan mismatch')
            rows.append({'case':s['case'],'q':s['q'],'n':s['n'],'mode':s['mode'],'audit_ok':True,
                         'paired_audit_ok':paired_ok,'plan_sha256':s['plan_hash'],'certificate':check['certificate']})
    required={(f'case_{i:03d}',q,n) for i in range(1,101) for q in (1,2,3) for n in (2,3,4,5)}
    required|={(f'case_{i:03d}',0,1) for i in range(1,101)}
    required|={(f'case_{i:03d}',3,1) for i in range(1,101)}
    if a.require_complete and len({r['mode'] for r in rows}) != 1:
        raise ValueError('Formal export requires one fixed algorithm mode, not a mixture of experiment modes')
    present={(r['case'],r['q'],r['n']) for r in rows}
    missing=sorted(required-present)
    pair_missing=[(r['case'],r['n']) for r in rows if r['q']==3 and r['paired_audit_ok'] is not True]
    result={'rows':rows,'formal_required_missing':missing,'cache_counterfactual_missing':pair_missing,
            'formal_complete':not missing and not pair_missing,
            'scope':'official results independently re-audited; private-memory peaks remain official fields'}
    atomic_json(dest/'verification.json',result)
    print(json.dumps({'reaudited':len(rows),'formal_complete':result['formal_complete'],
                      'formal_missing_count':len(missing),'paired_missing_count':len(pair_missing)},indent=2))
    return 1 if a.require_complete and not result['formal_complete'] else 0

if __name__=='__main__':raise SystemExit(main())
