"""Official CPU CLI adapter and source-aligned performance metrics."""
from __future__ import annotations
from collections import defaultdict
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from .model import read_json, write_json


def interval_union(intervals):
    total, end = 0., float('-inf')
    for a, b in sorted(intervals):
        total += max(0., b - max(a, end))
        end = max(end, b)
    return total


def metrics(raw: dict) -> dict:
    """Current Q3 has no physical_ddr_bytes. Never fall back to scheduled bytes.

    Q1/Q2 constructed transfers and Step2 spill COPYs are DDR-backed. Under that
    official construction, scheduled minus cache-hit bytes is DDR byte accounting.
    COPY occupancy is *not* DDR utilization (it includes contention waiting).
    """
    movement, cache = raw.get('data_movement_bytes', {}), raw.get('cache_stats', {})
    makespan = float(raw['makespan'])
    scheduled = movement.get('scheduled_copy_bytes')
    hits = float(cache.get('hit_bytes', 0))
    ddr = raw.get('physical_ddr_bytes', movement.get('physical_ddr_bytes'))
    source = 'official_field'
    if ddr is None and scheduled is not None:
        ddr, source = float(scheduled) - hits, 'scheduled_copy_bytes_minus_cache_hit_bytes'
    intervals, compute_work = defaultdict(list), defaultdict(float)
    read_end = {}
    burst_bytes = 0.
    for core in raw.get('per_core_timeline', []):
        k = core['core_id']
        for op in core.get('ops', []):
            intervals[k, op['pipe']].append((op['start'], op['end']))
            if op['op'] not in ('COPY_IN', 'COPY_OUT'):
                compute_work[k] += op['duration']
            if 'cache_tensor_id' in op:
                read_end[k, op['op_id']] = op['end']
    pending = defaultdict(list)
    for event in raw.get('cache_events', []):
        if event['event'] not in ('hit', 'miss'):
            continue
        t, key = event['time'], event['tensor_id']
        pending[key] = [end for end in pending[key] if end > t]
        if event['event'] == 'miss' and pending[key]:
            burst_bytes += event['size_bytes']
        end = read_end.get((event['core_id'], event['op_id']), t)
        pending[key].append(end)
    count = int(cache.get('accesses', 0))
    byte_total = hits + float(cache.get('miss_bytes', 0))
    result = dict(makespan=makespan, scheduled_copy_bytes=scheduled,
                  spill_added_copy_bytes=movement.get('spill_added_copy_bytes', 0),
                  partition_added_copy_bytes=movement.get('partition_added_copy_bytes', 0),
                  cache_hit_bytes=hits, cache_accesses=count,
                  cache_byte_hit_rate=hits / byte_total if byte_total else None,
                  cache_count_hit_rate=cache.get('hits', 0) / count if count else None,
                  overlapping_miss_bytes=burst_bytes,
                  memory_peak=raw.get('memory_peak_by_core', raw.get('memory_peak_by_task', {})),
                  pipe_occupancy={f'{k}:{p}': interval_union(values) / makespan
                                  for (k, p), values in intervals.items()} if makespan else {},
                  compute_work_by_core=dict(compute_work), ddr_accounting_source=source)
    cores = raw.get('num_cores', max((k for k, _ in intervals), default=0) + 1)
    for pipe in ('PIPE_M', 'PIPE_V', 'PIPE_MTE2', 'PIPE_MTE3'):
        result[f'mean_occupancy_{pipe}'] = sum(interval_union(intervals[k, pipe]) for k in range(cores)) / max(1., cores * makespan)
    for pos in ('L1', 'UB'):
        result[f'max_{pos}_peak_bytes'] = max((v.get(pos, 0) for v in result['memory_peak'].values()), default=0)
    result['memory_dependency_count'] = sum(v.get('memory_dependency_count', 0)
        for v in raw.get('step3_by_core', raw.get('step3_by_task', {})).values())
    if raw.get('cache_bandwidth_bytes_per_cycle'):
        result['cache_service_lower_bound_cycles'] = hits / raw['cache_bandwidth_bytes_per_cycle']
    if ddr is not None:
        result['ddr_accounted_bytes'] = ddr
        if raw.get('bandwidth_bytes_per_cycle'):
            result['ddr_service_lower_bound_cycles'] = ddr / raw['bandwidth_bytes_per_cycle']
    return result


class Official:
    def __init__(self, code: Path, config: Path, graph: Path, directory: Path, timeout=300.):
        self.code, self.config, self.graph = Path(code).resolve(), Path(config).resolve(), Path(graph).resolve()
        self.directory, self.timeout = Path(directory), timeout
        self.directory.mkdir(parents=True, exist_ok=True)

    def evaluate(self, plan=None, question=1, trace=False):
        with tempfile.TemporaryDirectory(prefix='eval_', dir=self.directory) as temp:
            work = Path(temp)
            script = self.code / (f'multicore_cut_evaluate_problem_{question}.py' if plan is not None else 'singlecore_evaluate.py')
            command = [sys.executable, str(script), str(self.graph)]
            if plan is not None:
                write_json(work / 'plan.json', plan.json())
                command.append(str(work / 'plan.json'))
            trace_path = self.directory / 'best_trace.json' if trace else Path(os.devnull)
            command += ['--config', str(self.config), '-o', str(work / 'result.json'),
                        '--trace-output', str(trace_path), '--log-output', os.devnull]
            start = time.perf_counter()
            try:
                process = subprocess.run(command, capture_output=True, text=True, timeout=self.timeout)
                elapsed = time.perf_counter() - start
                if process.returncode:
                    return dict(status='error', seconds=elapsed, error=(process.stderr + process.stdout)[-5000:]), None
                raw = read_json(work / 'result.json')
                return dict(status='ok', seconds=elapsed, **metrics(raw)), raw
            except subprocess.TimeoutExpired:
                return dict(status='timeout', seconds=time.perf_counter() - start,
                            error=f'Official evaluation exceeded {self.timeout:g} seconds'), None
            except (OSError, ValueError, KeyError) as error:
                return dict(status='error', seconds=time.perf_counter() - start, error=str(error)), None
