"""In-process calls to unchanged official functions; the controller owns the process.

No monkey-patching, performance surrogates never replace the official score.
"""
from __future__ import annotations
import sys
import time
from pathlib import Path
from .core import Graph, Config, one_core
from .worker import audit


def model_config(cfg, q, overrides=None):
    """Use the SAME hardware parameters for proposals/bounds and true scoring.

    Official default runs return the original immutable Config object unchanged.
    Non-default cache experiments must not prune with a default-bandwidth bound.
    """
    if q != 3 or not overrides:
        return cfg
    from dataclasses import replace
    return replace(cfg,
        cache_capacity=overrides.get('cache_capacity_bytes', cfg.cache_capacity),
        cache_bandwidth=overrides.get('cache_bandwidth_bytes_per_cycle', cfg.cache_bandwidth))


class OfficialSession:
    def __init__(self, official, graph_path, config):
        self.official=Path(official).resolve()
        sys.path.insert(0,str(self.official/'code'))
        from contest_io import _read_json
        from evaluation_validation import read_evaluation_config
        from multicore_cut_evaluate_problem_1 import evaluate_scene_a,read_scene_a_config
        from multicore_cut_evaluate_problem_2 import evaluate_scene_b,read_scene_b_config
        from multicore_cut_evaluate_problem_3 import evaluate_problem_3,read_cache_config
        from singlecore_evaluate import evaluate_singlecore
        self.raw=_read_json(str(graph_path));self.graph=Graph(self.raw)
        self.cfg=Config.read(config);self.settings=read_evaluation_config(str(config))
        self.a=read_scene_a_config(str(config));self.b=read_scene_b_config(str(config));self.c=read_cache_config(str(config))
        self.fn={0:evaluate_singlecore,1:evaluate_scene_a,2:evaluate_scene_b,3:evaluate_problem_3}

    def evaluate(self,plan,q,cache_overrides=None):
        kwargs=dict(self.settings)
        if q in (0,1):
            kwargs.update(cross_core_wait=self.a['task_cross_core_wait_cycles'],same_core_wait=self.a['task_same_core_wait_cycles'])
        else:
            kwargs['cross_core_copy_delay']=self.b['cross_core_copy_delay_cycles']
        if q==3:
            kwargs.update(self.c);kwargs.update(cache_overrides or {})
        st=time.perf_counter()
        result=self.fn[q](self.raw,**kwargs) if q==0 else self.fn[q](self.raw,plan,**kwargs)
        duration=time.perf_counter()-st
        check_cfg=self.cfg
        if cache_overrides:
            from dataclasses import replace
            check_cfg=replace(check_cfg,cache_capacity=kwargs['cache_capacity_bytes'],cache_bandwidth=kwargs['cache_bandwidth_bytes_per_cycle'])
        check=audit(self.graph,plan,result,q,check_cfg)
        return dict(status='ok' if check['ok'] else 'audit_failed',official_result=result,
                    audit=check,eval_seconds=duration,non_official=bool(cache_overrides))
