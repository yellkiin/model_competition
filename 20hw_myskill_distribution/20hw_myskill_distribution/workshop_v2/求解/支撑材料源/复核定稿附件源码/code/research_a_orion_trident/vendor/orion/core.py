# 本程序及代码是在人工智能工具辅助下完成的。
# 人工智能工具名称及版本/型号：GPT-6、GPT-6 Sol、GPT-6 Luna（论文参考文献[11]）。
# 开发机构/公司：OpenAI。
# 版本颁布日期：GPT-6（Astra）2026-09-03；GPT-6 Sol、GPT-6 Luna 2026-09-22。

"""Deterministic acyclic construction, tensor-set costs and certified relaxations.

Only the two official plan fields are decision variables. All proxy timings and
memory/cache predictions are heuristics; only bounds() is used for safe pruning.
No third-party packages and no modifications to an official evaluator.
"""
from __future__ import annotations

from collections import Counter, defaultdict, OrderedDict
from dataclasses import dataclass
import hashlib
import heapq
import json
import math
from pathlib import Path
from typing import Any, Iterable

COPY = {'COPY_IN', 'COPY_OUT'}
PIPES = ('PIPE_M', 'PIPE_V', 'PIPE_MTE2', 'PIPE_MTE3')


def fingerprint(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False).encode()).hexdigest()


def topological(nodes: Iterable[int], preds: dict[int, set[int]], key=None) -> list[int]:
    nodes = set(nodes)
    successors = {u: [] for u in nodes}
    degree = {}
    for v in nodes:
        degree[v] = len(preds.get(v, set()) & nodes)
        for u in preds.get(v, set()) & nodes:
            successors[u].append(v)
    key = key or (lambda u: u)
    heap = [(key(u), u) for u in nodes if degree[u] == 0]
    heapq.heapify(heap)
    order = []
    while heap:
        _, u = heapq.heappop(heap)
        order.append(u)
        for v in successors[u]:
            degree[v] -= 1
            if degree[v] == 0:
                heapq.heappush(heap, (key(v), v))
    if len(order) != len(nodes):
        raise ValueError('dependency cycle in graph/partition/core order')
    return order


@dataclass(frozen=True)
class Config:
    l1: int
    ub: int
    bandwidth: float
    cross_a: int
    same_a: int
    cross_b: int
    cache_capacity: int
    cache_bandwidth: float

    @property
    def capacity(self) -> dict[str, int]:
        return {'L1': self.l1, 'UB': self.ub}

    @classmethod
    def read(cls, path: str | Path) -> 'Config':
        # Exact grammar is checked again by the original official reader.
        sections: dict[str, dict[str, str]] = defaultdict(dict)
        section = ''
        for line in Path(path).read_text(encoding='utf-8-sig').splitlines():
            line = line.split('#')[0].strip()
            if not line:
                continue
            if line.startswith('[') and line.endswith(']'):
                section = line[1:-1]
                continue
            k, v = line.split()
            if k in sections[section]:
                raise ValueError(f'duplicate setting: {section}.{k}')
            sections[section][k] = v
        return cls(int(sections['capacity']['L1']), int(sections['capacity']['UB']),
                   float(sections['bandwidth']['bandwidth']),
                   int(sections['multicore_scene_a']['task_cross_core_wait_cycles']),
                   int(sections['multicore_scene_a']['task_same_core_wait_cycles']),
                   int(sections['multicore_scene_b']['cross_core_copy_delay_cycles']),
                   int(sections['problem_3']['cache_capacity_bytes']),
                   float(sections['problem_3']['cache_bandwidth_bytes_per_cycle']))


class Graph:
    def __init__(self, raw: dict):
        self.raw = raw
        self.all_ops = {int(o['id']): o for o in raw['ops']}
        self.ops = {u: o for u, o in self.all_ops.items() if o['op'] not in COPY}
        self.tensors = {int(t['id']): t for t in raw['tensors']}
        self.duration = {u: max(1, int(o['cycles'])) for u, o in self.ops.items()}
        if len(self.all_ops) != len(raw['ops']) or len(self.tensors) != len(raw['tensors']):
            raise ValueError('duplicate IDs')
        if self.all_ops.keys() & self.tensors.keys():
            raise ValueError('op/tensor IDs overlap')
        self.producers: dict[int, set[int]] = defaultdict(set)
        self.consumers: dict[int, set[int]] = defaultdict(set)
        all_pred: dict[int, set[int]] = {u: set() for u in self.all_ops}
        self.direct_edges = []
        for e in raw['edges']:
            a, b = e['source'], e['target']
            if a in self.all_ops and b in self.tensors:
                self.producers[b].add(a)
            elif a in self.tensors and b in self.all_ops:
                self.consumers[a].add(b)
            elif a in self.all_ops and b in self.all_ops:
                all_pred[b].add(a)
                self.direct_edges.append((a, b, int(e.get('data_size', 0))))
            else:
                raise ValueError(f'invalid edge {a}->{b}')
        for t in self.tensors:
            for v in self.consumers[t]:
                all_pred[v].update(self.producers[t])
        all_order = topological(self.all_ops, all_pred)
        frontier: dict[int, set[int]] = {}
        self.pred: dict[int, set[int]] = {}
        for u in all_order:
            parents = set()
            for p in all_pred[u]:
                parents.update({p} if p in self.ops else frontier[p])
            frontier[u] = parents
            if u in self.ops:
                self.pred[u] = parents
        self.succ = {u: set() for u in self.ops}
        for v, ps in self.pred.items():
            for u in ps:
                self.succ[u].add(v)
        self.topo = topological(self.ops, self.pred)
        self.rank = {}
        for u in reversed(self.topo):
            self.rank[u] = self.duration[u] + max(
                (self.rank[v] for v in self.succ[u]), default=0)
        self.inputs: dict[int, set[int]] = {u: set() for u in self.ops}
        self.outputs: dict[int, set[int]] = {u: set() for u in self.ops}
        self.tp, self.tc = {}, {}
        self.terminal = {}
        # These are exactly the eligible producer/consumer relations kept by
        # the official task builders, not COPY-contracted paths used for legality.
        self.retained_pred = {u: set() for u in self.ops}
        for t in self.tensors:
            self.tp[t] = self.producers[t] & self.ops.keys()
            self.tc[t] = self.consumers[t] & self.ops.keys()
            for u in self.tp[t]:
                self.outputs[u].add(t)
            for v in self.tc[t]:
                self.inputs[v].add(t)
                self.retained_pred[v].update(self.tp[t])
            self.terminal[t] = bool(self.tp[t]) and (
                not self.tc[t] or any(self.all_ops[v]['op'] == 'COPY_OUT'
                                     for v in self.consumers[t]))
        for a, b, _ in self.direct_edges:
            if a in self.ops and b in self.ops:
                self.retained_pred[b].add(a)
        self.dfs_order = self._sink_dfs()
        self.position = {u: i for i, u in enumerate(self.dfs_order)}
        self.components = self.weak_components(set(self.ops))
        self.hash = fingerprint(raw)

    def _sink_dfs(self) -> list[int]:
        """Iterative sink-oriented DFS; no recursion-depth dependence."""
        seen, result = set(), []
        sinks = sorted(self.ops, key=lambda u: (bool(self.succ[u]), -self.rank[u], u))
        for sink in sinks:
            if sink in seen:
                continue
            seen.add(sink)
            stack = [(sink, iter(sorted(self.pred[sink], key=lambda u: (-self.rank[u], u))))]
            while stack:
                u, it = stack[-1]
                v = next(it, None)
                if v is None:
                    result.append(u)
                    stack.pop()
                elif v not in seen:
                    seen.add(v)
                    stack.append((v, iter(sorted(self.pred[v], key=lambda x: (-self.rank[x], x)))))
        return result

    def weak_components(self, nodes: set[int]) -> list[set[int]]:
        unseen, parts = set(nodes), []
        while unseen:
            u = min(unseen)
            unseen.remove(u)
            comp, stack = {u}, [u]
            while stack:
                v = stack.pop()
                near = (self.pred[v] | self.succ[v]) & unseen
                unseen.difference_update(near)
                comp.update(near)
                stack.extend(sorted(near))
            parts.append(comp)
        return parts

    def loads(self, nodes: Iterable[int]) -> dict[str, int]:
        out = {p: 0 for p in PIPES}
        for u in nodes:
            out[self.ops[u]['pipe']] += self.duration[u]
        return out

    def weight(self, nodes: Iterable[int]) -> float:
        return max(self.loads(nodes).values(), default=0)

    def split(self, nodes: set[int], cfg: Config, q: int,
              communication_weight: float = 1.0) -> list[set[int]]:
        """Balanced prefix cut with tensor-frontier costs (not an edge sum).

        A topological prefix can only send edges into its suffix. Refining an
        already acyclic block by this cut preserves quotient acyclicity.
        """
        order = sorted(nodes, key=self.position.__getitem__)
        if len(order) < 2:
            return [nodes]
        index = {u: i for i, u in enumerate(order)}
        delta = [0] * (len(order) + 1)
        touched = set().union(*(self.inputs[u] | self.outputs[u] for u in nodes))
        for t in touched:
            pins = (self.tp[t] | self.tc[t]) & nodes
            if len(pins) > 1:
                left, right = min(index[u] for u in pins), max(index[u] for u in pins)
                delta[left] += self.tensors[t]['size']
                delta[right] -= self.tensors[t]['size']
        total = self.loads(nodes)
        left_load = {p: 0 for p in PIPES}
        frontier_bytes, best = 0, None
        normalizer = max(1.0, max(total.values()))
        for i, u in enumerate(order[:-1]):
            left_load[self.ops[u]['pipe']] += self.duration[u]
            frontier_bytes += delta[i]
            frac = (i + 1) / len(order)
            if not 0.15 <= frac <= 0.85 and len(order) > 6:
                continue
            a = max(left_load.values())
            b = max(total[p] - left_load[p] for p in PIPES)
            comm = frontier_bytes / cfg.bandwidth * (2 if q == 1 else 1)
            score = max(a, b) / normalizer + communication_weight * comm / normalizer
            entry = (score, abs(a - b), i)
            if best is None or entry < best:
                best = entry
        cut = (best[2] + 1) if best else len(order) // 2
        return self.weak_components(set(order[:cut])) + self.weak_components(set(order[cut:]))


def plan_view(g: Graph, plan: dict) -> tuple[dict, dict, dict, list]:
    if set(plan) != {'node_to_subgraph', 'core_schedules'}:
        raise ValueError('plan must have exactly the two official fields')
    mapping = {}
    for key, sg in plan['node_to_subgraph'].items():
        u = int(key)
        if u in mapping or isinstance(sg, bool) or not isinstance(sg, int) or sg < 0:
            raise ValueError('duplicate op ID or invalid subgraph')
        mapping[u] = sg
    if set(mapping) != set(g.ops):
        raise ValueError('operation coverage differs from non-COPY operations')
    by_group: dict[int, set[int]] = defaultdict(set)
    for u, s in mapping.items():
        by_group[s].add(u)
    core = {}
    for k, seq in enumerate(plan['core_schedules']):
        for s in seq:
            if isinstance(s, bool) or not isinstance(s, int) or s in core:
                raise ValueError('invalid/repeated subgraph in core schedules')
            core[s] = k
    if set(core) != set(by_group):
        raise ValueError('subgraphs must occur exactly once in core schedules')
    pred = {s: set() for s in by_group}
    for u, ps in g.pred.items():
        pred[mapping[u]].update(mapping[p] for p in ps if mapping[p] != mapping[u])
    for seq in plan['core_schedules']:
        for a, b in zip(seq, seq[1:]):
            pred[b].add(a)
    order = topological(by_group, pred)
    return mapping, by_group, core, order


def make_plan(groups: list[set[int]], cores: list[int], n: int) -> dict:
    plan = {'node_to_subgraph': {}, 'core_schedules': [[] for _ in range(n)]}
    for s, (group, k) in enumerate(zip(groups, cores)):
        if not group:
            continue
        for u in sorted(group):
            plan['node_to_subgraph'][str(u)] = s
        plan['core_schedules'][k].append(s)
    return plan


def one_core(g: Graph, n: int) -> dict:
    return make_plan([set(g.ops)] if g.ops else [], [0] if g.ops else [], n)


def partition(g: Graph, n: int, cfg: Config, q: int, grain: int) -> list[set[int]]:
    groups = [set(c) for c in g.components]
    target = max(1.0, g.weight(g.ops) / max(1, grain * n))
    # At most 2*grain*n additional split operations: no unbounded recursion/search.
    for _ in range(2 * grain * n):
        choices = [(g.weight(c), len(c), i) for i, c in enumerate(groups) if len(c) > 1]
        if not choices:
            break
        w, _, i = max(choices)
        if w <= target:
            break
        parts = g.split(groups[i], cfg, q)
        groups[i:i + 1] = parts
    return groups


def map_groups(g: Graph, groups: list[set[int]], n: int, cfg: Config, q: int) -> dict:
    membership = {u: i for i, comp in enumerate(groups) for u in comp}
    preds = {i: set() for i in range(len(groups))}
    for v, ps in g.pred.items():
        preds[membership[v]].update(membership[u] for u in ps if membership[u] != membership[v])
    bl = {i: max((g.rank[u] for u in c), default=0) for i, c in enumerate(groups)}
    order = topological(preds, preds, key=lambda i: (-bl[i], min(groups[i])))
    loads = [{p: 0.0 for p in PIPES} for _ in range(n)]
    core_of, finish, assigned_inputs = {}, {}, [set() for _ in range(n)]
    ordered_groups, ordered_cores = [], []
    for i in order:
        comp = groups[i]
        w = g.loads(comp)
        ins = set().union(*(g.inputs[u] for u in comp))
        external = {t for t in ins if not g.tp[t] & comp}
        trials = []
        for k in range(n):
            ready = 0.0
            for j in preds[i]:
                delay = (cfg.cross_a if core_of[j] != k else cfg.same_a) if q == 1 else (
                    cfg.cross_b if core_of[j] != k else 0)
                ready = max(ready, finish[j] + delay)
            traffic = sum(g.tensors[t]['size'] for t in external
                          if q == 1 or t not in assigned_inputs[k])
            end = max(max(loads[k][p], ready) + w[p] for p in PIPES)
            trials.append((end + 0.25 * traffic / cfg.bandwidth,
                           max(loads[k].values()), k, end))
        _, _, k, end = min(trials)
        core_of[i], finish[i] = k, end
        for p in PIPES:
            if w[p]:
                loads[k][p] = max(loads[k][p], end - max(w.values())) + w[p]
        assigned_inputs[k].update(external)
        ordered_groups.append(comp)
        ordered_cores.append(k)
    return make_plan(ordered_groups, ordered_cores, n)


def planned_traffic(g: Graph, plan: dict, q: int) -> tuple[int, int]:
    """Exact pre-Spill boundary byte counting for the official tensor rules."""
    m, groups, core, _ = plan_view(g, plan)
    owner = {u: m[u] if q == 1 else core[m[u]] for u in g.ops}
    reads = writes = 0
    for t in g.tensors:
        ps, cs = {owner[u] for u in g.tp[t]}, {owner[u] for u in g.tc[t]}
        size = g.tensors[t]['size']
        if q == 1:
            reads += size * len(cs - ps)
            writes += size * sum(g.terminal[t] or bool(cs - {p}) for p in ps)
        else:
            if not ps:
                reads += size * len(cs)
            if g.terminal[t]:
                writes += size * len(ps)
            pairs = sum(p != c for p in ps for c in cs)
            reads += pairs * size
            writes += pairs * size
    if q != 1:
        for a, b, size in g.direct_edges:
            if a in owner and b in owner and owner[a] != owner[b]:
                reads += size
                writes += size
    return reads, writes


def bounds(g: Graph, cfg: Config, n: int, q: int, plan: dict | None = None) -> dict:
    """Provable LOWER bounds; never include heuristic memory/cache predictions.

    The global relaxation uses only computation dependencies the original task
    builders preserve. For problem 1, direct op->op cross-Task edges are not used
    in the candidate communication bound (the official contest graphs are bipartite).
    """
    if n < 1:
        raise ValueError('n must be positive')
    finish = {}
    for v in g.topo:
        finish[v] = g.duration[v] + max((finish[u] for u in g.retained_pred[v]), default=0)
    pipeline = max(g.loads(g.ops).values(), default=0) / n
    cp = max(finish.values(), default=0)
    compulsory_r = sum(g.tensors[t]['size'] for t in g.tensors if g.tc[t] and not g.tp[t])
    compulsory_w = sum(g.tensors[t]['size'] for t in g.tensors if g.terminal[t])
    # Explicit logical aliases are outside the primary-input certificate scope.
    # Writes remain mandatory; cold-read lower bound is disabled conservatively.
    aliases = any('logical_tid' in t for t in g.tensors.values())
    compulsory = (compulsory_w + (0 if q == 3 and aliases else compulsory_r)) / cfg.bandwidth
    result = {'compute_path': cp, 'compute_load': pipeline, 'compulsory_ddr': compulsory,
              'global_lower': max(cp, pipeline, compulsory), 'logical_aliases': aliases}
    if plan is None:
        return result
    m, groups, core, order = plan_view(g, plan)
    owner = {u: core[m[u]] for u in g.ops}
    core_load = max((max(g.loads(u for u in g.ops if owner[u] == k).values(), default=0)
                     for k in range(n)), default=0)
    if q == 1:
        group_pred = {s: set() for s in groups}
        for v, ps in g.pred.items():
            group_pred[m[v]].update(m[u] for u in ps if m[u] != m[v])
        for seq in plan['core_schedules']:
            for a, b in zip(seq, seq[1:]):
                group_pred[b].add(a)
        gf = {}
        for s in order:
            gf[s] = g.weight(groups[s]) + max((gf[p] + (cfg.same_a if core[p] == core[s]
                                             else cfg.cross_a) for p in group_pred[s]), default=0)
        communication = max(gf.values(), default=0)
    else:
        f = {}
        for v in g.topo:
            f[v] = g.duration[v] + max((f[u] + (cfg.cross_b if owner[u] != owner[v] else 0)
                                           for u in g.retained_pred[v]), default=0)
        communication = max(f.values(), default=0)
    reads, writes = planned_traffic(g, plan, q)
    io_lb = (reads + writes) / cfg.bandwidth if q != 3 else max(
        writes / cfg.bandwidth, (reads + writes) / (cfg.bandwidth + cfg.cache_bandwidth))
    result.update(candidate_core_load=core_load, candidate_communication=communication,
                  candidate_io=io_lb, pre_spill_read_bytes=reads, pre_spill_write_bytes=writes,
                  candidate_lower=max(result['global_lower'], core_load, communication, io_lb))
    return result


def memory_proxy(g: Graph, plan: dict, cfg: Config, q: int) -> dict:
    """Live-interval peak and eviction estimate on OUR order, not official Step2.

    A high peak is a penalty, not an infeasibility conclusion: Spill is legal.
    """
    m, groups, core, order = plan_view(g, plan)
    owner = {u: core[m[u]] for u in g.ops}
    sequences = []
    if q == 1:
        sequences = [sorted(groups[s], key=g.position.__getitem__) for s in order]
    else:
        sequences = [[u for s in plan['core_schedules'][k]
                      for u in sorted(groups[s], key=g.position.__getitem__)]
                     for k in range(len(plan['core_schedules']))]
    spill, peaks, live_area = 0, {'L1': 0, 'UB': 0}, 0
    for seq in sequences:
        if not seq:
            continue
        index = {u: i for i, u in enumerate(seq)}
        intervals = defaultdict(list)
        touched = set().union(*(g.inputs[u] | g.outputs[u] for u in seq))
        for t in touched:
            tensor = g.tensors[t]
            uses = [index[u] for u in g.tc[t] if u in index]
            creates = [index[u] for u in g.tp[t] if u in index]
            if not uses and not creates:
                continue
            a = min(creates) if creates else min(uses)
            b = max(uses + creates)
            pos = tensor['pos'] if tensor['pos'] != 'DDR' else 'UB'
            intervals[pos].append((a, b, t, tensor['size']))
        for pos, items in intervals.items():
            diff = [0] * (len(seq) + 1)
            for a, b, t, size in items:
                diff[a] += size
                diff[b + 1] -= size
            live = 0
            peak = 0
            over_area = 0
            for d in diff[:-1]:
                live += d
                peak = max(peak, live)
                over_area += max(0, live - cfg.capacity[pos])
            peaks[pos] = max(peaks[pos], peak)
            live_area += over_area
            # One excess working-set turnover per 16 operations; a heuristic.
            spill += 2 * over_area / max(16, min(128, len(seq)))
    return {'predicted_peak': peaks, 'live_excess_area': live_area,
            'predicted_spill_bytes': int(spill)}


def _timing_proxy(g: Graph, plan: dict, cfg: Config, q: int,
                  hit_map: dict | None = None) -> dict:
    m, groups, core, group_order = plan_view(g, plan)
    n = len(plan['core_schedules'])
    owner = {u: core[m[u]] for u in g.ops}
    task = {u: m[u] if q == 1 else owner[u] for u in g.ops}
    pipe = [{p: 0.0 for p in PIPES} for _ in range(n)]
    finished, group_finish, fetched, sent = {}, {}, {}, {}
    reads = []
    hit_map = hit_map or {}
    prev_core = [0.0] * n
    for s in group_order:
        k = core[s]
        activate = 0.0
        if q == 1:
            ps = {m[p] for u in groups[s] for p in g.pred[u] if m[p] != s}
            activate = max((group_finish[p] + (cfg.same_a if core[p] == k else cfg.cross_a)
                            for p in ps), default=0)
            if prev_core[k]:
                activate = max(activate, prev_core[k] + cfg.same_a)
        for u in sorted(groups[s], key=g.position.__getitem__):
            ready = activate
            for p in g.retained_pred[u]:
                ready = max(ready, finished[p] + (cfg.cross_b if q != 1 and owner[p] != k else 0))
            for t in sorted(g.inputs[u]):
                local_producers = [p for p in g.tp[t] if task[p] == task[u]]
                if local_producers:
                    ready = max(ready, *(finished[p] for p in local_producers))
                    # Multi-producer remote contributions are also required.
                    if q == 1 or all(owner[p] == k for p in g.tp[t]):
                        continue
                destinations = [None] if not g.tp[t] else sorted({owner[p] for p in g.tp[t] if owner[p] != k})
                if q == 1:
                    destinations = [None] if not local_producers else []
                for source_core in destinations:
                    key = (task[u], t, source_core)
                    if key not in fetched:
                        earliest = activate
                        size = g.tensors[t]['size']
                        if source_core is not None:
                            sk = (source_core, k, t)
                            if sk not in sent:
                                earliest_out = max(finished[p] for p in g.tp[t] if owner[p] == source_core)
                                out = max(earliest_out, pipe[source_core]['PIPE_MTE3']) + max(1, math.ceil(size / cfg.bandwidth))
                                pipe[source_core]['PIPE_MTE3'] = out
                                sent[sk] = out
                            earliest = max(earliest, sent[sk] + cfg.cross_b)
                        start = max(earliest, pipe[k]['PIPE_MTE2'])
                        bw = cfg.cache_bandwidth if hit_map.get(key, False) else cfg.bandwidth
                        end = start + max(1, math.ceil(size / bw))
                        fetched[key] = end
                        pipe[k]['PIPE_MTE2'] = end
                        reads.append({'key': key, 'tensor': g.tensors[t].get('logical_tid', t),
                                      'size': size, 'start': start, 'end': end, 'core': k})
                    ready = max(ready, fetched[key])
            begin = max(ready, pipe[k][g.ops[u]['pipe']])
            finished[u] = begin + g.duration[u]
            pipe[k][g.ops[u]['pipe']] = finished[u]
        # Account for terminal/boundary writes; task boundary semantics differ.
        for t in sorted(set().union(*(g.outputs[u] for u in groups[s]))):
            local_ps = g.tp[t] & groups[s]
            if not local_ps:
                continue
            need = g.terminal[t] or (q == 1 and any(m[v] != s for v in g.tc[t]))
            key = ('terminal', task[next(iter(local_ps))], t)
            all_local_ps = [p for p in g.tp[t] if task[p] == task[next(iter(local_ps))]]
            if need and key not in sent and all(p in finished for p in all_local_ps):
                end = max(pipe[k]['PIPE_MTE3'], max(finished[p] for p in all_local_ps)) + max(1, math.ceil(g.tensors[t]['size'] / cfg.bandwidth))
                pipe[k]['PIPE_MTE3'] = end
                sent[key] = end
        group_finish[s] = max(pipe[k].values())
        if q == 1:
            prev_core[k] = group_finish[s]
    return {'nominal_makespan': max((max(p.values()) for p in pipe), default=0),
            'reads': reads, 'pipe_finish': pipe, 'op_finish': finished}


def fifo_prediction(reads: list[dict], capacity: int) -> dict:
    """Hit at issue, fill at completion, FIFO hits NEVER refresh the queue.

    Event times come from a surrogate schedule; this is not the official hit rate.
    """
    queue: OrderedDict[int, int] = OrderedDict()
    used, hits = 0, {}
    events = []
    for i, read in enumerate(reads):
        events.extend([(read['start'], 1, read['core'], i), (read['end'], 0, read['core'], i)])
    for _, kind, _, i in sorted(events):
        r = reads[i]
        t, size = r['tensor'], r['size']
        if kind == 1:
            hits[r['key']] = t in queue
        elif size <= capacity and t not in queue:
            while queue and used + size > capacity:
                _, old = queue.popitem(last=False)
                used -= old
            queue[t] = size
            used += size
    return hits


def estimate(g: Graph, plan: dict, cfg: Config, q: int, memory: bool = True,
             cache: bool = True) -> dict:
    timing = _timing_proxy(g, plan, cfg, q)
    hit_bytes = 0
    if q == 3 and cache:
        hits = fifo_prediction(timing['reads'], cfg.cache_capacity)
        hit_bytes = sum(r['size'] for r in timing['reads'] if hits[r['key']])
        timing = _timing_proxy(g, plan, cfg, q, hits)
    r, w = planned_traffic(g, plan, q)
    bus = max((r + w - hit_bytes) / cfg.bandwidth,
              hit_bytes / cfg.cache_bandwidth if q == 3 else 0)
    mem = memory_proxy(g, plan, cfg, q) if memory else {'predicted_spill_bytes': 0, 'predicted_peak': {}, 'live_excess_area': 0}
    # Penalty is not a lower bound and is NEVER used for certified pruning.
    score = max(timing['nominal_makespan'], bus) + mem['predicted_spill_bytes'] / cfg.bandwidth
    return {'score': score, 'nominal_makespan': timing['nominal_makespan'], 'bus_load': bus,
            'predicted_hit_bytes': hit_bytes, **mem}


def constructors(g: Graph, n: int, cfg: Config, q: int,
                 memory: bool = True, cache: bool = True, diagnostics: list | None = None) -> list[dict]:
    """One multiresolution construction; no official performance calls."""
    candidates, seen = [], set()
    def add(name, plan):
        try:
            plan_view(g, plan)
            h = fingerprint(plan)
            if h in seen:
                return
            seen.add(h)
            proxy = estimate(g, plan, cfg, q, memory, cache)
            candidates.append({'name': name, 'plan': plan, 'proxy': proxy,
                               'bounds': bounds(g, cfg, n, q, plan)})
        except (ValueError, KeyError) as exc:
            # A constructor bug must be visible; it is not scored as a valid plan.
            candidates.append({'name': name, 'error': str(exc), 'plan': plan})
    roots = map_groups(g, g.components, n, cfg, q)
    add('component_order', roots)
    m, groups, core, _ = plan_view(g, roots)
    packed = [set(u for u in g.ops if core[m[u]] == k) for k in range(n)]
    add('component_pack', make_plan(packed, list(range(n)), n))
    for grain in (2, 4, 8):
        add(f'frontier_g{grain}', map_groups(g, partition(g, n, cfg, q, grain), n, cfg, q))
    if q == 3:
        phase = json.loads(json.dumps(roots))
        # Independent WCCs: legal natural-work staggering, not a delay command.
        for k, seq in enumerate(phase['core_schedules']):
            if seq:
                offset = k % len(seq)
                phase['core_schedules'][k] = seq[offset:] + seq[:offset]
        add('fifo_phase_order', phase)
    add('single_core_fallback', one_core(g, n))
    errors = [{'name': c['name'], 'error': c['error']} for c in candidates if 'error' in c]
    if diagnostics is not None:
        diagnostics.extend(errors)
    elif errors:
        raise ValueError(f'constructor failures: {errors}')
    valid = [c for c in candidates if 'error' not in c]
    return sorted(valid, key=lambda c: (c['proxy']['score'], c['bounds']['candidate_lower'], c['name']))


def neighbours(g: Graph, plan: dict, cfg: Config, q: int, result: dict | None,
               limit: int = 24, memory: bool = True, cache: bool = True) -> list[dict]:
    """Bottleneck-directed migration, split and independent-block reordering."""
    m, groups, core, order = plan_view(g, plan)
    n = len(plan['core_schedules'])
    candidates, seen = [], {fingerprint(plan)}
    def add(name, p):
        if len(candidates) >= limit:
            return
        try:
            plan_view(g, p)
        except ValueError:
            return
        h = fingerprint(p)
        if h not in seen:
            seen.add(h)
            candidates.append({'name': name, 'plan': p, 'proxy': estimate(g, p, cfg, q, memory, cache),
                               'bounds': bounds(g, cfg, n, q, p)})
    def migrate(s, k, name):
        p = make_plan([groups[v] for v in order], [k if v == s else core[v] for v in order], n)
        add(name, p)
    # Target late cross-core dependencies, not a random edge.
    links = sorted((result or {}).get('cross_core_transfers', []),
                   key=lambda x: (-x['copy_in_end'], -x['size'], x['tensor_id']))
    for link in links[:6]:
        t = link['tensor_id']
        for u in sorted(g.tp.get(t, set()))[:1]:
            migrate(m[u], link['target_core'], 'critical_producer_colocate')
        for v in sorted(g.tc.get(t, set()))[:1]:
            migrate(m[v], link['source_core'], 'critical_consumer_colocate')
    load = [g.weight(u for u in g.ops if core[m[u]] == k) for k in range(n)]
    busy = max(range(n), key=lambda k: (load[k], -k))
    light = min(range(n), key=lambda k: (load[k], k))
    choices = sorted((s for s in groups if core[s] == busy), key=lambda s: (-g.weight(groups[s]), s))
    for s in choices[:4]:
        if busy != light:
            migrate(s, light, 'bottleneck_load_move')
        if len(groups[s]) > 1:
            parts = g.split(groups[s], cfg, q)
            expanded, placed = [], []
            for v in order:
                if v == s:
                    for j, part in enumerate(parts):
                        expanded.append(part)
                        placed.append(light if j % 2 and light != busy else core[v])
                else:
                    expanded.append(groups[v]); placed.append(core[v])
            add('bottleneck_frontier_split', make_plan(expanded, placed, n))
    for k, seq in enumerate(plan['core_schedules']):
        for i in range(min(len(seq) - 1, 3)):
            p = json.loads(json.dumps(plan))
            p['core_schedules'][k][i:i + 2] = [seq[i + 1], seq[i]]
            add('fifo_or_live_order_swap', p)
    return sorted(candidates, key=lambda c: (c['proxy']['score'], c['name']))
