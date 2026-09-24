#!/usr/bin/env python3
"""Regression tests for the Huawei Cup abstract content gate."""
from __future__ import annotations

import json
import hashlib
import re
import tempfile
import unittest
from pathlib import Path

from audit_abstract import audit_abstract_manifest, audit_problem_paragraph, ABSTRACT_TYPE_TERMS, simplify_tex, numeric_tokens, UNIT_RE
from paper_contract import commands


PASSING_ABSTRACT = r"""本文针对多源储能系统联合调度问题，建立混合整数线性规划与双层博弈模型，采用\textbf{分阶段滚动优化方法}，得到日均运行成本降低 12.70\%。

针对问题一，建立以系统运行成本最小化为目标、满足功率平衡与储能荷电状态约束的混合整数线性规划模型；采用\textbf{分段线性化与时序解耦算法}处理充放电互斥和跨时段耦合，通过净负荷曲线识别削峰窗口，并用边界条件保持首尾荷电状态一致。模型把设备容量、转换效率和价格信号放在统一决策空间内，使调度变量具有明确工程含义。得到最优日成本 126.40 万元、峰谷差 36.80 MW，说明基线场景下成本目标与电网平滑目标能够同时满足。

针对问题二，基于问题一的模型进一步考虑用户侧与运营商之间的收益分配，建立以双方效用最大化为目标、满足个体理性与功率交换约束的双层博弈模型；采用\textbf{KKT 条件等价转化算法}把下层响应嵌入上层定价，并用互补条件线性化减少重复搜索。求解过程保留价格边界、能量守恒和设备寿命限制，使均衡点可以由原始输入重新计算。得到运营商收益 48.20 万元、用户购能成本 73.60 万元，说明收益提升没有以破坏用户可接受性为代价。

针对问题三，在问题二基础上引入随机需求约束并推广至多场景运行，建立以期望成本和尾部风险最小化为目标、满足场景概率与备用容量约束的两阶段随机规划模型；采用\textbf{场景生成与拉格朗日分解方法}压缩大规模耦合变量，再依据概率权重合并子问题。该处理保持日前决策一致，并允许实时补偿变量随场景变化，从而区分可控偏差和不可控冲击。为避免少数高损失场景被期望值掩盖，模型同步保留尾部损失项，并通过相同随机种子重复生成场景以核对解的稳定性。该设计使日前计划、实时调整与风险惩罚具有一致的变量口径，也便于识别备用容量不足时的失效边界。得到期望总成本 131.20 万元、条件风险值 145.70 万元，说明随机需求下的风险代价能够被显式计量。

本文的创新点在于提出分阶段自适应权重调整策略，并把价格响应、储能寿命与尾部风险纳入同一求解链；相比固定权重基线，在相同停止条件下，超体积指标提升 8.30\%，平均求解时间降低 11.40\%，方法差异由统一口径的对照实验支持。

最后，采用独立重算、灵敏度分析和稳健性检验核对目标值、约束与场景响应；在关键参数波动 ±10.00\% 时，成本变化不超过 2.80\%，独立评价相对误差为 0.60\%，表明模型在给定数据范围和设备容量边界内保持稳定。"""


# Controlled content fixtures, not measured contest results. Baseline records
# remain independent of each mutation under test; no science approval is claimed.
CONCLUSIONS = ['成本目标与电网平滑目标能够同时满足', '收益提升没有以破坏用户可接受性为代价', '随机需求下的风险代价能够被显式计量']
_parts = PASSING_ABSTRACT.split('\n\n')
_parts[0] = _parts[0].replace('分阶段滚动优化方法', '分段线性化与时序解耦算法')
_parts[1] += '独立重算核查约束，日均运行成本降低12.70\\%。'
_parts[2] += '独立验证核对均衡条件。'
_parts[3] += '独立重算验证场景加权结果。'+_parts[4]
for _i in range(1,4):
    _parts[_i] = _parts[_i].replace('针对问题'+ '一二三'[_i-1], r'\textbf{针对问题'+'一二三'[_i-1]+'}')
    _parts[_i] = _parts[_i].replace(CONCLUSIONS[_i-1], r'\textbf{'+CONCLUSIONS[_i-1]+'}')
PASSING_ABSTRACT = '\n\n'.join(_parts[:4])
# Explicit numeric literals in this fixed fixture are all key results.
PASSING_ABSTRACT = re.sub(r'(\d+\.\d+\s*(?:\\%|万元|MW))', lambda m:r'\textbf{'+m.group(1)+'}', PASSING_ABSTRACT)


def write_evidence_fixture(root, manifest, baseline=PASSING_ABSTRACT):
    parts=baseline.split('\n\n')[1:4]
    source={}; questions=[]
    for i,(chapter,paragraph) in enumerate(zip(manifest['chapters'],parts),1):
        (root/chapter['tex_path']).write_text('\\section{测试}\n'+paragraph,encoding='utf-8')
        rows=[]; content={}; phrases=[c.argument for c in commands(paragraph,('textbf',))]
        for j,text in enumerate(phrases):
            if text.startswith('针对问题'):continue
            plain=simplify_tex(text).strip()
            if re.match(r'^\d',plain):
                m=numeric_tokens(plain)[0];unit=UNIT_RE.match(plain[m.end():]).group().strip()
                value={'value':float(m.group()),'unit':unit,'status':'verified'};kind='value'
            elif simplify_tex(text) in CONCLUSIONS:
                value={'text':text,'status':'verified'};kind='conclusion'
            else:value=text;kind='method'
            key=f's{j}';content[key]=value
            rows.append({'kind':kind,'text':text,'source_path':root.name+'/results.json','source_pointer':f'/q{i}/{key}','source_sha256':''})
        validation=['独立重算核查约束','独立验证核对均衡条件','独立重算验证场景加权结果'][i-1]
        content['validation']=validation
        rows.append({'kind':'validation','text':validation,'source_path':root.name+'/results.json','source_pointer':f'/q{i}/validation','source_sha256':''})
        source[f'q{i}']=content;questions.append({'chapter_id':chapter['chapter_id'],'statements':rows})
    result=root/'results.json';result.write_text(json.dumps(source,ensure_ascii=False),encoding='utf-8')
    digest=hashlib.sha256(result.read_bytes()).hexdigest()
    for question in questions:
        for row in question['statements']:row['source_sha256']=digest
    (root/'abstract-evidence.json').write_text(json.dumps({'schema_version':'1.0','questions':questions},ensure_ascii=False),encoding='utf-8')
    manifest['abstract_evidence_path']='abstract-evidence.json'


class AbstractAuditTests(unittest.TestCase):
    def make_project(self, abstract: str, keywords: list[str]) -> Path:
        root = Path(tempfile.mkdtemp(prefix="gmcm-abstract-test-"))
        self.addCleanup(__import__("shutil").rmtree, root)
        (root / "abstract.tex").write_text(abstract, encoding="utf-8")
        for name in ("q1.tex", "q2.tex", "q3.tex"):
            (root / name).write_text(r"\section{测试}", encoding="utf-8")
        manifest = {
            "title": "储能系统联合调度",
            "keywords": keywords,
            "abstract_tex_path": "abstract.tex",
            "chapters": [
                {"chapter_id": f"q{index}", "title": f"问题{index}", "role": "problem", "order": index, "tex_path": f"q{index}.tex", "abstract_type": "optimization"}
                for index in range(1, 4)
            ],
        }
        write_evidence_fixture(root, manifest)
        manifest_path = root / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        return manifest_path

    def test_each_type_uses_its_own_vocabulary(self):
        paragraphs = {
            "optimization": "建立成本最小化模型，满足容量约束，采用求解方法，得到成本12.00万元、耗时2.00秒。",
            "statistics": "选取分布指标，采用分组统计分析揭示差异趋势，得到平均流量12.00辆、差异2.00辆。",
            "prediction": "建立以频谱特征为输入的分类模型，采用分类方法并独立验证，得到准确率92.00%、召回率90.00%。",
            "mechanism": "依据守恒假设推导方程并检验量纲边界，得到相对误差2.00%、耗时1.00秒。",
            "simulation": "建立随机过程模型，采用多场景仿真验证分布一致性，得到误差2.00%、耗时1.00秒。",
            "evaluation": "依据指标权重采用综合评价并分析排序稳定性，得到评分92.00分、敏感性2.00%。",
            "interpretation": "采用特征归因解释影响并消融验证，得到贡献20.00%、扰动变化2.00%。",
            "theory": "依据连续性假设推导并证明关系式，给出该判据在正定条件下成立而在奇异边界不成立。",
        }
        self.assertEqual(set(paragraphs), set(ABSTRACT_TYPE_TERMS))
        for kind, paragraph in paragraphs.items():
            with self.subTest(kind=kind):
                review = audit_problem_paragraph(paragraph, {"abstract_type": kind,
                    "abstract_result_mode": "qualitative" if kind == "theory" else "quantitative"})
                self.assertTrue(review["ok"], review)

    def test_types_and_qualitative_exceptions_are_not_bypasses(self):
        theory = "依据假设推导证明定理，给出判据在正定条件下成立而在奇异边界不成立。"
        self.assertFalse(audit_problem_paragraph(theory, {"abstract_type": "optimization"})["ok"])
        self.assertFalse(audit_problem_paragraph(theory, {"abstract_type": "prediction", "abstract_result_mode": "qualitative"})["ok"])
        self.assertFalse(audit_problem_paragraph(theory, {})["ok"])
        self.assertFalse(audit_problem_paragraph("依据假设证明定理及成立条件，得到模型有效。",
                         {"abstract_type": "theory", "abstract_result_mode": "qualitative"})["ok"])

    def test_character_limits_stay_hard(self):
        for invalid in ("本文针对一个问题。", PASSING_ABSTRACT + "说明" * 900):
            manifest = self.make_project(invalid, ["储能调度", "混合整数线性规划", "双层博弈"])
            failures = {x["code"] for x in audit_abstract_manifest(manifest)["failures"]}
            self.assertIn("visible_character_target", failures)

    def test_independent_statistics_question_needs_no_optimization_or_dependency(self):
        parts = PASSING_ABSTRACT.split("\n\n")
        parts[2] = r"针对问题二，采用分组统计与分布分析，选取能量指标考察不同工况的差异和关联，对偏态分布进行稳健检验。分析保留设备和负荷分组，检查异常值对组间比较的影响，并用独立记录构造区间以避免重复窗口夸大样本数量。得到组间差异12.00\%、区间宽度2.00\%。该结果只说明观测范围内的统计关联，不推断因果关系。"
        manifest = self.make_project("\n\n".join(parts), ["储能调度", "分组统计", "双层博弈"])
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["chapters"][1]["abstract_type"] = "statistics"
        manifest.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        report = audit_abstract_manifest(manifest)
        codes={x["code"] for x in report["failures"]}
        self.assertNotIn("problem_2_model_method_result_loop", codes)
        self.assertNotIn("problem_2_progression", codes)
        self.assertEqual(report["status"], "FAIL")  # old evidence cannot approve the changed question
        data["chapters"][1]["depends_on_previous"] = True
        manifest.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        self.assertIn("problem_2_progression", {x["code"] for x in audit_abstract_manifest(manifest)["failures"]})

    def test_complete_abstract_passes(self) -> None:
        manifest = self.make_project(PASSING_ABSTRACT, ["储能调度", "混合整数线性规划", "双层博弈", "随机规划"])
        report = audit_abstract_manifest(manifest)
        self.assertEqual(report["status"], "PASS", report["failures"])

    def test_delivery_inventory_and_duplicate_keywords_fail(self) -> None:
        invalid = PASSING_ABSTRACT.replace(
            "本文的创新点在于",
            "最终交付包含 12 张科研图、完整源码和 JSON 文件。本文的创新点在于",
        )
        manifest = self.make_project(invalid, ["储能调度", "储能调度", "优化算法"])
        report = audit_abstract_manifest(manifest)
        failed_codes = {item["code"] for item in report["failures"]}
        self.assertIn("abstract_excludes_delivery_inventory", failed_codes)
        self.assertIn("keywords_are_unique_and_specific", failed_codes)

    def test_missing_problem_loop_and_bold_methods_fail(self) -> None:
        invalid = PASSING_ABSTRACT.replace("针对问题二", "对于问题二").replace(r"\textbf", r"\mbox")
        manifest = self.make_project(invalid, ["储能调度", "混合整数线性规划", "双层博弈"])
        report = audit_abstract_manifest(manifest)
        failed_codes = {item["code"] for item in report["failures"]}
        self.assertIn("one_ordered_paragraph_per_problem", failed_codes)
        self.assertIn("key_methods_are_selectively_bold", failed_codes)

    def test_four_emphasis_categories_are_independent(self):
        replacements = [
            (r'\textbf{针对问题一}', '针对问题一', 'problem_1_lead_is_bold'),
            (r'\textbf{分段线性化与时序解耦算法}', '分段线性化与时序解耦算法', '_short_span_bold'),
            (r'\textbf{'+CONCLUSIONS[0]+'}', CONCLUSIONS[0], '_short_span_bold'),
            (r'\textbf{126.40 万元}', r'\textbf{126.40} 万元', 'key_value_occurrence_bold:'),
        ]
        for old,new,code in replacements:
            with self.subTest(code=code):
                p=self.make_project(PASSING_ABSTRACT.replace(old,new), ['储能调度','混合整数线性规划','双层博弈'])
                codes=[r['code'] for r in audit_abstract_manifest(p)['failures']]
                self.assertTrue(any(code in c for c in codes), codes)

    def test_old_closing_and_internal_checks_are_rejected(self):
        for sentence in ['最后，独立验证得到误差0.60\\%，数据不足仍限制研究范围。',
                         '未来工作将进一步完善模型。', '尺寸压力测试通过内部验收。']:
            p=self.make_project(PASSING_ABSTRACT+'\n\n'+sentence,['储能调度','混合整数线性规划','双层博弈'])
            codes={r['code'] for r in audit_abstract_manifest(p)['failures']}
            self.assertIn('abstract_excludes_limitations_future_and_internal_checks',codes)
            self.assertIn('no_separate_validation_or_limitation_closing',codes)

    def test_wrong_value_or_unit_cannot_pass_by_bolding(self):
        for old,new in [('126.40','126.41'),('126.40 万元','126.40 MW')]:
            p=self.make_project(PASSING_ABSTRACT.replace(old,new),['储能调度','混合整数线性规划','双层博弈'])
            codes=[r['code'] for r in audit_abstract_manifest(p)['failures']]
            self.assertTrue(any(c.startswith('numeric_statement_traceable:') for c in codes),codes)

    def test_source_hash_and_body_binding(self):
        p=self.make_project(PASSING_ABSTRACT,['储能调度','混合整数线性规划','双层博弈'])
        result=p.parent/'results.json'
        result.write_text(result.read_text(encoding='utf-8')+'\n',encoding='utf-8')
        (p.parent/'q1.tex').write_text(r'\section{测试}不同正文',encoding='utf-8')
        codes=[r['code'] for r in audit_abstract_manifest(p)['failures']]
        self.assertTrue(any(c.endswith('_source_current') for c in codes))
        self.assertTrue(any(c.endswith('_in_corresponding_body') for c in codes))

    def test_nested_bold_and_more_than_eight_spans(self):
        text=PASSING_ABSTRACT.replace(r'\textbf{12.70\%}',r'\textbf{\num{12.70}\%}')
        p=self.make_project(text,['储能调度','混合整数线性规划','双层博弈'])
        report=audit_abstract_manifest(p)
        self.assertEqual(report['status'],'PASS',report['failures'])
        self.assertGreater(len(commands(text,('textbf',))),8)

    def test_repeated_question_marker_fails(self):
        p=self.make_project(PASSING_ABSTRACT+'\n\n'+PASSING_ABSTRACT.split('\n\n')[1],['储能调度','混合整数线性规划','双层博弈'])
        self.assertIn('problem_markers_exact_once_in_order',{r['code'] for r in audit_abstract_manifest(p)['failures']})

    def test_prediction_status_is_not_verified_truth(self):
        p=self.make_project(PASSING_ABSTRACT,['储能调度','混合整数线性规划','双层博弈'])
        source=p.parent/'results.json';data=json.loads(source.read_text(encoding='utf-8'))
        for value in data['q1'].values():
            if isinstance(value,dict) and 'text' in value:value['status']='prediction'
        source.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
        evidence=p.parent/'abstract-evidence.json';e=json.loads(evidence.read_text(encoding='utf-8'))
        digest=hashlib.sha256(source.read_bytes()).hexdigest()
        for q in e['questions']:
            for row in q['statements']:row['source_sha256']=digest
        evidence.write_text(json.dumps(e,ensure_ascii=False),encoding='utf-8')
        codes=[r['code'] for r in audit_abstract_manifest(p)['failures']]
        self.assertTrue(any(c.endswith('_prediction_not_ground_truth') for c in codes))

    def test_analytic_optimization_needs_no_invented_numbers(self):
        from abstract_evidence import evidence_gate
        from audit_abstract import problem_marker
        self.assertEqual(problem_marker(11),'十一')
        root=Path(tempfile.mkdtemp(prefix='abstract-analytic-test-'))
        self.addCleanup(__import__('shutil').rmtree,root)
        paragraph=(r'\textbf{针对问题一}，建立成本最小化模型并满足容量约束，采用'
                   r'\textbf{拉格朗日乘子法}进行独立解析证明，得到'
                   r'\textbf{判据在正定条件下成立而在奇异条件下不成立}。')
        chapter={'chapter_id':'q1','role':'problem','tex_path':'q1.tex','abstract_type':'optimization','abstract_result_mode':'analytic'}
        source={'method':'拉格朗日乘子法','conclusion':{'text':'判据在正定条件下成立而在奇异条件下不成立','status':'analytic'},'validation':'独立解析证明'}
        result=root/'results.json';result.write_text(json.dumps(source,ensure_ascii=False),encoding='utf-8')
        digest=hashlib.sha256(result.read_bytes()).hexdigest()
        rows=[{'kind':kind,'text':value['text'] if isinstance(value,dict) else value,
               'source_path':root.name+'/results.json','source_sha256':digest,'source_pointer':'/'+kind}
              for kind,value in source.items()]
        (root/'evidence.json').write_text(json.dumps({'schema_version':'1.0','questions':[{'chapter_id':'q1','statements':rows}]},ensure_ascii=False),encoding='utf-8')
        (root/'q1.tex').write_text(paragraph,encoding='utf-8')
        manifest={'chapters':[chapter],'abstract_evidence_path':'evidence.json'}
        report=evidence_gate(manifest,root,paragraph,{1:simplify_tex(paragraph)},simplify_tex)
        self.assertEqual(report['failures'],[])
        self.assertTrue(audit_problem_paragraph(simplify_tex(paragraph),chapter)['ok'])
        self.assertEqual(numeric_tokens(simplify_tex(paragraph)),[])

    def test_settings_cannot_replace_quantitative_results(self):
        p=self.make_project(PASSING_ABSTRACT,['储能调度','混合整数线性规划','双层博弈'])
        source=p.parent/'results.json';data=json.loads(source.read_text(encoding='utf-8'))
        for value in data['q1'].values():
            if isinstance(value,dict) and 'value' in value:value['status']='setting'
        source.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
        evidence=p.parent/'abstract-evidence.json';e=json.loads(evidence.read_text(encoding='utf-8'))
        digest=hashlib.sha256(source.read_bytes()).hexdigest()
        for q in e['questions']:
            for row in q['statements']:row['source_sha256']=digest
        evidence.write_text(json.dumps(e,ensure_ascii=False),encoding='utf-8')
        codes={r['code'] for r in audit_abstract_manifest(p)['failures']}
        self.assertIn('problem_1_numeric_evidence_is_result_not_setting',codes)


if __name__ == "__main__":
    unittest.main()
