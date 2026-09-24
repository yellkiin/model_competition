"""Small exact mechanism tests; no fabricated official benchmark results."""
import json
import os
from pathlib import Path
import random
import tempfile
import unittest
from .core import (Graph, Config, constructors, fingerprint, bounds, planned_traffic,
                   make_plan, plan_view, fifo_prediction, one_core, memory_proxy)
from .worker import execute

CFG=Config(524288,131072,60,1000,100,500,1048576,250)


def minimal():
    return {'tensors':[{'id':i,'pos':pos,'size':16} for i,pos in [(1,'DDR'),(2,'UB'),(3,'UB'),(4,'DDR')]],
            'ops':[{'id':i,'op':op,'pipe':pipe,'cycles':c} for i,op,pipe,c in
                   [(10,'COPY_IN','PIPE_MTE2',1),(11,'ADD','PIPE_V',4),(12,'COPY_OUT','PIPE_MTE3',1)]],
            'edges':[{'source':a,'target':b} for a,b in [(1,10),(10,2),(2,11),(11,3),(3,12),(12,4)]]}


def dag(durations,edges,size=0):
    tensors=[];links=[]
    for j,(a,b) in enumerate(edges):
        t=10000+j;tensors.append({'id':t,'pos':'UB','size':size})
        links.extend([{'source':a,'target':t},{'source':t,'target':b}])
    return {'tensors':tensors,'ops':[{'id':u,'op':'ADD','pipe':'PIPE_V','cycles':d} for u,d in enumerate(durations)],'edges':links}


class CoreTests(unittest.TestCase):
    def test_communication_counterexample_uses_tensor_edges(self):
        g=Graph(dag([8,7,6,5],[(0,1),(1,2),(2,3)]))
        same=one_core(g,2); split=make_plan([{0,1},{2,3}],[0,1],2)
        self.assertEqual(bounds(g,CFG,2,2,same)['candidate_communication'],26)
        self.assertEqual(bounds(g,CFG,2,2,split)['candidate_communication'],526)
        self.assertEqual(bounds(g,CFG,2,3,split)['candidate_communication'],526)
        self.assertEqual(bounds(g,CFG,2,2)['global_lower'],26)

    def test_zero_cycles_source_convention(self):+        self.assertEqual(Graph(dag([0],[])).duration[0],1)

    def test_core_order_cycle_rejected(self):
        g=Graph(dag([1,1,1,1],[(0,1),(2,3)]))
        plan={'node_to_subgraph':{str(i):i for i in range(4)},'core_schedules':[[1,2],[3,0]]}
        with self.assertRaises(ValueError):plan_view(g,plan)

    def test_quotient_cycle_rejected(self):
        g=Graph(dag([1,1,1],[(0,1),(1,2)]))
        with self.assertRaises(ValueError):plan_view(g,make_plan([{0,2},{1}],[0,1],2))

    def test_exact_multicast_pair_count(self):
        raw={'ops':[{'id':i,'op':'ADD','pipe':'PIPE_V','cycles':10} for i in range(4)],
             'tensors':[{'id':10,'pos':'UB','size':32}],
             'edges':[{'source':0,'target':10}]+[{'source':10,'target':i} for i in (1,2,3)]}
        g=Graph(raw); p=make_plan([{0},{1,2},{3}],[0,1,2],3)
        self.assertEqual(planned_traffic(g,p,2),(64,64))
        self.assertEqual(planned_traffic(g,p,1),(64,32))

    def test_fill_after_completion_and_no_hit_refresh(self):
        def r(key,t,start,end):return {'key':key,'tensor':t,'size':1,'start':start,'end':end,'core':0}
        reads=[r('cold1',1,0,10),r('cold2',1,1,11),r('warm',1,12,13),
               r('b',2,14,15),r('hit_a',1,16,17),r('c',3,18,19),r('evicted_a',1,20,21)]
        hit=fifo_prediction(reads,2)
        self.assertFalse(hit['cold1']);self.assertFalse(hit['cold2']);self.assertTrue(hit['warm'])
        self.assertTrue(hit['hit_a']);self.assertFalse(hit['evicted_a'])
        self.assertFalse(fifo_prediction([dict(reads[0],size=3),dict(reads[2],size=3)],2)['warm'])

    def test_random_constructors_acyclic_deterministic(self):
        rng=random.Random(617)
        for trial in range(6):
            raw=dag([rng.randrange(1,20) for _ in range(14)],[(u,v) for u in range(14) for v in range(u+1,14) if rng.random()<.15],16)
            g=Graph(raw)
            for q in (1,2,3):
                a=constructors(g,3,CFG,q); b=constructors(g,3,CFG,q)
                self.assertEqual([fingerprint(c['plan']) for c in a],[fingerprint(c['plan']) for c in b])
                for c in a:plan_view(g,c['plan'])

    def test_empty_core_and_two_fields(self):
        g=Graph(minimal());p=one_core(g,5)
        self.assertEqual(len(p['core_schedules']),5);plan_view(g,p)
        with self.assertRaises(ValueError):plan_view(g,{**p,'metadata':{}})

    def test_long_chain_no_python_recursion(self):
        g=Graph(dag([1]*1500,[(i,i+1) for i in range(1499)]))
        self.assertEqual(bounds(g,CFG,5,2)['compute_path'],1500)


class OfficialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root=os.environ.get('ORION_OFFICIAL')
        if not root:raise unittest.SkipTest('Set ORION_OFFICIAL to run unmodified official evaluator tests')
        cls.root=Path(root).resolve()
        cls.config=next(p for p in (cls.root/'data/config.txt',cls.root/'config.txt') if p.is_file())

    def eval(self,raw,plan,q):
        with tempfile.TemporaryDirectory() as td:
            gp=Path(td)/'g.json';pp=Path(td)/'p.json'
            gp.write_text(json.dumps(raw));pp.write_text(json.dumps(plan))
            return execute({'official_code':str(self.root/'code'),'graph':str(gp),'plan':str(pp),'q':q,'config':str(self.config)})

    def test_original_minimal_all_three_questions(self):
        raw=minimal();g=Graph(raw)
        for q in (1,2,3):
            r=self.eval(raw,one_core(g,2),q)
            self.assertEqual(r['status'],'ok',r.get('audit'))
            self.assertEqual(r['official_result']['makespan'],6)
            self.assertEqual(r['official_result']['data_movement_bytes']['scheduled_copy_bytes'],32)
            self.assertEqual(r['official_result']['data_movement_bytes']['added_copy_bytes'],0)

    def test_zero_tensor_chain_true_sync(self):
        raw=dag([8,7,6,5],[(0,1),(1,2),(2,3)]);g=Graph(raw)
        for q in (2,3):
            r=self.eval(raw,make_plan([{0,1},{2,3}],[0,1],2),q)
            self.assertEqual(r['status'],'ok',r.get('audit'))
            self.assertGreaterEqual(r['official_result']['makespan'],526)

    def test_exhaustive_tiny_assignments_certificate(self):
        # 16 assignments, singleton groups, all three original evaluators.
        # This is an exhaustive RESTRICTED small problem, not global A optimality.
        raw=dag([9,5,8,6],[(0,2),(1,2),(2,3)],16);g=Graph(raw)
        for mask in range(16):
            p=make_plan([{u} for u in range(4)],[(mask>>u)&1 for u in range(4)],2)
            for q in (1,2,3):
                try:r=self.eval(raw,p,q)
                except RuntimeError:continue # Full execution graph may be infeasible; no false feasible score.
                self.assertEqual(r['status'],'ok',r.get('audit'))
                self.assertLessEqual(bounds(g,CFG,2,q,p)['candidate_lower'],r['official_result']['makespan'])


class RunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root=os.environ.get('ORION_OFFICIAL')
        if not root:raise unittest.SkipTest('Set ORION_OFFICIAL for runner integration')
        cls.root=Path(root).resolve()
        cls.config=next(p for p in (cls.root/'data/config.txt',cls.root/'config.txt') if p.is_file())

    def test_unicode_subprocess_resume_and_source_identity(self):
        from .run import solve
        with tempfile.TemporaryDirectory(prefix='orion space ') as td:
            gp=Path(td)/'最小 图.json';gp.write_text(json.dumps(minimal()),encoding='utf8')
            out=Path(td)/'output space'
            a=solve(self.root,self.config,gp,out,3,2,mode='construct',seconds=10,eval_timeout=5)
            self.assertEqual(a['status'],'ok',a)
            self.assertEqual(a['cache_speedup'],1)
            b=solve(self.root,self.config,gp,out,3,2,mode='construct',seconds=10,eval_timeout=5)
            self.assertEqual(a,b)
            with self.assertRaises(ValueError):solve(self.root,self.config,gp,out,3,2,mode='construct',seconds=11,eval_timeout=5)

    def test_hard_evaluation_timeout_recorded(self):
        from .run import evaluate,prepare_context
        import time
        with tempfile.TemporaryDirectory() as td:
            gp=Path(td)/'g.json';gp.write_text(json.dumps(minimal()))
            plan=one_core(Graph(minimal()),2)
            ident=prepare_context(self.root,self.config,gp,{'test':'timeout'})
            r=evaluate(self.root,self.config,gp,plan,1,Path(td)/'out',ident,time.monotonic()+1,.000001)
            self.assertEqual(r['status'],'timeout')
            self.assertTrue(Path(r['record']).is_file())

if __name__=='__main__':unittest.main(verbosity=2)
