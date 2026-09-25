"""Collect actual published plans; recorded labels never replace target evaluation."""
from __future__ import annotations
from collections import defaultdict
from pathlib import Path
import re
from .io import ROOT, read, plan_key


def _case(value):
    if value is None:return None
    m=re.search(r'(?:case_)?(\d{3})(?:\D|$)',str(value))
    return 'case_'+m[1] if m else None


def _key(path):
    text=Path(path).as_posix()
    m=re.search(r'/q([0-3])/n([1-5])/(case_\d{3})_multicore_res\.json$',text)
    if m:return m[3],int(m[1]),int(m[2])
    matches=re.findall(r'(case_\d{3})_q([0-3])_n([1-5])',text)
    if matches:
        case,q,n=matches[-1];return case,int(q),int(n)
    return None


def _resolve(value, origin):
    if not value:return None
    p=Path(str(value))
    for candidate in (p,ROOT/p,origin.parent/p):
        if candidate.is_file():return candidate.resolve()
    return None


def catalogue(extra_roots=()):
    roots=[ROOT/'research_a_orion_track_anytime/results',
           ROOT/'research_a_orion_track_structure/results',
           ROOT/'research_a_orion_track_memory/results',
           ROOT/'research_a_orion_fusion/evidence/seed_plans',
           ROOT/'research_a_orion_fusion/runs/installed_seeds']
    roots.extend(Path(x).resolve() for x in extra_roots)
    entries=defaultdict(list); seen=defaultdict(set); missing=[]
    def add(key,path,origin,recorded=None):
        if not key or key[1]==0:return
        if not path or not path.is_file():
            missing.append({'key':key,'source':str(origin),'reason':'declared_plan_not_local'})
            return
        try:
            p=read(path)
            if set(p)!={'node_to_subgraph','core_schedules'}:return
            if len(p['core_schedules'])!=key[2]:return
            sig=plan_key(p)
            if sig in seen[key]:return
            seen[key].add(sig)
            entries[key].append({'path':str(path.resolve()),'name':'published_seed',
                                 'source':str(origin),'recorded_makespan':recorded})
        except (ValueError,KeyError,TypeError,OSError):return
    for root in roots:
        if not root.exists():continue
        files=[root] if root.is_file() else root.rglob('*.json')
        for p in files:
            if {'attempts','official_calls','failures'} & set(p.parts):continue
            key=_key(p)
            if key and (p.name.endswith('_multicore_res.json') or re.fullmatch(r'case_\d{3}_q[0-3]_n[1-5]\.json',p.name)):
                add(key,p,p)
            elif p.name=='plan.json' and key and p.parent.name=='selected' and 'pairs' not in p.parts:
                summary=p.parent.parent/'summary.json'
                d=read(summary) if summary.is_file() else {}
                if d.get('status')=='ok':add(key,p,summary,d.get('makespan'))
            elif p.name=='SOURCE.json' and (p.parent/'plan.json').is_file():
                d=read(p);case=_case(d.get('case'))
                if not case:
                    case=next((_case(x) for x in reversed(p.parts[:-1]) if re.fullmatch(r'(?:case_)?\d{3}',x)),None)
                if case and 'q' in d and 'n' in d:add((case,int(d['q']),int(d['n'])),p.parent/'plan.json',p,d.get('makespan'))
            elif p.name in ('AVAILABLE_SEEDS.json','next_seed_manifest.json','seed_manifest.json','SEED_INDEX.json'):
                d=read(p);rows=d if isinstance(d,list) else d.get('seeds',d.get('entries',d.get('rows',[])))
                if isinstance(rows,dict):rows=list(rows.values())
                for row in rows:
                    if not isinstance(row,dict):continue
                    case=_case(row.get('case'));q=row.get('q');n=row.get('n')
                    if case and q is not None and n is not None:
                        value=row.get('plan_file',row.get('plan',row.get('path')))
                        add((case,int(q),int(n)),_resolve(value,p),p,
                            row.get('recorded_makespan',row.get('makespan')))
    for key,rows in entries.items():
        rows.sort(key=lambda x:(x['recorded_makespan'] is None,x['recorded_makespan'] or 0,x['path']))
    return dict(entries),missing
