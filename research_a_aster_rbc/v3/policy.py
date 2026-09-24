"""Fixed input-structural construction policy; no case-name exceptions."""
from __future__ import annotations
import math
from . import algorithms as A
from .model import make_plan
from .quality import view, bound_and_proxy, neighbors

VERSION="aster-v3-release-affinity-4.1"


def profile(g,n,cfg):
    component={u:i for i,c in enumerate(g.components) for u in c}
    shared=0.;replicated=0.
    for t in g.tensors:
        if g.ps[t]:continue
        touched={component[u] for u in g.cs[t]}
        if len(touched)>1:
            shared+=g.tensors[t]['size']
            replicated+=g.tensors[t]['size']*(min(n,len(touched))-1)
    work=max(g.work,default=0);depth=max(g.depth.values(),default=0)
    independent=(len(g.components)>1 and depth<48 and max((sum(g.loads(c)) for c in g.components),default=0)<=1.3*sum(g.work)/n)
    junction=(depth>512 and len(g.components)<n)
    pressure=replicated/cfg['bandwidth']/max(1.,work/n)
    active=min(n,max(2,int(round(math.sqrt(work*cfg['bandwidth']/max(1,shared))))))
    return dict(independent=independent,junction=junction,replicated_input_pressure=pressure,
                shared_input_bytes=shared,suggested_active_cores=active)


def _base_recipes(g,n,q,cfg):
    """Lazy recipes: descriptor generation does not score dozens of plans."""
    f=profile(g,n,cfg);seen=set()
    def spec(kind,active=None,**kw):return dict(kind=kind,active=active or n,**kw)
    if n==1:yield spec('component');return
    if f['independent']:
        queue=[spec('component'),spec('wave',width=4),spec('wave',width=1)]
    elif f['junction']:
        queue=[spec('junction'),spec('junction',active=n-1),spec('junction',pack=False),spec('junction',active=max(2,n-2))]
    elif len(g.components)<n:
        first=spec('dp',penalty=.5) if len(g.ids)<=5000 else spec('stage',stages=4)
        queue=[first]+[spec('stage',stages=s) for s in ((2,4,8,16) if q==1 else (4,16,8,2))]
        queue += [spec('junction'),spec('stage',active=max(2,n-1),stages=2)]
    elif f['replicated_input_pressure']>1.5:
        a=f['suggested_active_cores']
        if q==1:
            queue=[spec('stage',active=a,stages=2),spec('stage',active=a,stages=4),
                   spec('stage',stages=8),spec('stage',active=min(n,a+1),stages=2),spec('dp',active=a,penalty=2.)]
        else:
            queue=[spec('pipeline',stages=n,batch=2,fine=True),spec('pipeline',stages=n,batch=4,fine=True),
                   spec('stage',stages=8),spec('pipeline',stages=2,batch=4,fine=True),
                   spec('pipeline',stages=n,batch=2,fine=True,frontier=True),spec('stage',active=a,stages=4)]
    else:
        queue=[spec('stage',stages=8),spec('stage',stages=4),spec('dp',penalty=2.),
               spec('stage',stages=16),spec('component'),spec('wave',width=4)]
    if len(g.components)>1 and not f['independent']:
        queue.insert(1,spec('component'))
    for r in queue:
        key=tuple(sorted(r.items()))
        if key not in seen:seen.add(key);yield r


def _base_build(g,n,q,cfg,spec):
    kind=spec['kind'];k=spec['active']
    if kind=='component':p=A.locality_waves(g,k,None)
    elif kind=='wave':p=A.locality_waves(g,k,spec['width'])
    elif kind=='junction':p=A.junction_plan(g,k,cfg,q,pack=spec.get('pack',True))
    elif kind=='stage':p=A.stage_plan(g,k,cfg,q,stages=spec['stages'])
    elif kind=='dp':p=A.dp_stage_plan(g,k,cfg,q,penalty=spec['penalty'])
    elif kind=='pipeline':p=A.pipeline_plan(g,k,cfg,q,stages=spec['stages'],batch=spec['batch'],fine=spec.get('fine',False),frontier=spec.get('frontier',False))
    elif kind=='serial':p=make_plan([g.order],[0],k)
    else:raise ValueError(kind)
    p['core_schedules'] += [[] for _ in range(n-k)]
    return p


def recipes(g,n,q,cfg):
    """Prioritise measured mechanism improvements; retain the legacy first plan.

    No case-name rules. Full mode is the deployment default, not a grid of runs.
    """
    legacy=list(_base_recipes(g,n,q,cfg))
    if n == 1 or q == 1:
        yield from legacy
        return
    from .enhancements import release_frontier
    f=profile(g,n,cfg)
    extra=[]
    if f['junction']:
        extra=[dict(kind='release',active=n),dict(kind='release',active=max(2,n-1))]
    elif f['shared_input_bytes']>cfg['capacity']['UB'] and max(g.depth.values(),default=0)>=64 and len(g.components)>=n:
        extra=[dict(kind='affinity',active=n,batch=1),
               dict(kind='affinity',active=n,batch=1,io_weight=.5),
               dict(kind='ordered_stage',active=n,stages=8),
               dict(kind='ordered_stage',active=n,stages=4)]
    elif len(g.components)<n:
        extra=[dict(kind='ordered_stage',active=n,stages=4),
               dict(kind='release',active=n)]
    sequence=legacy[:1]+extra+legacy[1:]
    seen=set()
    for item in sequence:
        key=tuple(sorted(item.items()))
        if key not in seen:
            seen.add(key)
            yield item


def build(g,n,q,cfg,spec):
    from .enhancements import release_frontier,affinity_pipeline,export_split
    kind=spec['kind']; k=spec['active']
    if kind=='release': p=release_frontier(g,k,q,cfg)
    elif kind=='affinity': p=affinity_pipeline(g,k,q,cfg,batch=spec.get('batch',1),io_weight=spec.get('io_weight',1.))
    elif kind=='ordered_stage':
        p=A.stage_plan(g,k,cfg,q,stages=spec['stages'],pack=False)
    else: return _base_build(g,n,q,cfg,spec)
    p['core_schedules'] += [[] for _ in range(n-k)]
    return p
