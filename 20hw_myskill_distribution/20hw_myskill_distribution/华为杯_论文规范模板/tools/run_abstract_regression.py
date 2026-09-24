"""Compile controlled abstract fixtures; synthetic values are NOT contest facts."""

# Shared execution is explicit; direct legacy/maintenance CLIs must declare mode.
if __name__ == "__main__":
    import sys as _workflow_sys
    _workflow_sys.dont_write_bytecode = True
    from pathlib import Path as _WorkflowPath
    _workflow_sys.path.insert(0, str(_WorkflowPath(__file__).resolve().parents[2] / "华为杯_求解规范/tools"))
    from workspace_cli import require_cli_mode
    require_cli_mode(__file__)

import argparse
import json
from pathlib import Path
from audit_abstract import audit_abstract_manifest
from audit_abstract_pdf import audit_abstract_pdf
from run_layout_smoke import create_fixture, compile_fixture
from test_audit_abstract import PASSING_ABSTRACT, write_evidence_fixture


def run(folder, variant, xelatex):
    folder.mkdir(parents=True, exist_ok=True)
    main = create_fixture(folder, 3)
    manifest_path = folder/'论文输入.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    manifest['keywords']=['储能调度','混合整数线性规划','双层博弈']
    questions = [c for c in manifest['chapters'] if c['role']=='problem']
    for question in questions:
        question['abstract_type']='optimization'
    subset = {'chapters':questions}
    write_evidence_fixture(folder, subset)
    for question in questions:
        source=folder/question['tex_path']
        text=source.read_text(encoding='utf-8').replace(r'\section{测试}',
            '\\section{'+question['title']+'}\n\\subsection{问题的描述与分析}')
        if question == questions[0]:
            text += '\n排版用文献引用\\cite{knuth}。\n'
        source.write_text(text,encoding='utf-8')
    manifest['abstract_evidence_path']=subset['abstract_evidence_path']
    (folder/'abstract.tex').write_text(PASSING_ABSTRACT,encoding='utf-8')
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    text=main.read_text(encoding='utf-8')
    text=text.replace(r'\keywords{结构\quad 编号\quad 模型}',r'\keywords{储能调度\quad 混合整数线性规划\quad 双层博弈}')
    text=text.replace(r'\begin{abstract}',
        '\\begin{abstract}\n\\noindent 隔离内容审计样例：以下为合成测试数值，不是赛题结果。\\par\n')
    if variant=='erase_emphasis':
        text=text.replace(r'\begin{document}',r'\renewcommand{\textbf}[1]{#1}'+'\n'+r'\begin{document}')
    elif variant=='bold_entire_abstract':
        text=text.replace(r'\input{abstract.tex}',r'{\bfseries\input{abstract.tex}}')
    elif variant!='valid':raise ValueError(variant)
    main.write_text(text,encoding='utf-8')
    source=audit_abstract_manifest(manifest_path)
    if source['status']!='PASS':raise ValueError(json.dumps(source['failures'],ensure_ascii=False))
    compiled=compile_fixture(main,xelatex)
    if compiled['status']!='PASS':raise ValueError('Compile failed: '+str(folder))
    audit=audit_abstract_pdf(main.with_suffix('.pdf'),manifest_path)
    expected=(audit['status']=='PASS')==(variant=='valid')
    report={'variant':variant,'expected_behavior_pass':expected,'source_audit':source,
            'compile':compiled,'pdf_audit':audit,
            'scope':'Controlled source and font tests; no scientific, supporting-material or full-paper approval'}
    (folder/'abstract-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return {'variant':variant,'expected_behavior_pass':expected,'failures':audit['failures'],'pdf':str(main.with_suffix('.pdf'))}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--xelatex',required=True)
    args=ap.parse_args()
    rows=[run(args.output.resolve()/v,v,args.xelatex) for v in ('valid','erase_emphasis','bold_entire_abstract')]
    (args.output/'results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(rows,ensure_ascii=False))
    raise SystemExit(not all(x['expected_behavior_pass'] for x in rows))


if __name__=='__main__':main()
