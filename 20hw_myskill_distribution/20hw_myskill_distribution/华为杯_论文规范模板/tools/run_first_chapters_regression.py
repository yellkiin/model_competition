#!/usr/bin/env python3
"""Extend existing real XeLaTeX regression with symbol pagination and style probes."""
from __future__ import annotations
if __name__ == '__main__':
    import sys
    sys.dont_write_bytecode=True
    from pathlib import Path
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'华为杯_求解规范/tools'))
    from workspace_cli import require_cli_mode
    require_cli_mode(__file__)
import argparse
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from run_layout_smoke import create_fixture, compile_fixture
from test_first_chapters import fixture_evidence
from audit_pdf_layout import audit_layout
from first_chapters_pdf import prepare_review

CASES=[('group2',1,1,None),
       ('group3',12,1,None), ('group6',65,20,None), ('group7',85,20,None),
       ('symbols2',28,24,None), ('symbols3',28,50,'symbols_max_two_pages'),
       ('note-overflow',28,24,'symbol_note_with_final_fragment'),
       ('wrong-font',28,24,'symbol_font:'), ('wrong-note',28,24,'symbol_final_note'),
       ('extra-line',28,24,'symbol_three_rules:')]

def run(output,xelatex,case):
    name,paragraphs,rows,expected=case
    main=create_fixture(output/name,1)
    root=main.parent
    (root/'c2.tex').write_text('\\section{模型假设}\n'+'\n\n'.join(
        f'排版测试条目{i}：这里是隔离测试文字，用于观察连续排版后的自然换页和标题位置。这些句子不代表真实建模假设，也不应复制到正式论文中。'
        for i in range(1,paragraphs+1)),encoding='utf8')
    text='\\section{关键性符号说明}\n表~\\ref{tab:key-symbols}用于隔离排版测试，符号不代表实际研究。\n\\begin{GMCMSymbolTable}{本表仅列出排版测试符号，其他符号在文中首次出现处说明。}\n'
    for i in range(rows):
        category=('索引与集合','参数','变量','评价指标')[i%4]
        # Vary long and short meanings, including inline math, to exercise cell wrapping.
        meaning=f'隔离测试量的编号{i+1}' if i%4 else f'用于检验自然换行的第{i+1}个测试量，在条件 $t$ 下读取'
        text+=rf'\GMCMSymbolRow{{{category}}}{{x_{{{i+1},t}}}}{{{meaning}}}{{1}}'+'\n'
    text+='\\end{GMCMSymbolTable}\n'
    (root/'c3.tex').write_text(text,encoding='utf8')
    manifest=json.loads((root/'论文输入.json').read_text(encoding='utf8'))
    fixture_evidence(root,manifest)
    if name=='note-overflow':
        # Deliberately broken note: a new page after the final table tests whole-chapter counting.
        style=(root/'gmcm-layout.sty').read_text(encoding='utf8').replace(r'\nobreak\vskip6bp\nointerlineskip\noindent\usebox',r'\clearpage\noindent\usebox')
        (root/'gmcm-layout.sty').write_text(style,encoding='utf8')
    elif name=='wrong-font':
        p=root/'gmcm-layout.sty'; p.write_text(p.read_text(encoding='utf8').replace(r'\fontsize{12bp}{18bp}',r'\fontsize{10bp}{18bp}'),encoding='utf8')
    elif name=='wrong-note':
        p=root/'gmcm-layout.sty'; p.write_text(p.read_text(encoding='utf8').replace('注：#1','表注：#1'),encoding='utf8')
    elif name=='extra-line':
        p=root/'c3.tex'; p.write_text(p.read_text(encoding='utf8').replace(r'\end{GMCMSymbolTable}',r'\midrule\end{GMCMSymbolTable}'),encoding='utf8')
    compilation=compile_fixture(main,xelatex)
    (root/'compile-report.json').write_text(json.dumps(compilation,ensure_ascii=False,indent=2),encoding='utf8')
    if compilation['status']!='PASS':return dict(case=name,ok=False,compile=compilation)
    audit=audit_layout(main.with_suffix('.pdf'),main,root/'论文输入.json')
    (root/'layout-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf8')
    failures=[f['code'] for f in audit['failures']]
    result=dict(case=name,ok=not failures if expected is None else any(f.startswith(expected) for f in failures),
                expected=expected,failures=failures,group_pages=next(c['actual'] for c in audit['checks'] if c['code']=='first_three_unique_pages'),
                symbol_pages=next(c['actual'] for c in audit['checks'] if c['code']=='symbols_max_two_pages'),pdf=str(main.with_suffix('.pdf')))
    if name.startswith('group'):
        result['ok'] &= result['group_pages']==int(name[-1])
        result['warning_codes'] = [w['code'] for w in audit['warnings']]
        result['ok'] &= ('first_three_recommended_range' in result['warning_codes']) == (name in ('group2','group7'))
    if name in ('group3','symbols2'):
        prepare_review(main.with_suffix('.pdf'),audit,root/'first-three.review.json')
    return result

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output',type=Path,required=True); ap.add_argument('--xelatex',required=True); ap.add_argument('--cases',nargs='*')
    a=ap.parse_args(); a.output.mkdir(parents=True,exist_ok=True)
    results=[]
    selected=[c for c in CASES if not a.cases or c[0] in a.cases]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures={pool.submit(run,a.output.resolve(),a.xelatex,c):c[0] for c in selected}
        for f in as_completed(futures):
            try:r=f.result()
            except Exception as exc:r=dict(case=futures[f],ok=False,error=repr(exc))
            results.append(r); print(json.dumps(r,ensure_ascii=False),flush=True)
    report=dict(status='PASS' if all(r['ok'] for r in results) else 'FAIL',scope='synthetic real-XeLaTeX layout tests, not research acceptance',cases=results)
    (a.output/'first-chapters-regression.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    raise SystemExit(report['status']!='PASS')
if __name__=='__main__':main()
