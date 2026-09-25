"""Shared immutable micro-component computations, inherited from Fusion/Trident."""
from copy import copy
from .vendor.orion.core import make_plan
from .vendor.memory.coherent_v4 import candidates as mem

class WaveCache:
    """Exact generator speedup: scan global topological order ONCE, not per island.

    Original memory-v4 plans are unchanged for a fixed parent/envelope/stages.
    Only data independent of the proposed envelope is reused.
    """
    def __init__(self, g, cfg):
        self.g, self.cfg = g, cfg
        self.comps = sorted(g.components, key=min)
        of = {u:i for i,c in enumerate(self.comps) for u in c}
        self.orders = [[] for _ in self.comps]
        for u in g.topo: self.orders[of[u]].append(u)
        self.peaks, self.depths = [], []
        for comp, order in zip(self.comps,self.orders):
            view = copy(g); view.topo = order
            self.peaks.append(mem._component_live_peak(view,comp))
            depth = {}
            for u in order: depth[u] = 1+max((depth[p] for p in g.pred[u] if p in comp),default=-1)
            self.depths.append(depth)
        max_peak = {pos:max((p.get(pos,0) for p in self.peaks),default=0) for pos in cfg.capacity}
        self.safe = min((cfg.capacity[p]/max(1,max_peak[p]) for p in cfg.capacity),default=1)
        self.last_parent = None

    def plan(self, parent, n, envelope, stages):
        if parent is not self.last_parent:
            owners = mem._balanced_component_owners(self.g,parent,n)
            self.assigned = [[] for _ in range(n)]
            for i,c in enumerate(self.comps): self.assigned[owners[min(c)]].append(i)
            self.last_parent = parent
        width = max(1,int(max(1.,self.safe*envelope)))
        groups, cores = [], []
        for k, indices in enumerate(self.assigned):
            for start in range(0,len(indices),width):
                batch = indices[start:start+width]
                for stage in range(stages):
                    part = set()
                    for i in batch:
                        depth = self.depths[i]; levels = max(depth.values(),default=0)+1
                        part.update(u for u,d in depth.items() if min(stages-1,d*stages//max(1,levels))==stage)
                    if part: groups.append(part); cores.append(k)
        return make_plan(groups,cores,n)

