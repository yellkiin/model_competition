"""Unified plan model. Exact pre-spill COPY accounting; approximate timing/residency.

No evaluator is reimplemented here. Official CLI makespans decide every winner.
See THEORY.md for which expressions are identities, lower bounds, or heuristics.
"""
from __future__ import annotations
from collections import defaultdict, OrderedDict
from dataclasses import dataclass
import heapq
import json
import math
from pathlib import Path
import random

PIPES = ('PIPE_MTE2', 'PIPE_MTE3', 'PIPE_M', 'PIPE_V')
COPY = {'COPY_IN', 'COPY_OUT'}


def read_json(path: Path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path: Path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def settings(path: Path) -> dict:
    """Read the official whitespace-separated format, NOT ConfigParser INI."""
    sections, active = {}, None
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        line = line.split('#', 1)[0].strip()
        if not line:
            continue
        if line.startswith('[') and line.endswith(']'):
            active = line[1:-1].lower()
            sections[active] = {}
        else:
            key, value = line.split()
            sections[active][key] = int(value)
    return dict(capacity=sections['capacity'], bandwidth=sections['bandwidth']['bandwidth'],
                **sections['multicore_scene_a'], **sections['multicore_scene_b'], **sections['problem_3'])


def topo(pred, succ, priority=None):
    priority = priority or {u: u for u in pred}
    degree = {u: len(ps) for u, ps in pred.items()}
    ready = [(priority[u], u) for u in pred if not degree[u]]
    heapq.heapify(ready)
    order = []
    while ready:
        _, u = heapq.heappop(ready)
        order.append(u)
        for v in sorted(succ[u]):
            degree[v] -= 1
            if not degree[v]:
                heapq.heappush(ready, (priority[v], v))
    if len(order) != len(pred):
        raise ValueError('No topological order exists')
    return order


class Graph:
    def __init__(self, raw: dict):
        self.raw = raw
        self.ops = {o['id']: o for o in raw['ops']}
        self.tensors = {t['id']: t for t in raw['tensors']}
        self.ids = sorted(u for u, op in self.ops.items() if op.get('op') not in COPY)
        eligible = set(self.ids)
        self.producers = {t: set() for t in self.tensors}
        self.consumers = {t: set() for t in self.tensors}
        self.direct = []
        full_succ = {u: set() for u in self.ops}
        for edge in raw['edges']:
            a, b = edge['source'], edge['target']
            if a in self.ops and b in self.ops:
                full_succ[a].add(b)
                self.direct.append(edge)
            elif a in self.ops:
                self.producers[b].add(a)
            else:
                self.consumers[a].add(b)
        for tid in self.tensors:
            for a in self.producers[tid]:
                full_succ[a].update(self.consumers[tid] - {a})
        self.pred, self.succ = {u: set() for u in self.ids}, {u: set() for u in self.ids}
        # Match the official plan interface: contract excluded COPY paths.
        for u in self.ids:
            stack, visited = list(full_succ[u]), set()
            while stack:
                v = stack.pop()
                if v in eligible:
                    self.succ[u].add(v)
                    self.pred[v].add(u)
                elif v not in visited:
                    visited.add(v)
                    stack.extend(full_succ[v])
        self.order = topo(self.pred, self.succ)
        self.cost = {u: max(1., float(self.ops[u].get('cycles', 1))) for u in self.ids}
        self.rank = {}
        for u in reversed(self.order):
            self.rank[u] = self.cost[u] + max((self.rank[v] for v in self.succ[u]), default=0.)
        self.inputs, self.outputs = {u: set() for u in self.ids}, {u: set() for u in self.ids}
        self.ps, self.cs, self.final = {}, {}, {}
        for t in self.tensors:
            self.ps[t] = self.producers[t] & eligible
            self.cs[t] = self.consumers[t] & eligible
            self.final[t] = any(self.ops[u].get('op') == 'COPY_OUT' for u in self.consumers[t])
            for u in self.ps[t]:
                self.outputs[u].add(t)
            for u in self.cs[t]:
                self.inputs[u].add(t)
        self.work = {p: sum(self.cost[u] for u in self.ids if self.ops[u]['pipe'] == p) for p in PIPES}
        # A lower bound that uses only dependencies explicitly preserved by task construction.
        # COPY-contracted paths are for ordering; we do not silently certify their execution retention.
        guaranteed = {u: set() for u in self.ids}
        for t in self.tensors:
            for v in self.cs[t]:
                guaranteed[v].update(self.ps[t] - {v})
        for e in self.direct:
            if e['source'] in eligible and e['target'] in eligible:
                guaranteed[e['target']].add(e['source'])
        distance = {}
        for u in self.order:
            distance[u] = self.cost[u] + max((distance[v] for v in guaranteed[u]), default=0.)
        self.span = max(distance.values(), default=0.)
        self.original_copy = sum(float(tensor['size']) * (
            sum(self.ops[u].get('op') == 'COPY_IN' for u in self.producers[t]) +
            sum(self.ops[u].get('op') == 'COPY_OUT' for u in self.consumers[t]))
            for t, tensor in self.tensors.items())

    def lower_bound(self, cores: int) -> float:
        return max(self.span, max(self.work.values(), default=0.) / cores)

    def features(self) -> dict:
        total = sum(self.work.values())
        return dict(ops=len(self.ids), tensors=len(self.tensors), compute_work=total,
                    compute_span=self.span, parallelism=total / max(self.span, 1),
                    tensor_bytes=sum(float(t['size']) for t in self.tensors.values()),
                    max_tensor=max((float(t['size']) for t in self.tensors.values()), default=0),
                    fanout_pins=sum(max(0, len(c) - 1) for c in self.cs.values()),
                    shared_input_bytes=sum(float(self.tensors[t]['size']) for t in self.tensors
                                           if not self.ps[t] and len(self.cs[t]) > 1))

    def ordered(self, mode: str, rng: random.Random) -> list[int]:
        if mode == 'id':
            return list(self.order)
        if mode == 'random':
            return topo(self.pred, self.succ, {u: rng.random() for u in self.ids})
        if mode == 'critical':
            return topo(self.pred, self.succ, {u: -self.rank[u] for u in self.ids})
        # Consider up to 16 critical-ready ops. Reward last uses or recent shared inputs.
        degree = {u: len(self.pred[u]) for u in self.ids}
        heap = [(-self.rank[u], u) for u in self.ids if not degree[u]]
        heapq.heapify(heap)
        remaining = {t: len(self.cs[t]) for t in self.tensors}
        recent, answer = set(), []
        scale = max((float(t['size']) for t in self.tensors.values()), default=1.) or 1.
        rank_scale = max(self.rank.values(), default=1.)
        while heap:
            pool = [heapq.heappop(heap) for _ in range(min(16, len(heap)))]
            def key(item):
                u = item[1]
                release = sum(self.tensors[t]['size'] for t in self.inputs[u] if remaining[t] == 1)
                output = sum(self.tensors[t]['size'] for t in self.outputs[u])
                shared = sum(self.tensors[t]['size'] for t in self.inputs[u] & recent)
                benefit = shared if mode == 'cache' else release - output
                return (-benefit / scale - .2 * self.rank[u] / rank_scale, u)
            selected = min(pool, key=key)
            for item in pool:
                if item != selected:
                    heapq.heappush(heap, item)
            u = selected[1]
            answer.append(u)
            recent = self.inputs[u] | self.outputs[u]
            for t in self.inputs[u]:
                remaining[t] -= 1
            for v in sorted(self.succ[u]):
                degree[v] -= 1
                if not degree[v]:
                    heapq.heappush(heap, (-self.rank[v], v))
        return answer


@dataclass
class Plan:
    blocks: list[list[int]]
    owners: list[int]
    cores: int
    encoded: dict | None = None

    def json(self):
        if self.encoded is not None:
            return self.encoded  # exact same-plan replay, including original IDs/order
        schedules = [[] for _ in range(self.cores)]
        for s, owner in enumerate(self.owners):
            schedules[owner].append(s)
        mapping = {u: s for s, block in enumerate(self.blocks) for u in block}
        return dict(node_to_subgraph={str(u): mapping[u] for u in sorted(mapping)}, core_schedules=schedules)

    def labels(self, question: int):
        return {u: s if question == 1 else self.owners[s] for s, b in enumerate(self.blocks) for u in b}

    def key(self):
        return json.dumps(self.json(), sort_keys=True, separators=(',', ':'))

    @classmethod
    def load(cls, value: dict, graph: Graph):
        mapping = {int(u): s for u, s in value['node_to_subgraph'].items()}
        groups = sorted(set(mapping.values()))
        pred, succ = {s: set() for s in groups}, {s: set() for s in groups}
        pairs = [(mapping[u], mapping[v]) for u in graph.ids for v in graph.succ[u]]
        pairs += [(a, b) for seq in value['core_schedules'] for a, b in zip(seq, seq[1:])]
        for a, b in pairs:
            if a != b:
                succ[a].add(b)
                pred[b].add(a)
        order = topo(pred, succ)
        owner = {s: k for k, seq in enumerate(value['core_schedules']) for s in seq}
        return cls([[u for u in graph.order if mapping[u] == s] for s in order],
                   [owner[s] for s in order], len(value['core_schedules']), encoded=value)


def cut_order(graph: Graph, order: list[int], groups: int) -> list[list[int]]:
    """Contiguous, roughly equal COMPUTE-WORK blocks, not equal node counts."""
    groups = min(max(1, groups), len(order))
    if not order:
        return []
    target = sum(graph.cost[u] for u in order) / groups
    blocks, block, work = [], [], 0.
    for i, u in enumerate(order):
        block.append(u)
        work += graph.cost[u]
        remaining_blocks = groups - len(blocks) - 1
        if remaining_blocks and (work >= target or len(order) - i - 1 == remaining_blocks):
            blocks.append(block)
            block, work = [], 0.
    if block:
        blocks.append(block)
    return blocks


def copy_accounting(graph: Graph, plan: Plan, question: int):
    """Exact bytes of the official task-construction COPYs BEFORE Step2 spills.

    Q1 writes once per exporting task. Q2/Q3 write once PER remote core pair.
    Direct op-op data_size contributes COPY pairs only in Q2/Q3.
    """
    labels = plan.labels(question)
    reads, writes, direct = 0., 0., 0.
    requests = []
    for t, tensor in graph.tensors.items():
        size = float(tensor['size'])
        ps = {labels[u] for u in graph.ps[t]}
        cs = {labels[u] for u in graph.cs[t]}
        if question == 1:
            reads += size * len(cs - ps)
            writes += size * sum(graph.final[t] or not cs or bool(cs - {p}) for p in ps)
        else:
            if not ps:
                reads += size * len(cs)
                requests.extend((t, c, None, size) for c in sorted(cs))
            if ps and (graph.final[t] or not cs):
                writes += size * len(ps)
            remote = [(p, c) for p in sorted(ps) for c in sorted(cs) if p != c]
            reads += size * len(remote)
            writes += size * len(remote)
            requests.extend((t, c, p, size) for p, c in remote)
    if question != 1:
        for e in graph.direct:
            a, b = e['source'], e['target']
            if a in labels and b in labels and labels[a] != labels[b]:
                direct += 2 * max(0, int(e.get('data_size', 0)))
    return dict(read_bytes=reads, write_bytes=writes, direct_bytes=direct,
                pre_spill_bytes=reads + writes + direct, requests=requests)


def fifo_requests(requests, capacity: int, bandwidth: float, cache_bandwidth: float):
    """Timing proxy only: insertion at completion, including reinserted hit reads.

    Requests=(issue_time, logical_tensor_id, bytes). No bandwidth contention or
    generated Spill requests. Simultaneous cold reads both miss. Not official L2.
    """
    entries, used, pending, sequence = OrderedDict(), 0., [], 0
    hit_bytes, misses, hits, concurrent_misses = 0., 0, 0, 0
    inflight = defaultdict(int)
    def retire(now):
        nonlocal used
        while pending and pending[0][0] <= now:
            _, _, key, size = heapq.heappop(pending)
            inflight[key] -= 1
            if size > capacity or key in entries:
                continue
            while entries and used + size > capacity:
                _, evicted = entries.popitem(last=False)
                used -= evicted
            entries[key] = size
            used += size
    for now, key, size in sorted(requests, key=lambda r: r[0]):
        retire(now)
        if size <= 0:
            continue
        hit = key in entries
        if hit:
            hits += 1
            hit_bytes += size
        else:
            misses += 1
            concurrent_misses += int(inflight[key] > 0)
        duration = max(1, math.ceil(size / (cache_bandwidth if hit else bandwidth)))
        heapq.heappush(pending, (now + duration, sequence, key, size))
        sequence += 1
        inflight[key] += 1
    return dict(hit_bytes=hit_bytes, hits=hits, misses=misses, concurrent_misses=concurrent_misses)


def residency(graph: Graph, plan: Plan, question: int, capacity: dict):
    """Serial lifetime proxy per task: peak + work-weighted live-byte area.

    Does not model inserted COPYs, Step3 overlap or address reuse. Never claimed
    to be a physical memory bound. Outputs overlap last-use inputs at an op.
    """
    labels = plan.labels(question)
    ordered = defaultdict(list)
    for block in plan.blocks:
        for u in block:
            ordered[labels[u]].append(u)
    positions = {u: (k, j) for k, ops in ordered.items() for j, u in enumerate(ops)}
    events = defaultdict(lambda: defaultdict(float))
    for t, tensor in graph.tensors.items():
        touched = defaultdict(list)
        for u in graph.ps[t] | graph.cs[t]:
            k, j = positions[u]
            touched[k].append(j)
        pos = tensor.get('pos', 'UB')
        pos = 'UB' if pos == 'DDR' else pos
        if pos not in capacity:
            continue
        for k, js in touched.items():
            events[k, pos][min(js)] += tensor['size']
            events[k, pos][max(js) + 1] -= tensor['size']
    peaks, exposure, excess = {}, 0., 0.
    for (k, pos), changes in events.items():
        live, peak, area = 0., 0., 0.
        for j, u in enumerate(ordered[k]):
            live += changes.get(j, 0.)
            peak = max(peak, live)
            area += live * graph.cost[u]
        limit = max(1, capacity[pos])
        peaks[f'{k}:{pos}'] = peak
        excess += max(0, peak - capacity[pos])
        exposure += area / limit
    return dict(peak_proxy=peaks, excess_bytes=excess, exposure_cycles=exposure)


def estimate(graph: Graph, plan: Plan, question: int, cfg: dict,
             memory_weight: float = .15, cache_weight: float = 1., traffic_weight: float = .2):
    labels = plan.labels(question)
    by_op_core = {u: plan.owners[s] for s, b in enumerate(plan.blocks) for u in b}
    load = defaultdict(float)
    starts, finishes = {}, {}
    core_clock = [0.] * plan.cores
    for block in plan.blocks:
        for u in block:
            k = by_op_core[u]
            load[k, graph.ops[u]['pipe']] += graph.cost[u]
            start = max(core_clock[k], max((finishes[v] for v in graph.pred[u]), default=0.))
            starts[u], finishes[u] = start, start + graph.cost[u]
            core_clock[k] = finishes[u]
    account = copy_accounting(graph, plan, question)
    hit = 0.
    if question == 3 and cache_weight:
        request_times = []
        for t, dst, src, size in account['requests']:
            readers = [u for u in graph.cs[t] if by_op_core[u] == dst]
            when = min((starts[u] for u in readers), default=0.)
            if src is not None:
                writers = [u for u in graph.ps[t] if by_op_core[u] == src]
                ready = max((finishes[u] for u in writers), default=0.)
                when = max(when, ready + size / cfg['bandwidth'] + cfg['cross_core_copy_delay_cycles'])
            request_times.append((when, graph.tensors[t].get('logical_tid', t), size))
        hit = fifo_requests(request_times, cfg['cache_capacity_bytes'], cfg['bandwidth'],
                            cfg['cache_bandwidth_bytes_per_cycle'])['hit_bytes']
    transfer = max(0., account['pre_spill_bytes'] - cache_weight * hit) / cfg['bandwidth']
    cache_service = cache_weight * hit / cfg['cache_bandwidth_bytes_per_cycle'] if question == 3 else 0.
    compute = max(load.values(), default=0.)
    sync = 0.
    if question == 1:
        # Task barrier longest path. Each Task costs at least its largest Pipe work.
        end = {}
        mapping = {u: s for s, block in enumerate(plan.blocks) for u in block}
        tails = {}
        for s, block in enumerate(plan.blocks):
            owner = plan.owners[s]
            predecessors = {mapping[v] for u in block for v in graph.pred[u] if mapping[v] != s}
            ready = max((end[p] + (cfg['task_same_core_wait_cycles'] if plan.owners[p] == owner
                         else cfg['task_cross_core_wait_cycles']) for p in predecessors), default=0.)
            if owner in tails:
                ready = max(ready, end[tails[owner]] + cfg['task_same_core_wait_cycles'])
            work = max(sum(graph.cost[u] for u in block if graph.ops[u]['pipe'] == p) for p in PIPES)
            end[s], tails[owner] = ready + work, s
        sync = max(end.values(), default=0.)
    mem = residency(graph, plan, question, cfg['capacity']) if memory_weight else {}
    score = max(compute, graph.span, transfer, cache_service, sync) + traffic_weight * transfer
    score += memory_weight * (mem.get('excess_bytes', 0.) / cfg['bandwidth'] + .1 * mem.get('exposure_cycles', 0.))
    return dict(score=score, pre_spill_bytes=account['pre_spill_bytes'],
                cache_hit_bytes_proxy=hit, cache_service_proxy=cache_service, load_bound=compute, task_barrier_bound=sync, **mem)
