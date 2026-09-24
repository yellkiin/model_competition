"""Structural, budget, persistence and original-evaluator regression tests."""
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from .test_core import dag,minimal,CFG
from .core import Graph,make_plan,plan_view,fingerprint
from .strategies import stage_candidates,fine_candidates,joint_window,memory_window_order,mutations
from .campaign import required,list_bound,estimate_cap
from .transfer import rewrite
from .supervisor import run_job
from .solver import read

class StructuralTests(unittest.TestCase):
    def test_cache_model_parameters_match_experiment(self):
        from .engine import model_config
        self.assertIs(model_config(CFG,3),CFG)
        self.assertIs(model_config(CFG,2,{'cache_capacity_bytes':123}),CFG)
        changed=model_config(CFG,3,{'cache_capacity_bytes':4194304,'cache_bandwidth_bytes_per_cycle':500})
        self.assertEqual(changed.cache_capacity,4194304)
        self.assertEqual(changed.cache_bandwidth,500)
        self.assertEqual(changed.bandwidth,CFG.bandwidth)
        self.assertNotEqual(changed.cache_bandwidth,CFG.cache_bandwidth)

    def test_stage_fine_and_dp_preserve_coverage(self):
        g=Graph(dag([3,2,7,4,2,5,6,1],[(0,2),(1,2),(2,4),(3,5),(4,6),(5,7)],16))
        for q in (1,2,3):
            stream=list(stage_candidates(g,3,CFG,q))+list(fine_candidates(g,3,CFG,q))
            self.assertGreaterEqual(len(stream),8)
            for c in stream:plan_view(g,c['plan']);self.assertEqual(set(c['plan']),{'node_to_subgraph','core_schedules'})
    def test_joint_and_local_live_dp_are_acyclic(self):
        g=Graph(dag([4]*10,[(i,i+2) for i in range(8)],16));p=make_plan([{i} for i in range(10)],[i%3 for i in range(10)],3)
        for q in (1,2,3):
            for r in range(3):
                cs=joint_window(g,p,CFG,q,{},r)+list(mutations(g,p,CFG,q,{},r))
                mem=memory_window_order(g,p,CFG,q,r)
                if mem:cs.append(mem)
                for c in cs:plan_view(g,c['plan'])
    def test_formal_mandatory_counts(self):
        rows=required([f'case_{i:03d}' for i in range(1,101)])
        self.assertEqual(len(rows),1400);self.assertEqual(sum(q==3 for _,q,_ in rows),500)
        self.assertNotIn(('case_001',1,1),rows)
    def test_list_envelope(self):
        caps=[2,8,9,4,5];loads=[0,0]
        for c in caps:loads[loads.index(min(loads))]+=c
        self.assertLessEqual(max(loads),list_bound(caps,2))
    def test_relocation_only_path_prefix(self):
        obj={'plan':'C:\\old\\runs\\a.json','x':'unrelated C:\\old\\runs'}
        val=rewrite(obj,'C:\\old\\runs','/new')
        self.assertEqual(val['plan'],'/new/a.json');self.assertEqual(val['x'],obj['x'])
    def test_calibration_adequacy_not_a_theorem(self):
        self.assertGreater(estimate_cap(20000,0,1,[(18000,0,1,80,1)],1),160)

class RuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.environ.get('ORION_OFFICIAL'):raise unittest.SkipTest('Set ORION_OFFICIAL for original evaluator tests')
        cls.root=Path(os.environ['ORION_OFFICIAL']).resolve()
        cls.cfg=next(p for p in [cls.root/'config.txt',cls.root/'data/config.txt'] if p.exists())
    def test_unicode_whole_process_resume_and_fixed_pair(self):
        with tempfile.TemporaryDirectory(prefix='ORION 中文 ') as td:
            p=Path(td);gp=p/'最小 图.json';gp.write_text(json.dumps(minimal()),encoding='utf8')
            kwargs=dict(official=self.root,config=self.cfg,graph=gp,folder=p/'out',q=3,n=2,seconds=5,max_evaluations=3)
            a=run_job(**kwargs);self.assertEqual(a['status'],'ok',a)
            self.assertEqual(a,run_job(**kwargs))
            with self.assertRaises(ValueError):run_job(**{**kwargs,'seconds':6})
            b=run_job(self.root,self.cfg,gp,p/'pair',2,2,5,1,fixed_plan=a['plan'])
            self.assertEqual(a['plan_hash'],b['plan_hash']);self.assertEqual(a['makespan'],b['makespan'])
            c=run_job(self.root,self.cfg,gp,p/'refine',3,2,5,4,seed_job=a['job'])
            self.assertLessEqual(c['makespan'],a['makespan'])
    def test_seed_hardware_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);gp=p/'g.json';gp.write_text(json.dumps(minimal()))
            seed=run_job(self.root,self.cfg,gp,p/'seed',3,2,5,1)
            self.assertEqual(seed['status'],'ok')
            with self.assertRaisesRegex(ValueError,'cache parameters differ'):
                run_job(self.root,self.cfg,gp,p/'new',3,2,5,1,seed_job=seed['job'],
                        cache_overrides={'cache_bandwidth_bytes_per_cycle':500})

    def test_interrupted_policy_mismatch_rejected_before_archival(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);gp=p/'g.json';gp.write_text(json.dumps(minimal()))
            job=p/'out';s=run_job(self.root,self.cfg,gp,job,2,2,5,1)
            self.assertEqual(s['status'],'ok')
            (job/'summary.json').unlink()  # Emulate a crash after a valid checkpoint.
            with self.assertRaisesRegex(ValueError,'Interrupted job policy'):
                run_job(self.root,self.cfg,gp,job,2,2,6,1)
            self.assertTrue((job/'progress.json').exists())

    def test_deadline_no_false_feasible_score(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);gp=p/'g.json';gp.write_text(json.dumps(minimal()))
            r=run_job(self.root,self.cfg,gp,p/'out',2,2,.00001,2)
            self.assertNotEqual(r['status'],'ok');self.assertNotIn('makespan',r)
            r=run_job(self.root,self.cfg,gp,p/'expired',2,2,1,2,deadline_epoch=time.time()-1)
            self.assertEqual(r['status'],'not_started_global_deadline')

if __name__=='__main__':unittest.main(verbosity=2)
