"""Input graph and immutable-plan helpers. No changes to official operations."""
from __future__ import annotations
from collections import defaultdict
import heapq
import json
from pathlib import Path

COPY = {'COPY_IN', 'COPY_OUT'}
PIPES = ('PIPE_M', 'PIPE_V', 'PIPE_MTE2', 'PIPE_MTE3')


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def topo(pred, key=None):
    key = key or (lambda u: u)
    succ = {u: [] for u in pred}
    degree = {u: len(ps) for u, ps in pred.items()}
    for v, ps in pred.items():
        for u in ps:
            succ[u].append(v)
    heap = [(key(u), u) for u, d in degree.items() if not d]
    heapq.heapify(heap)
    order = []
    while heap:
        _, u = heapq.heappop(heap)
        order.append(u)
        for v in succ[u]:
            degree[v] -= 1
            if not degree[v]:
                heapq.heappush(heap, (key(v), v))
    if len(order) != len(pred):
        raise ValueError('cyclic dependency graph')
    return order


class Graph:
    def __init__(self, raw):
        self.raw = raw
        self.all_ops = {o['id']: o for o in raw['ops']}
        self.ops = {u: o for u, o in self.all_ops.items() if o['op'] not in COPY}
        self.ids = sorted(self.ops)
        self.tensors = {t['id']: t for t in raw['tensors']}
        if len(self.all_ops)!=len(raw['ops']) or len(self.tensors)!=len(raw['tensors']) or self.all_ops.keys() & self.tensors.keys():
            raise ValueError('node IDs must be unique and disjoint')
        self.producers = {t: set() for t in self.tensors}
        self.consumers = {t: set() for t in self.tensors}
        allpred = {u: set() for u in self.all_ops}
        self.direct = []
        for e in raw['edges']:
            a, b = e['source'], e['target']
            if a in self.all_ops and b in self.tensors:
                self.producers[b].add(a)
            elif a in self.tensors and b in self.all_ops:
                self.consumers[a].add(b)
            elif a in self.all_ops and b in self.all_ops:
                allpred[b].add(a)
                self.direct.append(e)
            else:
                raise ValueError('invalid edge endpoint')
        for t in self.tensors:
            for v in self.consumers[t]:
                allpred[v].update(self.producers[t])
        allorder = topo(allpred)
        frontier = {}
        self.pred = {}
        for u in allorder:
            ps = set()
            for v in allpred[u]:
                if v in self.ops:
                    ps.add(v)
                else:
                    ps.update(frontier[v])
            frontier[u] = ps
            if u in self.ops:
                self.pred[u] = ps
        self.succ = {u: set() for u in self.ids}
        for v, ps in self.pred.items():
            for u in ps:
                self.succ[u].add(v)
        self.order = topo(self.pred)
        self.index = {u: i for i, u in enumerate(self.order)}
        self.cost = {u: max(1, self.ops[u].get('cycles', 1)) for u in self.ids}
        self.pipe = {u: PIPES.index(self.ops[u]['pipe']) for u in self.ids}
        self.rank, self.depth, self.earliest = {}, {}, {}
        for u in reversed(self.order):
            self.rank[u] = self.cost[u] + max((self.rank[v] for v in self.succ[u]), default=0)
        for u in self.order:
            self.depth[u] = max((self.depth[v] + 1 for v in self.pred[u]), default=0)
            self.earliest[u] = max((self.earliest[v] + self.cost[v] for v in self.pred[u]), default=0)
        self.ps = {t: self.producers[t] & self.ops.keys() for t in self.tensors}
        self.cs = {t: self.consumers[t] & self.ops.keys() for t in self.tensors}
        self.inputs = {u: set() for u in self.ids}
        self.outputs = {u: set() for u in self.ids}
        self.final = {}
        self.retained_pred = {u: set() for u in self.ids}
        for t in self.tensors:
            for u in self.ps[t]: self.outputs[u].add(t)
            for v in self.cs[t]:
                self.inputs[v].add(t)
                self.retained_pred[v].update(self.ps[t] - {v})
            self.final[t] = bool(self.ps[t]) and (not self.cs[t] or any(self.all_ops[u]['op']=='COPY_OUT' for u in self.consumers[t]))
        for e in self.direct:
            if e['source'] in self.ops and e['target'] in self.ops:
                self.retained_pred[e['target']].add(e['source'])
        self.work = self.loads(self.ids)
        distance = {}
        for u in self.order:
            distance[u] = self.cost[u]+max((distance[v] for v in self.retained_pred[u]), default=0)
        self.span = max(distance.values(), default=0)
        self.components = self.wcc(self.ids)

    def wcc(self, nodes):
        remaining = set(nodes)
        parts = []
        for u in self.order:
            if u not in remaining: continue
            remaining.remove(u)
            stack, part = [u], []
            while stack:
                v = stack.pop(); part.append(v)
                for w in self.pred[v] | self.succ[v]:
                    if w in remaining:
                        remaining.remove(w); stack.append(w)
            parts.append(sorted(part, key=self.index.__getitem__))
        return parts

    def loads(self, nodes):
        load = [0] * len(PIPES)
        for u in nodes: load[self.pipe[u]] += self.cost[u]
        return load

    def lower_bound(self, n):
        return max(self.span, max(self.work, default=0)/n)

    def features(self, n=5):
        total = sum(self.work)
        return dict(ops=len(self.ids), components=len(self.components), max_component=max(map(len,self.components), default=0),
                    depth=max(self.depth.values(), default=0), span=self.span, work=self.work,
                    max_component_work=max((sum(self.loads(c)) for c in self.components), default=0),
                    lower_bound=self.lower_bound(n), parallelism=total/max(self.span,1))


def make_plan(blocks, owners, n):
    if n < 1 or len(blocks) != len(owners):
        raise ValueError("invalid core count or block ownership")
    mapping, schedules = {}, [[] for _ in range(n)]
    for s, (block, k) in enumerate(zip(blocks, owners)):
        if not block: continue
        if not isinstance(k,int) or not 0<=k<n:raise ValueError("invalid owner")
        schedules[k].append(s)
        for u in block:
            if str(u) in mapping: raise ValueError('duplicate assignment')
            mapping[str(u)] = s
    return dict(node_to_subgraph=mapping, core_schedules=schedules)
