"""Analytic and naturally two-page abstract fixtures; never contest results."""

# Shared execution is explicit; direct legacy/maintenance CLIs must declare mode.
if __name__ == "__main__":
    import sys as _workflow_sys
    _workflow_sys.dont_write_bytecode = True
    from pathlib import Path as _WorkflowPath
    _workflow_sys.path.insert(0, str(_WorkflowPath(__file__).resolve().parents[2] / "华为杯_求解规范/tools"))
    from workspace_cli import require_cli_mode
    require_cli_mode(__file__)

import argparse
import hashlib
import json
from pathlib import Path
from audit_abstract import audit_abstract_manifest, simplify_tex, visible_character_count
from audit_abstract_pdf import audit_abstract_pdf
from run_layout_smoke import create_fixture, compile_fixture
from test_audit_abstract import PASSING_ABSTRACT, write_evidence_fixture


ANALYTIC = r'''本文针对对称二次模型的极值存在性与迭代稳定性问题，建立谱分解与零空间分析模型，采用配方法和特征方向分解方法，证明极小解的存在、唯一性及稳定性由算子的谱性质共同决定。

\textbf{针对问题一}，在算子对称正定、变量取遍全空间且没有额外约束的条件下，建立二次目标最小化模型，采用\textbf{配方法}把目标函数分解为非负二次项与常数项。通过\textbf{驻点方程具有唯一全局极小解}刻画优化结果，驻点满足$Ax=b$。该结论不依赖给定数值矩阵的偶然可逆性，而由所有特征方向上的严格正曲率保证。独立谱分解证明把原变量旋转到正交特征坐标，逐方向完成平方，再把这些恒等式相加，因此极小性与唯一性均可由解析式重算。直接求解平衡方程与最小化目标函数得到相同的点，二者在该条件下具有等价的数学含义。证明同时明确正定性属于保证条件，不能只检查一个驻点便断言任意非凸目标取得全局最小值。变量重参数化只改变表示方式，不改变原目标的极值位置。

\textbf{针对问题二}，研究算子对称半正定时的二次优化模型，保留全空间变量约束，采用\textbf{值域与零空间分解法}区分可确定方向与平坦方向。推导得到\textbf{极小解存在当且仅当右端属于值域}，并以零空间说明解集的非唯一性。独立反证验证沿零特征值方向检查线性项：若该方向的投影不为零，沿适当方向增大位移即可使目标持续下降；若投影为零，该方向对目标没有贡献，正特征值方向则仍可完成平方。由此，存在性检验与唯一性检验被明确分开，奇异矩阵不会自动意味着目标无下界，也不会自动意味着所有平衡方程都有解。对于存在极小值的情况，全部极小解构成一个由特解加零空间生成的仿射集合，任何其中的点均取得相同目标值。本文的方法改进在于把单独驻点检查补充为值域检验与零空间反证，方法差异由上述必要性和充分性证明支持。

\textbf{针对问题三}，针对正定二次目标的最小化求解，建立固定正步长约束下的离散迭代模型，采用\textbf{特征方向误差递推法}分析梯度迭代。证明\textbf{全部误差方向收缩时迭代收敛到极小解}。独立递推验证将每步误差投影到特征向量，原多维问题转化为相互独立的标量递推，各方向乘子的绝对值共同决定收敛。最大特征值限制允许的正步长上界，而最小特征值影响慢方向的衰减速度。因此仅观察目标下降的一次迭代不足以证明持续收敛，应检查所有方向的乘子。边界处存在模长等于单位值的方向，一般初始误差可能持续振荡；超出边界则可构造沿不稳定方向的初始误差给出反例。该反例说明严格收缩条件的作用，并区分特殊初值收敛与对全部初值收敛这两种命题。

\textbf{针对问题四}，依据算子对称正定假设研究右端扰动引起的解变化，采用\textbf{谱范数扰动分析法}推导确定性误差界，给出\textbf{解扰动受最小特征值倒数控制}的解析结论。独立特征方向验证对扰动方程再次作正交变换，在每个方向比较输入扰动与输出变化，合并后得到欧氏范数界。沿最小特征值方向施加扰动时可以达到该界，因而它同时提供最坏方向及界的可达性证据。这里描述的是给定算子与扰动范数下的数学上界，不把上界写成已经观测到的预测误差。该结论解释了正定问题虽然具有唯一解，数值响应仍可能对某些方向更敏感；把存在性、收敛性与扰动放大分别检查，能够避免用其中一个性质替代另外两个性质。''' 


EXTRA = '''为明确可行域与目标函数的对应关系，计算流程先把功率平衡写成逐时段等式，再把容量、充放电功率和荷电状态限制写成不等式。设备投入状态只影响相应时段的可用功率，连续变量用于描述实际充放电量，因而不能用设备是否开启替代能量守恒检查。对跨时段耦合，模型显式传递储能状态，期末条件用于排除通过透支末端储能获得虚假收益的方案。比较不同算法时保持同一输入、同一可行域和同一停止规则，避免把设置差异归因于算法改进。对候选解的核查直接使用原始约束表达式，逐项检查等式残差和不等式余量，并将运行费用按实际决策重新累加。这样可以区分目标函数较小但不可行的方案与满足全部约束的有效调度。结果解释先对应各项物理量，再讨论方案之间的成本差别。模型中价格信号与负荷信号具有不同作用，前者决定能量交换的经济代价，后者决定需要由电源和储能共同承担的实际功率。为防止储能收益被重复计入，购能费用、售能收益和储能损耗分别按同一时间口径求和，并保持能量流向与费用符号一致。通过比较相同容量下的调度结果，可以识别收益来自负荷转移还是转换损耗变化；通过直接检查边界状态，可以确认所谓削峰没有把功率缺口转移到计算区间之外。独立重算同时检查费用口径与约束满足情况，二者分别对应经济结果和物理可执行性。'''


def run(folder, variant, xelatex):
    folder.mkdir(parents=True, exist_ok=False)
    count=4 if variant=='analytic' else 3
    main=create_fixture(folder,count)
    mp=folder/'论文输入.json'
    manifest=json.loads(mp.read_text(encoding='utf-8'))
    questions=[c for c in manifest['chapters'] if c['role']=='problem']
    if variant=='analytic':
        raw=(ANALYTIC.replace('研究算子对称半正定时的二次优化模型',
                 '在算子对称半正定假设下研究二次目标最小化模型')
             .replace('本文的方法改进在于','该判据给出了极小解存在的充要条件。本文的贡献在于')
             .replace('因而它同时提供最坏方向及界的可达性证据。',
                 '因而它同时提供最坏方向及界的可达性证据，并明确正定性是该界的成立条件。'))
        methods=['配方法','值域与零空间分解法','特征方向误差递推法','谱范数扰动分析法']
        conclusions=['驻点方程具有唯一全局极小解','极小解存在当且仅当右端属于值域','全部误差方向收缩时迭代收敛到极小解','解扰动受最小特征值倒数控制']
        validations=['独立谱分解证明','独立反证验证','独立递推验证','独立特征方向验证']
        facts={}; evidence=[]
        for i,q in enumerate(questions):
            q.update(abstract_type='theory' if i==3 else 'optimization',abstract_result_mode='analytic')
            facts[q['chapter_id']]=dict(method=methods[i],conclusion=dict(text=conclusions[i],status='analytic'),validation=validations[i])
            evidence.append(dict(chapter_id=q['chapter_id'],statements=[dict(kind=kind,
                text=value['text'] if isinstance(value,dict) else value,source_path=folder.name+'/results.json',
                source_pointer='/'+q['chapter_id']+'/'+kind,source_sha256='') for kind,value in facts[q['chapter_id']].items()]))
            (folder/q['tex_path']).write_text('\\section{'+q['title']+'}\n\\subsection{问题的描述与分析}\n'+raw.split('\n\n')[i+1],encoding='utf-8')
        rp=folder/'results.json';rp.write_text(json.dumps(facts,ensure_ascii=False,indent=2),encoding='utf-8')
        digest=hashlib.sha256(rp.read_bytes()).hexdigest()
        for e in evidence:
            for row in e['statements']:row['source_sha256']=digest
        (folder/'abstract-evidence.json').write_text(json.dumps(dict(schema_version='1.0',questions=evidence),ensure_ascii=False),encoding='utf-8')
        manifest['abstract_evidence_path']='abstract-evidence.json'
        manifest['keywords']=['二次优化','谱分解','零空间分析']
    else:
        raw=PASSING_ABSTRACT
        for q in questions:q['abstract_type']='optimization'
        subset={'chapters':questions}
        write_evidence_fixture(folder,subset)
        manifest['abstract_evidence_path']=subset['abstract_evidence_path']
        parts=raw.split('\n\n');parts[1]+=EXTRA;raw='\n\n'.join(parts)
        manifest['keywords']=['储能调度','混合整数线性规划','双层博弈']
        for q in questions:
            path=folder/q['tex_path']
            path.write_text(path.read_text(encoding='utf-8').replace('\\section{测试}',
                '\\section{'+q['title']+'}\n\\subsection{问题的描述与分析}'),encoding='utf-8')
    # A real bibliography entry is only a typography probe, not ten references.
    first=folder/questions[0]['tex_path']
    with first.open('a',encoding='utf-8') as f:f.write('\n排版引用\\cite{knuth}。\n')
    (folder/'abstract.tex').write_text(raw,encoding='utf-8')
    mp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    text=main.read_text(encoding='utf-8')
    text=text.replace(r'\keywords{结构\quad 编号\quad 模型}',r'\keywords{'+r'\quad '.join(manifest['keywords'])+'}')
    text=text.replace(r'\begin{abstract}',r'\begin{abstract}'+'\n隔离摘要边界测试，不是参赛论文。\\par\n')
    main.write_text(text,encoding='utf-8')
    source=audit_abstract_manifest(mp)
    (folder/'source-audit.json').write_text(json.dumps(source,ensure_ascii=False,indent=2),encoding='utf-8')
    if source['status']!='PASS':
        return dict(variant=variant,status='FAIL',count=visible_character_count(simplify_tex(raw)),failures=source['failures'])
    compile_result=compile_fixture(main,xelatex)
    if compile_result['status']!='PASS':raise ValueError('Compilation failed: '+str(folder))
    pdf=audit_abstract_pdf(main.with_suffix('.pdf'),mp)
    pages=sorted({page for c in pdf['checks'] for page in c.get('pages',[])})
    result=dict(variant=variant,status=pdf['status'],count=visible_character_count(simplify_tex(raw)),
        abstract_emphasis_pages=pages,source=source,compile=compile_result,pdf=pdf,
        scope='Analytic statements or synthetic controlled numbers; no scientific/full-paper acceptance')
    if variant=='two_page' and pages!=[1,2]:result['status']='FAIL'
    (folder/'boundary-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return dict(variant=variant,status=result['status'],pages=pages,failures=pdf['failures'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--xelatex',required=True)
    p.add_argument('--variant',choices=['analytic','two_page'],action='append')
    a=p.parse_args()
    rows=[run(a.output.resolve()/v,v,a.xelatex) for v in (a.variant or ['analytic','two_page'])]
    (a.output/'results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(rows,ensure_ascii=False))
    raise SystemExit(any(r['status']!='PASS' for r in rows))


if __name__=='__main__':main()
