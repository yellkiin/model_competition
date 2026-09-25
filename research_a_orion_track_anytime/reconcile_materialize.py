"""One-time additive source materializer; never overwrites the peer runner.

Generated reconcile_runner.py is committed before official real-case runs.
No line-number patching, hidden changes to shared code, or synthetic tests.
"""
from pathlib import Path
P=Path(__file__).resolve().parent
s=(P/'runner.py').read_text(encoding='utf8')
changes=[
('"""Bounded paired real experiments. No synthetic inputs or deferred score backfill."""','"""Additive reconciliation runner derived from the recorded Wu runner.\nExisting runner.py is unchanged. old / peer_v4 / repair_v6 are explicit arms.\nMissing former v4/v5 files are not silently materialized or treated as executed.\n"""'),
("'research_a_orion_track_anytime.adapter'","'research_a_orion_track_anytime.reconcile_v6'"),
("default='old,combined'","default='old,peer_v4,repair_v6'"),
("choices=['v1.1','v2','v3'],default='v1.1'","choices=['reconcile-v6'],default='reconcile-v6'"),
("{'old','budget','combined','queue','fifo'}","{'old','peer_v4','repair_v6'}"),
("branch='orion/track-anytime_wu'","branch='orion/anytime-reconcile-20260925-1012',peer_commit='27f7aa073bd7f91a1b1b9842eb2c9eb48117bf37'"),
("cost=seed['seed_solve_seconds']+seed['validation_seconds'] if mode=='warm' else 0.","cost=None if mode=='warm' else 0. # complete historical acquisition cost is unknown"),
("seed_validation_seconds=seed['validation_seconds'])","seed_validation_seconds=seed['validation_seconds'],seed_validated_this_run=True,\n                known_seed_primary_path_seconds=seed.get('seed_solve_seconds'),\n                seed_cost_note='Historical per-case subtotal is not full search acquisition cost')"),
("revision=a.revision)","revision=a.revision,near_bound_budget_gap=.0205)"),
("dict(jobs=len(records),statuses=","dict(expected_jobs=len(manifest['cases'])*len(manifest['questions'])*len(manifest['cores'])*len(manifest['methods'])*len(manifest['modes']),jobs=len(records),statuses=")]
for old,new in changes:
    if s.count(old)!=1:raise ValueError('Source anchor absent or ambiguous: '+old[:80])
    s=s.replace(old,new,1)
target=P/'reconcile_runner.py'
if target.exists():raise FileExistsError(target)
target.write_text(s,encoding='utf8')
