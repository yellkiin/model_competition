"""Stage-stationary cores and legal independent-component microbatches."""
from __future__ import annotations
from collections import defaultdict
import math
from .model import Graph, make_plan, topo
from .stages import frontier_cuts


def pipeline_plan(g, n, cfg, q, stages=5, batch=1, fine=False, frontier=False):
    """Stage-stationary cores and independent-component microbatches.

    No operator splitting or new dependency is written to the input graph.
    Fine uses legal subgraph priority to promote same-layer tensor reuse.
    """
    stages=min(n,stages)
    levels=sorted(set(g.depth.values())); ix={d:i for i,d in enumerate(levels)}
    # Balance cumulative compute work across the depth axis.
    work=[0.]*len(levels)
    for u in g.order:work[ix[g.depth[u]]]+=g.cost[u]
    total=sum(work);cum=0.;stage_of={}
    for j,d in enumerate(levels):
        stage_of[d]=min(stages-1,int((cum+.5*work[j])*stages/max(total,1)))
        cum+=work[j]
    if frontier:
        cuts=frontier_cuts(g,n,stages)
        stage_of={d:next(s for s,end in enumerate(cuts) if ix[d]<end) for d in levels}
    # At least one core per stage; deterministic proportional allocation.
    alloc=[n//stages+(int(s<n%stages)) for s in range(stages)]
    offsets=[sum(alloc[:s]) for s in range(stages)]
    grouped=defaultdict(list)
    for i,comp in enumerate(g.components):
        for u in comp:
            s=stage_of[g.depth[u]]
            k=offsets[s]+(i//batch)%alloc[s]
            wave=i//(batch*alloc[s])
            # Stages own disjoint cores. All cross-stage edges move forward.
            # Within a stage, component batches are independent.
            key=(s,wave,g.depth[u] if fine else 0,k)
            grouped[key].append(u)
    keys=sorted(grouped)
    return make_plan([sorted(grouped[key],key=g.index.__getitem__) for key in keys],[key[-1] for key in keys],n)
