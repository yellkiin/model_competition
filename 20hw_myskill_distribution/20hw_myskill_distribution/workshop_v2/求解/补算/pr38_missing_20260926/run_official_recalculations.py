"""Three isolated official re-evaluations; never enters the search loop."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

OUT=Path(__file__).resolve().parent
SNAP=Path(r'D:\华为杯写作\ORION_Paper_Agent\数据\ORION_论文资料\snapshots\20260925T204725662983Z\method')
sys.path.insert(0,str(SNAP))
from research_a_orion_trident.io import read, write
from research_a_orion_trident.vendor.orion.engine import OfficialSession

RAW=Path(r'D:\华为杯写作\.orion_paper_cache\local_raw')
H1=RAW/r'host1\records\research_a_orion_trident\runs\assets_shard_1\official'
H2=RAW/r'host2\records\research_a_orion_trident\runs\assets_shard_2\official'
H0=RAW/r'shard0_outer\records\03_inputs\official'
Q3_ORIGINAL=RAW/r'host0\records\run\jobs\case_014_q3_n5'

CASES={
 'case_072_q0_n1':dict(official=H1,graph=H1/'data/case_072.json',q=0,n=1),
 'case_091_q0_n1':dict(official=H2,graph=H2/'data/case_091.json',q=0,n=1),
 'case_014_q3n5_same_plan_no_l2':dict(official=H0,graph=H0/'data/case_014.json',q=2,n=5),
}

def run(key):
    spec=CASES[key]
    dest=OUT/key
    dest.mkdir(parents=True,exist_ok=True)
    start=datetime.now(timezone.utc)
    t0=time.perf_counter()
    print('START',start.isoformat(),key,flush=True)
    print('OFFICIAL',spec['official'],flush=True)
    print('GRAPH',spec['graph'],flush=True)
    print('CONFIG',spec['official']/'data/config.txt',flush=True)
    try:
        session=OfficialSession(spec['official'],spec['graph'],spec['official']/'data/config.txt')
        if spec['q']==0:
            # Use the official one-core builder; OfficialSession.evaluate(q=0)
            # calls evaluate_singlecore on the original whole graph.
            from singlecore_evaluate import build_singlecore_plan
            plan=build_singlecore_plan(session.raw)
            plan_name='singlecore_plan.json'
            result_name='result.json.gz'
            raw_name='official_result.json.gz'
            q3_original=None
        else:
            plan=read(Q3_ORIGINAL/'plan.json')
            plan_name='same_plan_no_l2_plan.json'
            result_name='same_plan_no_l2_result.json.gz'
            raw_name='same_plan_no_l2_official_result.json.gz'
            q3_original=read(Q3_ORIGINAL/'result.json.gz')
            write(dest/'original_q3_result.json.gz',q3_original)
        write(dest/plan_name,plan)
        write(dest/'input_graph.json',session.raw)
        (dest/'input_config.txt').write_bytes((spec['official']/'data/config.txt').read_bytes())
        print('ENTRY', 'singlecore_evaluate.evaluate_singlecore' if spec['q']==0 else 'multicore_cut_evaluate_problem_2.evaluate_scene_b',flush=True)
        print('EVALUATING',flush=True)
        result=session.evaluate(plan,spec['q'])
        write(dest/result_name,result)
        write(dest/raw_name,result['official_result'])
        end=datetime.now(timezone.utc)
        wall=time.perf_counter()-t0
        raw=result['official_result']
        info=dict(case=key,status=result['status'],start_utc=start.isoformat(),end_utc=end.isoformat(),wall_seconds=wall,official_eval_seconds=result['eval_seconds'],makespan=raw.get('makespan'),added_copy_bytes=raw.get('data_movement_bytes',{}).get('added_copy_bytes'),problem_evaluated=spec['q'],target_cores=spec['n'],entry='singlecore_evaluate.evaluate_singlecore' if spec['q']==0 else 'multicore_cut_evaluate_problem_2.evaluate_scene_b',source_graph=str(spec['graph']),source_config=str(spec['official']/'data/config.txt'),source_official_root=str(spec['official']),input_graph=str(dest/'input_graph.json'),input_config=str(dest/'input_config.txt'),plan=str(dest/plan_name),response=str(dest/result_name),raw_official_result=str(dest/raw_name),method_source=str(SNAP/'research_a_orion_trident'),fixed_theory_commit='489ec93a4c74683679e6a87a0175e4b8a3e3bbe1',run_scope='authorized_late_recalculation_not_original_600s_budget')
        if q3_original:
            q3=q3_original.get('official_result',q3_original)
            info.update(source_selected_q3_plan=str(Q3_ORIGINAL/'plan.json'),source_q3_response=str(Q3_ORIGINAL/'result.json.gz'),original_q3_makespan=q3.get('makespan'),same_plan_cache_ratio=(raw['makespan']/q3['makespan'] if result['status']=='ok' else None))
        write(dest/'execution.json',info)
        print('END',end.isoformat(),'STATUS',info['status'],'WALL_SECONDS',wall,'MAKESPAN',info['makespan'],'ADDED_COPY_BYTES',info['added_copy_bytes'],flush=True)
        if 'same_plan_cache_ratio' in info: print('SAME_PLAN_CACHE_RATIO',info['same_plan_cache_ratio'],flush=True)
        return 0 if result['status']=='ok' else 2
    except Exception as exc:
        import traceback
        end=datetime.now(timezone.utc)
        info=dict(case=key,status='error',start_utc=start.isoformat(),end_utc=end.isoformat(),wall_seconds=time.perf_counter()-t0,error=str(exc),traceback=traceback.format_exc())
        write(dest/'execution.json',info)
        print(info['traceback'],flush=True)
        return 1

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('case',choices=CASES)
    args=parser.parse_args()
    raise SystemExit(run(args.case))
