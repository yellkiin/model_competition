"""Structure-triggered continuation candidates for the independent Anytime track.

These candidates are deliberately narrow: they activate only when the observed
incumbent has a materially late core whose schedule is also structurally longer
than the other cores. No case identifier participates in the decision.
"""
from __future__ import annotations
from collections import defaultdict
import math
import statistics
import time


def propose_tail_rebalance(g, n, cfg, q, incumbent=None, deadline=None, limit=12):
    if not incumbent or n < 2:
        return
    from research_a_orion_anytime.core import plan_view, make_plan, estimate, bounds
    plan = incumbent['plan']
    raw = incumbent['official_result']
    mapping, groups, core, order = plan_view(g, plan)
    ends = []
    for k in range(n):
        timeline = next((c for c in raw.get('per_core_timeline', []) if c['core_id'] == k), None)
        ends.append(max((o['end'] for o in timeline['ops']), default=0) if timeline else 0)
    makespan = max(ends, default=0)
    if not makespan:
        return
    ranked = sorted(range(n), key=lambda k: (ends[k], -k), reverse=True)
    tail, second = ranked[0], ranked[1]
    seq_lens = [len(s) for s in plan['core_schedules']]
    median_len = statistics.median(seq_lens) if seq_lens else 0
    imbalance = (ends[tail] - ends[second]) / makespan
    schedule_ratio = seq_lens[tail] / max(1.0, median_len)
    if imbalance < 0.015 or (seq_lens[tail] < median_len + 8 and schedule_ratio < 1.5):
        return

    sg_end = {s: 0 for s in groups}
    timeline = next(c for c in raw['per_core_timeline'] if c['core_id'] == tail)
    for op in timeline['ops']:
        s = op.get('subgraph_id')
        if s in sg_end:
            sg_end[s] = max(sg_end[s], op['end'])
    late = sorted(plan['core_schedules'][tail], key=lambda s: (sg_end.get(s, 0), s), reverse=True)[:8]
    light = sorted((k for k in range(n) if k != tail), key=lambda k: (ends[k], k))[:2]
    base_cores = [core[s] for s in order]
    seen = set()
    emitted = 0

    def emit(groups_order, placements, name, family, evidence):
        nonlocal emitted
        p = make_plan(groups_order, placements, n)
        key = (tuple(sorted((int(u), s) for u, s in p['node_to_subgraph'].items())),
               tuple(tuple(x) for x in p['core_schedules']))
        if key in seen:
            return None
        seen.add(key)
        try:
            plan_view(g, p)
        except ValueError:
            return None
        emitted += 1
        return dict(name=name, family='anytime/'+family, plan=p,
                    proxy=estimate(g, p, cfg, q), bounds=bounds(g, cfg, n, q, p),
                    evidence=evidence)

    ordered_groups = [groups[s] for s in order]
    position = {s: i for i, s in enumerate(order)}
    batch = []
    for s in late[:5]:
        for dst in light:
            if deadline is not None and time.monotonic() >= deadline:
                return
            placements = list(base_cores)
            placements[position[s]] = dst
            ev = dict(trigger='observed_tail_imbalance', tail_core=tail, target_core=dst,
                      imbalance=imbalance, tail_schedule_len=seq_lens[tail],
                      median_schedule_len=median_len, subgraph=s, subgraph_end=sg_end.get(s, 0),
                      case_specific=False)
            c = emit(ordered_groups, placements,
                     f'tail_rebalance_s{s}_c{tail}_to{dst}', 'struct_tail_move', ev)
            if c:
                batch.append(c)
            if emitted >= min(limit, 10):
                break
        if emitted >= min(limit, 10):
            break
    batch.sort(key=lambda c: (c['proxy'].get('score', float('inf')), c['name']))
    for c in batch:
        yield c

    for s in late[:4]:
        if deadline is not None and time.monotonic() >= deadline:
            return
        if len(groups[s]) <= 1:
            continue
        parts = g.split(groups[s], cfg, q)
        if len(parts) <= 1:
            continue
        for dst in light[:1]:
            expanded, placements = [], []
            for v in order:
                if v != s:
                    expanded.append(groups[v]); placements.append(core[v])
                else:
                    for j, part in enumerate(parts):
                        expanded.append(part); placements.append(dst if j % 2 else tail)
            ev = dict(trigger='observed_tail_imbalance_split', tail_core=tail, target_core=dst,
                      imbalance=imbalance, tail_schedule_len=seq_lens[tail],
                      median_schedule_len=median_len, subgraph=s, parts=len(parts), case_specific=False)
            c = emit(expanded, placements, f'tail_split_s{s}_c{tail}_c{dst}', 'struct_tail_split', ev)
            if c:
                yield c
            if emitted >= limit:
                return


def _private_island_features(g, cfg, q, incumbent):
    """Detect many independent micro-components without using case IDs."""
    from research_a_orion_anytime.core import bounds
    component_of = {u:i for i, comp in enumerate(g.components) for u in comp}
    shared = private = 0
    for t, tensor in g.tensors.items():
        consumers = g.tc[t]
        if g.tp[t] or not consumers:
            continue
        size = int(tensor['size'])
        if len({component_of[u] for u in consumers}) > 1:
            shared += size
        else:
            private += size
    tiny = [comp for comp in g.components if len(comp) <= 32]
    tiny_fraction = sum(map(len, tiny))/max(1,len(g.ops))
    lower = float(bounds(g,cfg,len(incumbent['plan']['core_schedules']),q)['global_lower'])
    upper = float(incumbent['official_result']['makespan'])
    return dict(components=len(g.components), tiny_fraction=tiny_fraction,
                shared_input_bytes=shared, private_input_bytes=private,
                ratio=upper/lower if lower else math.inf,
                private_islands=(len(g.components)>=8 and tiny_fraction>=.75 and
                                 shared < .10*max(1,private)))


def _component_live_peak(g, component):
    seq=[u for u in g.topo if u in component]
    index={u:i for i,u in enumerate(seq)}
    events=defaultdict(lambda:defaultdict(int))
    touched=set().union(*(g.inputs[u] | g.outputs[u] for u in seq)) if seq else set()
    for t in touched:
        tensor=g.tensors[t]; pos=tensor.get('pos')
        if pos not in ('L1','UB'):
            continue
        pins=(g.tp[t] | g.tc[t]) & component
        if not pins:
            continue
        a=min(index[u] for u in pins); b=max(index[u] for u in pins); size=int(tensor['size'])
        events[a][pos]+=size; events[b+1][pos]-=size
    live=defaultdict(int); peak=defaultdict(int)
    for i in sorted(events):
        for pos,delta in events[i].items():
            live[pos]+=delta; peak[pos]=max(peak[pos],live[pos])
    return dict(peak)


def _balanced_component_owners(g, plan, n):
    from research_a_orion_anytime.core import plan_view
    mapping,_,owner,_=plan_view(g,plan)
    assigned={}; loads=[defaultdict(int) for _ in range(n)]
    for comp in sorted(g.components,key=lambda c:(-g.weight(c),min(c))):
        work=g.loads(comp); old=defaultdict(int)
        for u in comp:
            old[owner[mapping[u]]] += g.duration[u]
        def score(core):
            worst=0
            for k in range(n):
                for pipe in set(loads[k]) | (set(work) if k==core else set()):
                    value=loads[k].get(pipe,0)+(work.get(pipe,0) if k==core else 0)
                    worst=max(worst,value)
            return (worst,-old[core],core)
        dest=min(range(n),key=score); assigned[min(comp)]=dest
        for pipe,value in work.items():
            loads[dest][pipe]+=value
    return assigned


def _micro_wave_plan(g, plan, cfg, n, envelope=2.0, stages=2):
    from research_a_orion_anytime.core import make_plan
    components=sorted(g.components,key=min)
    owners=_balanced_component_owners(g,plan,n)
    peaks=[_component_live_peak(g,c) for c in components]
    max_peak={pos:max((p.get(pos,0) for p in peaks),default=0) for pos in cfg.capacity}
    safe=min((cfg.capacity[pos]/max(1,max_peak[pos]) for pos in cfg.capacity),default=1.0)
    width=max(1,int(max(1.0,safe*envelope)))
    assigned=[[] for _ in range(n)]
    for comp in components:
        assigned[owners[min(comp)]].append(comp)
    groups=[]; cores=[]
    for core in range(n):
        comps=assigned[core]
        for start in range(0,len(comps),width):
            batch=comps[start:start+width]; depths={}
            for comp in batch:
                depth={}
                for u in g.topo:
                    if u in comp:
                        depth[u]=1+max((depth[p] for p in g.pred[u] if p in comp),default=-1)
                depths[min(comp)]=depth
            for stage in range(stages):
                part=set()
                for comp in batch:
                    depth=depths[min(comp)]; levels=max(depth.values(),default=0)+1
                    for u,d in depth.items():
                        if min(stages-1,d*stages//max(1,levels))==stage:
                            part.add(u)
                if part:
                    groups.append(part); cores.append(core)
    return make_plan(groups,cores,n)


def propose_private_island_wave(g,n,cfg,q,incumbent=None,deadline=None):
    """One conservative component-wave candidate for Q2/Q3 private islands."""
    if not incumbent or q not in (2,3):
        return
    from research_a_orion_anytime.core import plan_view,estimate,bounds
    features=_private_island_features(g,cfg,q,incumbent)
    if not features['private_islands'] or features['ratio'] <= 1.08:
        return
    if deadline is not None and time.monotonic() >= deadline:
        return
    plan=_micro_wave_plan(g,incumbent['plan'],cfg,n,2.0,2)
    try:
        plan_view(g,plan)
    except ValueError:
        return
    yield dict(name='private_island_micro_wave_e2_s2', family='anytime/struct_private_wave',
               plan=plan, proxy=estimate(g,plan,cfg,q), bounds=bounds(g,cfg,n,q,plan),
               evidence=dict(trigger='private_islands',components=features['components'],
                             tiny_fraction=features['tiny_fraction'],
                             shared_input_bytes=features['shared_input_bytes'],
                             private_input_bytes=features['private_input_bytes'],
                             gap_ratio=features['ratio'],case_specific=False))


def propose_structural(g,n,cfg,q,incumbent=None,deadline=None,limit=12):
    """Case-agnostic structural portfolio: private-island wave, then tail relief."""
    yield from propose_private_island_wave(g,n,cfg,q,incumbent,deadline)
    yield from propose_tail_rebalance(g,n,cfg,q,incumbent,deadline,limit=limit)
