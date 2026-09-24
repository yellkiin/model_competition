#!/usr/bin/env python3
"""Real XeLaTeX net-prose probes; explicitly not scientific acceptance."""
from __future__ import annotations
if __name__ == '__main__':
    import sys
    sys.dont_write_bytecode = True
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


def run(output, xelatex, name):
    main=create_fixture(output/name,1)
    root=main.parent
    count={'short-large-figure':2,'enough-text':24,'long-first-chapter':65}[name]
    paragraphs=[f'第{i+1}段为隔离排版测量文字：这里检验正文行的实际基线、自然换行与分页。测试材料不代表真实题目、科学结论或合格竞赛论文，不能移用于生产内容。' for i in range(count)]
    fig=(r'\begin{figure}[htbp]\centering\fbox{\parbox[c][130mm][c]{.8\linewidth}{\centering 图内文字不属于第一章正文\par 此处仅作浮动图排除测试}}'
         r'\caption{隔离图件排除测试}\label{fig:prose-exclusion}\end{figure}')
    text='\\section{问题重述}\n\\subsection{问题背景}\n'+'\n\n'.join(paragraphs[:count//2])
    text+='\n\\subsection{问题重述}\n'+'\n\n'.join(paragraphs[count//2:])
    text+='\n\n图~\\ref{fig:prose-exclusion}是本文排版测试安排，不是原题要求。\n'+fig+'\n'
    (root/'c1.tex').write_text(text,encoding='utf8')
    if name!='long-first-chapter':
        (root/'c2.tex').write_text('\\section{模型假设}\n本章仅验证自然接排，不含真实模型假设。',encoding='utf8')
    manifest=json.loads((root/'论文输入.json').read_text(encoding='utf8'))
    fixture_evidence(root,manifest)
    compiled=compile_fixture(main,xelatex)
    (root/'compile-report.json').write_text(json.dumps(compiled,ensure_ascii=False,indent=2),encoding='utf8')
    if compiled['status']!='PASS':return dict(case=name,ok=False,compilation=compiled)
    layout=audit_layout(main.with_suffix('.pdf'),main,root/'论文输入.json')
    (root/'layout-audit.json').write_text(json.dumps(layout,ensure_ascii=False,indent=2),encoding='utf8')
    errors=[x['code'] for x in layout['failures']]
    expected=['restatement_prose_at_least_one_page'] if name=='short-large-figure' else []
    ok=sorted(errors)==sorted(expected)
    if name=='long-first-chapter':ok &= layout['chapter_ranges'][0]['touched_pages']>2
    prepare_review(main.with_suffix('.pdf'),layout,root/'prose.review.json')
    return dict(case=name,ok=ok,failures=errors,expected=expected,
                first_chapter_pages=layout['chapter_ranges'][0]['touched_pages'],
                lines=layout['restatement_prose'].get('counted_lines'),
                equivalent_pages=layout['restatement_prose']['equivalent_pages'],
                warnings=layout['warnings'],pdf=str(main.with_suffix('.pdf')))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);ap.add_argument('--xelatex',required=True);ap.add_argument('--cases',nargs='*')
    a=ap.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    cases=a.cases or ['short-large-figure','enough-text','long-first-chapter']
    results=[]
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending={pool.submit(run,a.output.resolve(),a.xelatex,c):c for c in cases}
        for f in as_completed(pending):
            try:r=f.result()
            except Exception as exc:r=dict(case=pending[f],ok=False,error=repr(exc))
            results.append(r);print(json.dumps(r,ensure_ascii=False),flush=True)
    report=dict(status='PASS' if all(r['ok'] for r in results) else 'FAIL',cases=results,scope='maintenance layout probes only; actual visual review remains required')
    (a.output/'prose-regression.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    raise SystemExit(report['status']!='PASS')
if __name__=='__main__':main()
