"""Read original events; reconstruct official precedence only for diagnostics.

This does not alter the evaluator or implement a replacement simulation. Its
extra task preparation and analysis costs are not charged as search improvement.
"""
from __future__ import annotations
import argparse
import csv
import sys
import time
from pathlib import Path
from .storage import read, write
from .trace import read_requests, frozen_criticality


def csv_write(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(k for row in rows for k in row))
    if not fields:
        path.write_text('', encoding='utf-8')
        return
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fields)
        writer.writeheader()
        writer.writerows(rows)


def diagnose(official, config, graph, plan, response, out, no_l2=None):
    started = time.monotonic()
    response = read(response) if isinstance(response, (str, Path)) else response
    if response.get('status') != 'ok' or not response.get('audit', {}).get('ok'):
        raise ValueError('Expected a successfully validated original response')
    raw = response['official_result']
    rows, fills = read_requests(raw)
    plan = read(plan) if isinstance(plan, (str, Path)) else plan
    from research_a_orion_anytime.engine import OfficialSession
    session = OfficialSession(official, graph, config)
    from multicore_cut_evaluate_problem_3 import _build_scene_b_tasks
    tasks, links, _, _, _ = _build_scene_b_tasks(
        session.raw, plan, session.cfg.bandwidth, session.cfg.capacity)
    critical = frozen_criticality(raw, tasks, links, session.cfg.cross_b)
    by_op = {(r['core_id'], r['op_id']): r for r in critical['operations']}
    for row in rows:
        item = by_op.get((row['core_id'], row['op_id']), {})
        row['frozen_slack'] = item.get('frozen_slack')
        row['zero_frozen_slack'] = item.get('frozen_slack') == 0
    out = Path(out)
    csv_write(out/'reads.csv', rows)
    csv_write(out/'fills_evictions.csv', fills)
    csv_write(out/'frozen_critical_ops.csv', critical['operations'])
    sizes = {}
    for row in rows:
        category = row['cause']
        value = sizes.setdefault(category, dict(count=0, bytes=0, zero_slack_bytes=0))
        value['count'] += 1
        value['bytes'] += row['bytes']
        if row['zero_frozen_slack']:
            value['zero_slack_bytes'] += row['bytes']
    report = dict(makespan=raw['makespan'], cache_stats=raw['cache_stats'], categories=sizes,
                  criticality= {k: v for k, v in critical.items() if k != 'operations'},
                  diagnostic_seconds=time.monotonic()-started,
                  claim='Observed events and frozen-duration precedence, NOT a causal cache-speedup decomposition')
    if no_l2:
        paired = read(no_l2)
        if paired.get('status') == 'ok':
            t = paired['official_result']['makespan']
            report['same_plan_pair'] = dict(no_l2_makespan=t, with_l2_makespan=raw['makespan'],
                makespan_reduction=(t-raw['makespan'])/t if t else None,
                provenance_requirement='Caller must provide the Q2 response for exactly this plan')
    write(out/'diagnostics.json', report)
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('official', 'config', 'graph', 'plan', 'response', 'out'):
        p.add_argument('--'+name, required=True)
    p.add_argument('--no-l2')
    a = p.parse_args()
    diagnose(a.official, a.config, a.graph, a.plan, a.response, a.out, a.no_l2)


if __name__ == '__main__':
    main()
