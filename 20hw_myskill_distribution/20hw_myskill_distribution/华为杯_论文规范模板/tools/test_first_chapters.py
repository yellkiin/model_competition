"""Synthetic source-contract cases; no generated fixture is research evidence."""
from pathlib import Path
import copy
import json
import tempfile
import unittest
from first_chapters import (audit_source, source_bindings, REVIEW_DIMENSIONS,
                            symbol_rows, symbol_source_errors, independent_symbol_error)
from first_chapters_pdf import page_limits

SCENARIOS = {
 'data': dict(background='传感器记录存在连续缺测，直接比较每日均值会混淆缺测时段与真实变化。已有逐小时观测可用于识别可用区间，因此需要在明确的时间范围内分析变化并预测。',
              task='利用2024年逐小时观测预测未来24小时的流量，至少比较2种方法，并按时间顺序验证。',
              required=['2024年','未来24小时','至少','2种','按时间顺序验证']),
 'physics': dict(background='薄板受边界热流驱动，不同位置的温度变化受到传导与边界条件共同影响。题目给定材料参数和初始温度，需要据此计算温度场及离散误差，而不把局部测点视作全场温度。',
                 task='使用有限差分法求解二维热传导方程，在绝热边界下模拟0至60秒的温度场，并比较网格加密后的误差。',
                 required=['有限差分法','二维','绝热','0至60秒','比较网格加密后的误差']),
 'optimization': dict(background='固定运力下，配送资源在不同需求点之间相互竞争。已知需求和通行时间能够界定可行路线，但仅缩短单条路线不能保证整体费用较低，需要同时考虑时限与成本。',
                      task='在至多3辆车且每条路线不超过8小时的条件下设计配送方案，最小化总费用，输出路线及费用；不考虑交通随机波动。',
                      required=['至多3辆','且','不超过8小时','最小化总费用','路线及费用','不考虑交通随机波动'])}


def fixture_evidence(root, manifest, scenario='data'):
    """Explicit synthetic test attestations, never used to certify production prose."""
    text=(root/'c1.tex').read_text(encoding='utf8')
    body=text.split(r'\subsection{问题重述}')[-1].strip()
    background=text.split(r'\subsection{问题背景}')[-1].split(r'\subsection{问题重述}')[0].strip()
    q=sum(c['role']=='problem' for c in manifest['chapters'])
    source=root/'fixture_problem.txt'
    source.write_text('简化测试题，不是正式赛题。\n'+background+'\n'+body,encoding='utf8')
    ref=lambda quote:dict(source_id='problem',location='简化测试题正文',quote=quote)
    evidence={'sources':[dict(id='problem',path=source.relative_to(root.parent).as_posix(),kind='problem')],
      'context':{k:[dict(text=background,source=ref(background))] for k in ('object_scene','difficulty_causes','scope_exclusions','shared_conditions')},
      'tasks':[dict(order=i,original_id=str(i),source=ref(body),inputs=['测试输入'],action='按测试原文执行',object='测试对象',conditions=SCENARIOS[scenario]['required'],outputs=['原文所列输出'],validation=[],depends_on=[],required_methods=['有限差分法'] if scenario=='physics' else [],subtasks=[],literal_requirements=SCENARIOS[scenario]['required'] if SCENARIOS[scenario]['task'] in body else [],coverage=dict(status='verified',restatement_quote=body,observation='合成回归记录：逐字保留上述简化题条件；不授予真实论文语义审核。')) for i in range(1,q+1)],
      'claims':[dict(text=background,kind='problem',source=ref(background))], 'gaps':[], 'symbols':[],
      'review':dict(reviewer='synthetic-contract-test',reviewed_at='fixture-not-a-real-review',findings=[],**{k:dict(status='verified',observation='合成测试字段；仅验证合同执行，正式项目须由实际阅读替代。') for k in REVIEW_DIMENSIONS})}
    for row in symbol_rows((root/'c3.tex').read_text(encoding='utf8')):
        quote=r'\GMCMSymbolRow{'+row['category']+'}{'+row['symbol']+'}{'+row['meaning']+'}{'+row['unit']+'}'
        evidence['symbols'].append(dict(**row,scope='隔离排版测试',in_core_table=True,first_definition=dict(tex_path='c3.tex',quote=quote),uses=[dict(tex_path='c3.tex',quote=quote)]))
    manifest['first_chapters_evidence_path']='fixture_evidence.json'
    manifest['first_chapters_review_path']='first-three.review.json'
    evidence['review']['bindings']=source_bindings(manifest,root,evidence)
    (root/'fixture_evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf8')
    return evidence


class FirstChaptersTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        from test_paper_contract import make_fixture
        self.manifest=make_fixture(self.root,1)

    def write(self,e):
        (self.root/'fixture_evidence.json').write_text(json.dumps(e,ensure_ascii=False),encoding='utf8')

    def scenario(self,name):
        s=SCENARIOS[name]
        (self.root/'c1.tex').write_text('\\section{问题重述}\n\\subsection{问题背景}\n'+s['background']+'\n\\subsection{问题重述}\n问题1：'+s['task'],encoding='utf8')
        return fixture_evidence(self.root,self.manifest,name)

    def test_three_different_task_structures_and_prescribed_method(self):
        for name in SCENARIOS:
            self.scenario(name)
            self.assertEqual(audit_source(self.manifest,self.root)['status'],'PASS',name)

    def test_missing_subtask_or_condition_time_and_quantifier(self):
        e=self.scenario('data')
        for phrase in ('2024年','未来24小时','至少'):
            broken=copy.deepcopy(e)
            broken['tasks'][0]['coverage']['restatement_quote']=broken['tasks'][0]['coverage']['restatement_quote'].replace(phrase,'改动')
            self.write(broken)
            self.assertTrue(any('限定' in f for f in audit_source(self.manifest,self.root)['failures']))
        broken=copy.deepcopy(e)
        broken['tasks'][0]['subtasks']=[dict(original_id='1.b',source=e['tasks'][0]['source'],coverage=dict(status='pending',restatement_quote='',observation='遗漏原题验证子项'))]
        self.write(broken)
        self.assertEqual(audit_source(self.manifest,self.root)['status'],'FAIL')

    def test_unsupported_claim_author_algorithm_and_result_are_hard(self):
        e=self.scenario('physics')
        for kind in ('author_method','author_result','author_assumption'):
            b=copy.deepcopy(e); b['claims'][0]['kind']=kind; self.write(b)
            self.assertTrue(any('倒灌' in f for f in audit_source(self.manifest,self.root)['failures']))
        b=copy.deepcopy(e); b['claims'][0]['source']['quote']='传统技术完全失效'; self.write(b)
        self.assertTrue(any('摘录' in f for f in audit_source(self.manifest,self.root)['failures']))

    def test_semantic_hard_finding_vs_style_advice(self):
        e=self.scenario('optimization')
        e['review']['findings']=[dict(severity='style',message='背景转折可以更紧凑',resolved=False)]
        self.write(e); r=audit_source(self.manifest,self.root)
        self.assertEqual(r['status'],'PASS'); self.assertTrue(r['warnings'])
        e['review']['findings'].append(dict(severity='hard',message='将至多改成至少改变了可行域',resolved=False))
        self.write(e); self.assertEqual(audit_source(self.manifest,self.root)['status'],'FAIL')

    def test_changed_source_and_missing_definition_fail(self):
        e=self.scenario('data'); e['symbols'][0]['first_definition']['quote']='不存在的定义'; self.write(e)
        self.assertTrue(any('首次定义' in f for f in audit_source(self.manifest,self.root)['failures']))
        self.scenario('data')
        with (self.root/'c4.tex').open('a',encoding='utf8') as f:f.write('源变化')
        self.assertTrue(any('过期' in f for f in audit_source(self.manifest,self.root)['failures']))

    def test_one_independent_object_not_one_character(self):
        for good in ('x_{i,t}',r'\mathbf{x}',r'\mathcal{I}',r'\alpha_i'):
            self.assertFalse(independent_symbol_error(good))
        for bad in ('i,j,k',r'\alpha,\beta,\gamma',r'i\\j','i=j'):
            self.assertTrue(independent_symbol_error(bad))
        tex=(self.root/'c3.tex').read_text(encoding='utf8')
        self.assertTrue(symbol_source_errors(tex.replace(r'\end{GMCMSymbolTable}',r'\hline\end{GMCMSymbolTable}')))
        self.assertTrue(symbol_source_errors(tex.replace(r'\end{GMCMSymbolTable}',r'参数 & i,j & 合并定义 & 1\\\end{GMCMSymbolTable}')))

    def test_group_boundaries_and_deduplicated_same_page(self):
        for n,expected in ((2,False),(3,True),(6,True),(7,False)):
            ranges=[dict(content_pages=list(range(1,n))),dict(content_pages=[n-1]),dict(content_pages=[n-1,n])]
            checks=page_limits(ranges,{})
            self.assertTrue(checks[0]['ok'])
            self.assertEqual(checks[-1]['ok'],expected)
            self.assertEqual(checks[-1]['severity'],'warning')
            self.assertEqual(checks[0]['actual'],n)
        self.assertTrue(page_limits([dict(content_pages=[1]),dict(content_pages=[1,2]),dict(content_pages=[2,3])],{})[2]['ok'])
        self.assertFalse(page_limits([dict(content_pages=[1]),dict(content_pages=[2]),dict(content_pages=[2,3,4])],{})[2]['ok'])
        self.assertFalse(page_limits([dict(content_pages=[1]),dict(content_pages=[3]),dict(content_pages=[3,4])],{})[1]['ok'])

if __name__=='__main__':unittest.main()
