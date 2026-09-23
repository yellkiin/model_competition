"""Mathematics and bounded integration checks; NOT a prerequisite for local runs.

In a complete checkout, the unchanged official evaluators really execute synthetic
bipartite graphs. No mock scores or official-data performance claims are made.
"""
from __future__ import annotations
import itertools
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from .core import graph, normalize, relaxed_lower, assignment_path, predict, certificate
from .construct import construct, refine, window_optimize, paper_candidates, components
from .official import write, call
from .run import EXPECTED
from research_a.model import Plan, copy_accounting


def fixture(kind='chain', count=8):
    raw=dict(ops=[],tensors=[],edges=[])
    next_id=1000
    def tensor(pos='UB',size=16):
        nonlocal next_id
        next_id+=1;raw['tensors'].append(dict(id=next_id,pos=pos,size=size));return next_id
    def edge(a,b):raw['edges'].append(dict(source=a,target=b))
    for i in range(count):
        raw['ops'].append(dict(id=i+1,op='ADD',pipe='PIPE_M' if kind=='pipes' and i%2 else 'PIPE_V',cycles=[8,7,6,5][i%4]))
    inputs={}; outputs={}
    for i in range(count):outputs[i+1]=tensor()
    if kind=='chain': links=[(i,i+1) for i in range(1,count)]
    elif kind=='fork':links=[(1,i) for i in range(2,count)]+[(i,count) for i in range(2,count)]
    elif kind=='diamond':links=[(1,2),(1,3),(2,4),(3,4)]
    else:links=[]
    incoming={v for _,v in links};outgoing={u for u,_ in links}
    # A single original COPY_IN can feed multiple independent computations.
    shared=tensor() if kind=='shared' else None
    shared_copy_done=False
    copy_id=500
    for i in range(1,count+1):
        if i not in incoming:
            local=shared if shared is not None else tensor()
            if shared is None or not shared_copy_done:
                ddr=tensor('DDR');copy_id+=1
                raw['ops'].append(dict(id=copy_id,op='COPY_IN',pipe='PIPE_MTE2',cycles=1))
                edge(ddr,copy_id);edge(copy_id,local);shared_copy_done=True
            edge(local,i)
        edge(i,outputs[i])
        if i not in outgoing:
            ddr=tensor('DDR');copy_id+=1
            raw['ops'].append(dict(id=copy_id,op='COPY_OUT',pipe='PIPE_MTE3',cycles=1))
            edge(outputs[i],copy_id);edge(copy_id,ddr)
    for u,v in links:edge(outputs[u],v)
    return raw


def config_text():
    return '''[capacity]\nL1 524288\nUB 131072\n[bandwidth]\nbandwidth 60\n[multicore_scene_a]\ntask_cross_core_wait_cycles 1000\ntask_same_core_wait_cycles 100\n[multicore_scene_b]\ncross_core_copy_delay_cycles 500\n[problem_3]\ncache_capacity_bytes 1048576\ncache_bandwidth_bytes_per_cycle 250\n'''


class Mathematics(unittest.TestCase):
    def test_original_bipartite_counterexample(self):
        g=graph(fixture('chain',4));same=Plan([g.order],[0],2)
        split=Plan([g.order[:2],g.order[2:]],[0,1],2)
        self.assertEqual(relaxed_lower(g,2)['global_lower'],26)
        self.assertEqual(assignment_path(g,same,2,EXPECTED),26)
        self.assertEqual(assignment_path(g,split,2,EXPECTED),526)
        self.assertGreater(predict(g,split,2,EXPECTED)['score'],predict(g,same,2,EXPECTED)['score'])

    def test_fractional_assignment_bound(self):
        g=graph(fixture('independent',12))
        self.assertEqual(relaxed_lower(g,3)['fractional_load'],sum(g.cost.values())/3)
        self.assertGreaterEqual(relaxed_lower(g,3)['global_lower'],max(g.cost.values()))

    def test_construct_three_questions_five_core_counts(self):
        for kind in ('chain','fork','diamond','independent','shared','pipes'):
            g=graph(fixture(kind,4 if kind=='diamond' else 8))
            for q in (1,2,3):
                for n in range(1,6):
                    p=construct(g,n,q,EXPECTED);normalize(g,p)
                    self.assertEqual(len(p.json()['core_schedules']),n)
                    self.assertEqual(len(p.json()['node_to_subgraph']),len(g.ids))

    def test_refinement_retains_parent_surrogate(self):
        for q in (1,2,3):
            g=graph(fixture('fork',8));p=construct(g,3,q,EXPECTED)
            better,info=refine(g,p,q,EXPECTED,seconds=20)
            self.assertLessEqual(predict(g,better,q,EXPECTED)['score'],predict(g,p,q,EXPECTED)['score'])
            self.assertFalse(info['official_improvement_claimed'])

    def test_restricted_branch_bound_matches_exhaustive(self):
        g=graph(fixture('independent',3));parent=Plan([[u] for u in g.ids],[0]*3,2)
        best,info=window_optimize(g,parent,2,EXPECTED,width=3,node_limit=100,seconds=20)
        exact=min(predict(g,Plan(parent.blocks,list(ks),2),2,EXPECTED)['score']
                  for ks in itertools.product(range(2),repeat=3))
        self.assertAlmostEqual(predict(g,best,2,EXPECTED)['score'],exact)
        self.assertTrue(info['exhaustive'])

    def test_integer_window_budget_not_optimality_claim(self):
        g=graph(fixture('independent',8));p=Plan([[u] for u in g.ids],[0]*8,4)
        _,info=window_optimize(g,p,2,EXPECTED,node_limit=1,seconds=20)
        self.assertFalse(info['exhaustive'])

    def test_paper_candidates_are_explicit_reimplementations(self):
        g=graph(fixture('fork',12));plans=list(paper_candidates(g,3))
        self.assertEqual([x[0] for x in plans],['draft_components','draft_bands8'])
        for _,p in plans:normalize(g,p)

    def test_supplied_plan_ids_and_order_preserved(self):
        g=graph(fixture('independent',4))
        value={'node_to_subgraph':{'1':90,'2':90,'3':17,'4':17},'core_schedules':[[90],[17],[]]}
        p=normalize(g,Plan.load(value,g));self.assertEqual(p.json(),value)
        self.assertEqual(len(p.owners),2)

    def test_relaxed_bound_not_candidate_bound(self):
        g=graph(fixture('chain',4));p=Plan([g.order[:2],g.order[2:]],[0,1],2)
        self.assertLess(relaxed_lower(g,2)['global_lower'],assignment_path(g,p,2,EXPECTED))

    def test_shared_input_is_not_compute_dependency(self):
        g=graph(fixture('shared',6));self.assertEqual(len(components(g)),6)
        self.assertGreater(copy_accounting(g,Plan([[u] for u in g.ids],list(range(6)),6),2)['pre_spill_bytes'],g.original_copy)

    def test_partial_results_never_full_mean(self):
        from .report import collect
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);write(root/'manifest.json',dict(cases=['case_001'],cores=[2,5],formal_scope=False,baseline_kind='test'))
            result=collect(root)
            self.assertFalse(result['complete'])
            self.assertTrue(all(r['mean_speedup'] is None for r in result['summary']))
            self.assertFalse(json.loads((root/'report/status.json').read_text())['formal_full100_complete'])

    def test_copy_core_model_differs_from_task_model(self):
        # One source plus three remote consumer tasks. Shared source write is
        # once in Q1 but one COPY pair per remote core in Q2.
        raw=fixture('fork',5);g=graph(raw)
        p=Plan([[1],[2],[3],[4],[5]],[0,1,2,3,0],4)
        a=copy_accounting(g,p,1)['pre_spill_bytes'];b=copy_accounting(g,p,2)['pre_spill_bytes']
        self.assertNotEqual(a,b)


class OfficialSynthetic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root=Path(__file__).resolve().parents[1]
        found=list((root/'题目'/'A题').glob('*附件/code'))
        if not found:raise unittest.SkipTest('Official source is not mounted locally; complete checkout CI executes this class')
        cls.code=found[0]

    def test_all_questions_original_api_and_cli(self):
        rows=[]
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);source=root/'graph.json';config=root/'config.txt';config.write_text(config_text())
            for kind in ('chain','fork','shared','pipes'):
                raw=fixture(kind,8);write(source,raw);g=graph(raw)
                base,_=call(self.code,config,source,None,0,root/'base',20)
                self.assertEqual(base['status'],'ok',base)
                for q in (1,2,3):
                    p=construct(g,3,q,EXPECTED)
                    record,response=call(self.code,config,source,p,q,root/f'{kind}_q{q}',20)
                    self.assertEqual(record['status'],'ok',record)
                    cert=certificate(g,p,q,EXPECTED,response,base['makespan'])
                    self.assertLessEqual(cert['global_lower'],record['makespan'])
                    self.assertLessEqual(record['makespan'],cert['analytic_upper'])
                    rows.append(dict(kind=kind,question=q,makespan=record['makespan'],lower=cert['global_lower'],upper=cert['analytic_upper']))
                    if kind=='chain':
                        plan=root/'plan.json';write(plan,p.json());result=root/f'cli{q}.json'
                        proc=subprocess.run([sys.executable,str(self.code/f'multicore_cut_evaluate_problem_{q}.py'),str(source),str(plan),
                                             '--config',str(config),'-o',str(result),'--trace-output',str(root/'trace.json'),'--log-output',str(root/'log.txt')],
                                            capture_output=True,text=True,encoding='utf-8',timeout=20)
                        self.assertEqual(proc.returncode,0,proc.stderr)
                        self.assertEqual(json.loads(result.read_text(encoding='utf-8'))['makespan'],record['makespan'])
            print('OFFICIAL_SYNTHETIC_RESULT='+json.dumps(rows))

    def test_original_chain_cross_core_bound(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);raw=fixture('chain',4);source=root/'g.json';write(source,raw)
            config=root/'config.txt';config.write_text(config_text());g=graph(raw)
            split=Plan([g.order[:2],g.order[2:]],[0,1],2)
            for q in (1,2,3):
                rec,result=call(self.code,config,source,split,q,root/f'q{q}',20)
                self.assertEqual(rec['status'],'ok',rec)
                cert=certificate(g,split,q,EXPECTED,result)
                self.assertGreaterEqual(rec['makespan'],cert['candidate_lower'])


    def test_case_job_exports_all_questions_and_singlecore_definition(self):
        from unittest.mock import patch
        import shutil
        from . import run as runner, __version__
        from .report import collect
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);attachment=root/'题目'/'A题'/'synthetic 附件'
            shutil.copytree(self.code,attachment/'code')
            write(attachment/'data/case_001.json',fixture('fork',8))
            (attachment/'data/config.txt').write_text(config_text())
            out=root/'results';write(out/'manifest.json',dict(algorithm=__version__,config=EXPECTED,
                cases=['case_001'],cores=[1,2],profile='balanced',eval_seconds=20,case_seconds=120,
                max_calls=40,imported={},formal_scope=False,baseline_kind='synthetic_reimplementation'))
            with patch.object(runner,'ROOT',root):runner.case_job(out,'case_001')
            report=collect(out)
            self.assertTrue(report['complete'])
            self.assertEqual(len(report['rows']),6)
            self.assertEqual([r['speedup'] for r in report['rows'] if r['cores']==1 and r['question'] in (1,2)],[1.,1.])
            for q in (1,2,3):
                self.assertTrue((out/'cases/case_001'/f'q{q}/n2/case_001_multicore_res.json').exists())
            self.assertFalse(json.loads((out/'report/status.json').read_text())['formal_full100_complete'])
            print('OFFICIAL_SYNTHETIC_BATCH_COMPLETE=true')

    def test_standalone_solver_cli(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);source=root/'g.json';write(source,fixture('fork',8))
            cfg=root/'config.txt';cfg.write_text(config_text());out=root/'solve'
            proc=subprocess.run([sys.executable,'-X','utf8','-m','research_a_next.solve',str(source),
               '--code',str(self.code),'--config',str(cfg),'--question','2','--cores','3',
               '--method','fast','--out',str(out),'--seconds','60'],capture_output=True,text=True,timeout=70)
            self.assertEqual(proc.returncode,0,proc.stderr+((out/'process.log').read_text(encoding='utf-8') if (out/'process.log').exists() else ''))
            self.assertTrue((out/'g_multicore_res.json').exists())
            self.assertEqual(json.loads((out/'solver.json').read_text())['status'],'ok')


if __name__=='__main__':unittest.main()
