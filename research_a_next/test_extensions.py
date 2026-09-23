"""Additional real-evaluator FIFO and parameter-study checks; synthetic data only."""
from pathlib import Path
import json
import tempfile
import unittest
from .test_math import fixture, config_text
from .core import graph, normalize, certificate
from .construct import construct
from .official import write, call
from .run import EXPECTED
from research_a.model import Plan


class OfficialExtensions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root=Path(__file__).resolve().parents[1]
        found=list((root/'题目'/'A题').glob('*附件/code'))
        if not found:raise unittest.SkipTest('Official source is not mounted locally; complete checkout CI executes this class')
        cls.code=found[0]


    def test_actual_fifo_warm_read(self):
        # Core 0 fills shared X first. Core 1 naturally reads large Y before X.
        # This is a legal bipartite graph and real Pipe ordering, not a delay op.
        raw=fixture('shared',3)
        # Existing shared input is the COPY_IN output.
        in_op=next(o['id'] for o in raw['ops'] if o['op']=='COPY_IN')
        shared=next(e['target'] for e in raw['edges'] if e['source']==in_op)
        next(t for t in raw['tensors'] if t['id']==shared)['size']=4096
        original=next(e['source'] for e in raw['edges'] if e['target']==in_op)
        next(t for t in raw['tensors'] if t['id']==original)['size']=4096
        raw['edges'].remove({'source':shared,'target':3})
        raw['tensors'] += [dict(id=2000,pos='DDR',size=65536),dict(id=2001,pos='UB',size=65536)]
        raw['ops'].append(dict(id=600,op='COPY_IN',pipe='PIPE_MTE2',cycles=1))
        raw['edges'] += [dict(source=2000,target=600),dict(source=600,target=2001),dict(source=2001,target=3)]
        g=graph(raw);plan=normalize(g,Plan([[1],[3],[2]],[0,1,1],2))
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);source=root/'g.json';write(source,raw)
            cfg=root/'config.txt';cfg.write_text(config_text())
            rec,response=call(self.code,cfg,source,plan,3,root/'result',20)
            self.assertEqual(rec['status'],'ok',rec)
            self.assertGreater(response['cache_stats']['hit_bytes'],0)
            certificate(g,plan,3,EXPECTED,response)
            print('OFFICIAL_FIFO_HIT_BYTES='+str(response['cache_stats']['hit_bytes']))

    def test_parameter_axis_study_real_official(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        import shutil
        from . import sensitivity
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);attachment=root/'attachment';shutil.copytree(self.code,attachment/'code')
            raw=fixture('shared',4);g=graph(raw);plan=construct(g,2,3,EXPECTED)
            source=attachment/'data/case_001.json';write(source,raw)
            cfg=attachment/'data/config.txt';cfg.write_text(config_text())
            rec,response=call(self.code,cfg,source,plan,3,root/'anchor',20)
            self.assertEqual(rec['status'],'ok',rec)
            pilot=root/'pilot';write(pilot/'manifest.json',dict(config=EXPECTED))
            case=pilot/'cases/case_001/q3/n2'
            write(case/'case_001_multicore_res.json',plan.json());write(case/'best_result.json',response)
            with patch.object(sensitivity,'locate',lambda:attachment):
                sensitivity.worker(SimpleNamespace(source=pilot,out=root/'axes',cases=['case_001'],cores=2,minutes=1,eval_seconds=20))
            scope=json.loads((root/'axes/scope.json').read_text(encoding='utf-8'))
            self.assertEqual(scope['expected_rows'],10);self.assertEqual(scope['completed_rows'],10)
            self.assertTrue(scope['not_a_full100_score'])


if __name__=='__main__':unittest.main()
