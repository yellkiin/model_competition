"""One-time source materialization, not an experiment or a runtime patch.

The frozen PR26 files are read from the exported evidence directory. Full
resulting .py files are committed and shipped; normal runners never need this.
"""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
D=Path(__file__).parent
P=ROOT/'prior_pr26/research_a_orion_track_anytime'
def replace(s,a,b):
    if a not in s:raise ValueError('Frozen source context missing: '+a[:100])
    return s.replace(a,b)
def main():
    for name in ('storage.py','trace.py','diagnose.py'):
        (D/name).write_bytes((P/name).read_bytes())
    (D/'__init__.py').write_text('"""Independent Anytime Wu; PR26 diagnostic/storage lineage is recorded in METHOD.md."""\n')
    s=(P/'selector.py').read_text()
    s=replace(s,'dict(calls=len(rows), valid=len(ratios), calibration=calibration,',"dict(calls=sum(x.get('time_source')=='local' for x in rows), historical_calls=sum(x.get('time_source')!='local' for x in rows), valid=len(ratios), calibration=calibration,")
    s=replace(s,'if makespan / global_lower <= 1.0 + gap_tolerance:','if 1.0 - global_lower / makespan <= gap_tolerance:')
    s=replace(s,"failure_discount = (1 + stat['valid']) / (1 + stat['calls'])","failure_discount = (1 + stat['valid']) / (1 + stat['valid'] + stat['failures'])")
    (D/'selector.py').write_text(s)
    s=(P/'adapter.py').read_text()
    changes=[
      ('bounds, plan_view, fingerprint, neighbours','bounds, plan_view, neighbours'),
      ("fifo_enabled = request['method'] == 'combined'","fifo_enabled = request['method'] in ('combined','fifo')\n    adaptive = request['method'] in ('budget','combined')"),
      ("if best and generation_cost.get(name, 0)","if adaptive and best and generation_cost.get(name, 0)"),
      ("plan_hash=fingerprint(c['plan']), ",''),
      ("    checkpoint()\n    while time.monotonic() < deadline", "    if best:\n        def initial_local():\n            yield from neighbours(g,best['plan'],cfg,q,best['official_result'],limit=12)\n        streams.appendleft(('upstream_local',iter(initial_local())))\n    checkpoint()\n    while time.monotonic() < deadline"),
      ("request.get('gap_tolerance', .005)","request.get('gap_tolerance', .02)"),
      ("request.get('minimum_calls', 16))","request.get('minimum_calls', 16)) if adaptive else None"),
      ('lookahead = 1 if best is None else 2','lookahead = 1 if calls < 2 else 2'),
      ('index = select_candidate(pool, history, remaining)',"index = select_candidate(pool, history, remaining) if adaptive else min(range(len(pool)),key=lambda i:(pool[i]['proxy'].get('score',0),pool[i]['name']))"),
      ('detail = selection_details(pool, history, remaining)[index]',"detail = selection_details(pool, history, remaining)[index] if adaptive else {'rule':'static_proxy_same_lazy_engine'}"),
      ("generation_seconds=c['generation_seconds'],","generation_seconds=c['generation_seconds'], evidence=c.get('evidence'),"),
      ("costs['official_eval_seconds'] += spent","costs['official_eval_seconds'] += response.get('eval_seconds',spent)\n        costs['audit_seconds'] = costs.get('audit_seconds',0.)+max(0.,spent-response.get('eval_seconds',spent))"),
      ("plan_hash=row['plan_hash'],",''),
      ("if request['method'] == 'old':","if request['method'] == 'fixed':\n            from research_a_orion_anytime.engine import OfficialSession\n            session=OfficialSession(request['official'],request['graph'],request['config'])\n            plan=read(request['fixed_plan']);response=session.evaluate(plan,request['q'])\n            folder=Path(request['job']);write(folder/'fixed_plan.json',plan);write(folder/'fixed_response.json.gz',response)\n            raw=response.get('official_result',{})\n            write(folder/'progress.json',dict(case=request['case'],q=request['q'],n=request['n'],status=response['status'],attempts=[],evaluations=1,incumbent=dict(plan_file='fixed_plan.json',result_file='fixed_response.json.gz',makespan=raw['makespan'],added_copy_bytes=raw['data_movement_bytes']['added_copy_bytes'],name='fixed',elapsed_seconds=0.,certificate=response['audit']['certificate']) if response['status']=='ok' else None))\n        elif request['method'] == 'old':")
    ]
    for a,b in changes:s=replace(s,a,b)
    (D/'adapter.py').write_text(s)
if __name__=='__main__':main()
