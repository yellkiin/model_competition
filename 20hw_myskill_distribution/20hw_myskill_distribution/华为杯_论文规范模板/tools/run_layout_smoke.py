#!/usr/bin/env python3
"""Isolated, deliberately non-scientific layout fixtures. Never formal paper evidence.

Exercises production build_main, class, captions and appendix style. The complete
supporting-material/appendix fact chain has its own integration smoke test.
"""
from __future__ import annotations

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
import os
from pathlib import Path
import shutil
import subprocess

from build_latex import build_main, copy_assets
from test_paper_contract import make_fixture


def create_fixture(root: Path, q: int, variant: str = 'valid') -> Path:
    root.mkdir(parents=True, exist_ok=True)
    manifest = make_fixture(root, q)
    manifest['title'] = '工作流排版隔离演练'
    (root / '论文输入.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    (root / 'abstract.tex').write_text(
        r'此文档只测试排版，不是科学求解或正式论文。\textbf{针对问题一}，'
        r'测试\textbf{统一标题配置}及\textbf{编译后的字形与分页}。'
        r'\textbf{12.0 ms} 仅用于检查数值与单位的加粗字形，不是测量结果。', encoding='utf-8')
    p = root / 'c4.tex'
    p.write_text(
        '\\section{问题一求解与分析}\n'
        '\\subsection{问题的描述与分析}\n'
        '本页检验图在本节描述之后、下一节之前的位置。图~\\ref{fig:layout}是排版占位，不代表科学图。\n'
        '\\begin{figure}[htbp]\n\\centering\n'
        '\\fbox{\\parbox[c][35mm][c]{.7\\linewidth}{\\centering 布局占位\\par 非科学结果、非合格综合图}}\n'
        '\\caption{布局示例}\\label{fig:layout}\n'
        '\\GMCMFigureNote{独立图注允许换行。本注专门检验较长说明不会进入正式图题，说明文字保持规定字号。}\n'
        '\\end{figure}\n'
        '\\subsection{模型与验证}\n普通文字与标题字重对照。\n'
        '\\subsubsection{三级标题字重}\n三级标题正文。\n'
        '\\paragraph{四级标题字重}四级标题后的正文保持正常字重。\n\n'
        '\\subparagraph{五级标题字重}五级标题后的正文保持正常字重。\n\n'
        '\\begin{table}[htbp]\\centering\\caption{布局参数}\\label{tab:layout}\n'
        '\\begin{tabular}{ll}\\toprule 参数&用途\\\\\\midrule 字号&版面检查\\\\\\bottomrule\\end{tabular}\n'
        '\\GMCMTableNote{此表仅作字号和表题换行的排版测试。}\\end{table}\n\n'
        '文献引用字形测试\\cite{knuth}。图~\\ref{fig:layout}和表~\\ref{tab:layout}不采用文献上标样式。\n', encoding='utf-8')
    # One genuine book is sufficient for a typography probe; it deliberately
    # does NOT satisfy the ten-cited-reference final-paper gate.
    (root / 'reference.bib').write_text(
        '@book{knuth, author={Donald E. Knuth}, title={The Art of Computer Programming, Volume 1: Fundamental Algorithms}, '
        'edition={3}, publisher={Addison-Wesley}, year={1997}}\n', encoding='utf-8')
    # Explicit layout-only text exercises natural page flow, never scientific content.
    prose = [f'第{i}段为隔离排版测试文字：这里检验正文行的实际基线、自然换行与分页。测试材料不代表真实题目、科学结论或合格竞赛论文，不能移用于生产内容。'
             for i in range(1, 25)]
    (root / 'c1.tex').write_text('\\section{问题重述}\n\\subsection{问题背景}\n' +
        '\n\n'.join(prose[:12]) + '\n\\subsection{问题重述}\n' + '\n\n'.join(prose[12:]), encoding='utf-8')
    (root / 'c2.tex').write_text('\\section{模型假设}\n' + '\n\n'.join(
        f'排版测试条目{i}：这里是隔离测试文字，用于观察连续排版后的自然换页和标题位置。这些句子不代表真实建模假设，也不应复制到正式论文中。'
        for i in range(1, 35)), encoding='utf-8')
    from test_first_chapters import fixture_evidence
    fixture_evidence(root, manifest)
    (root / '论文输入.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    text, _ = build_main(manifest, root, include_appendix=False)
    copy_assets(Path(__file__).resolve().parents[1], root, include_appendix=True)
    # Isolated interface probe, not a hand-maintained production appendix.
    text = text.replace(r'\begin{document}', r'\input{附录模板.tex}' + '\n' + r'\begin{document}')
    text = text.replace(r'\end{document}',
                        '\\AppendixStart\n\\AppendixPart{1}{附件文件及内容}\n'
                        '隔离排版演练；这里不宣称通过支撑材料事实链。\n'
                        '\\AppendixPart{2}{问题一关键代码}\n'
                        '\\AppendixCodeFile{排版探针源码}{python}{probe.py}\n'
                        '\\end{document}')
    (root / 'probe.py').write_text('# 隔离排版探针，不是建模代码\nprint("layout probe")\n', encoding='utf-8')
    if variant == 'long_caption':
        p.write_text(p.read_text(encoding='utf-8').replace('\\caption{布局示例}', '\\caption{' + '需要改写的过长标题' * 8 + '}'), encoding='utf-8')
    elif variant == 'boxed_multiline_caption':
        p.write_text(p.read_text(encoding='utf-8').replace('\\caption{布局示例}',
            r'\caption{\protect\parbox{30mm}{布局标题被人为装进窄盒后形成多行}}'), encoding='utf-8')
    elif variant.startswith('evaluation_'):
        from evaluation_fixture import evaluation_text
        ep = root / f'c{q + 4}.tex'
        evaluation = evaluation_text(short=variant in ('evaluation_short', 'evaluation_padded'), extra=variant == 'evaluation_long')
        if variant == 'evaluation_padded':
            evaluation = evaluation.replace(r'\subsection{模型缺点}', '\\newpage\n\\subsection{模型缺点}')
        elif variant == 'evaluation_large_spacing':
            evaluation = evaluation.replace(r'\begin{enumerate}', '\\begin{enumerate}\n\\setlength{\\itemsep}{25pt}')
        elif variant == 'evaluation_large_font':
            evaluation = evaluation.replace(r'\subsection{模型优点}', '\\subsection{模型优点}\n\\fontsize{14pt}{24pt}\\selectfont')
        elif variant not in ('evaluation_short', 'evaluation_long'):
            raise ValueError(variant)
        ep.write_text(evaluation, encoding='utf-8')
        # Refresh only maintenance fixture evidence after intentional mutation.
        fixture_evidence(root, manifest)
        (root / '论文输入.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    elif variant == 'restatement_short_padded':
        ep = root / 'c1.tex'
        ep.write_text('\\section{问题重述}\n\\subsection{问题背景}\n短背景。\n'
                      '\\subsection{问题重述}\n短任务。\n\\newpage\n第二页。\\newpage\n第三页。', encoding='utf-8')
    elif variant == 'inline_chapter':
        text = text.replace(r'\begin{document}', r'\makeatletter\renewcommand{\GMCMSectionBoundary}{\FloatBarrier}\makeatother' + '\n' + r'\begin{document}')
    elif variant == 'normal_heading':
        text = text.replace(r'\begin{document}', r'\makeatletter\patchcmd{\subsubsection}{\bfseries}{\mdseries}{}{\errmessage{patch failed}}\makeatother' + '\n' + r'\begin{document}')
    elif variant == 'small_caption':
        text = text.replace(r'\begin{document}', r'\DeclareCaptionFont{wrongsize}{\fontsize{10pt}{12pt}\selectfont}\captionsetup[figure]{font={song,wrongsize}}' + '\n' + r'\begin{document}')
    elif variant != 'valid':
        raise ValueError(variant)
    main = root / 'layout.tex'
    main.write_text(text, encoding='utf-8')
    return main


def compile_fixture(main: Path, xelatex: str) -> dict:
    env = dict(os.environ)
    env['PATH'] = str(Path(xelatex).parent) + os.pathsep + env.get('PATH', '')
    logs = []
    commands = [[xelatex, '-shell-escape', '-interaction=nonstopmode', '-halt-on-error', '-recorder', main.name],
                [str(Path(xelatex).with_name('bibtex.exe' if os.name == 'nt' else 'bibtex')), main.stem]]
    commands += [commands[0]] * 2
    for i, cmd in enumerate(commands, 1):
        proc = subprocess.run(cmd, cwd=main.parent, env=env, capture_output=True)
        log = main.parent / f'compile-{i}.log'
        log.write_bytes(proc.stdout + proc.stderr)
        logs.append({'command': cmd, 'exit_code': proc.returncode, 'log': str(log)})
        if proc.returncode:
            break
    return {'status': 'FAIL' if logs[-1]['exit_code'] else 'PASS', 'runs': logs,
            'pdf': str(main.with_suffix('.pdf')), 'scope': 'layout probe, not scientific or final-paper acceptance'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--xelatex', default=shutil.which('xelatex'))
    ap.add_argument('--questions', type=int, default=1)
    ap.add_argument('--variant', default='valid')
    args = ap.parse_args()
    if not args.xelatex:
        ap.error('XeLaTeX is required')
    entry = create_fixture(args.output.resolve(), args.questions, args.variant)
    report = compile_fixture(entry, args.xelatex)
    (entry.parent / 'compile-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
    raise SystemExit(report['status'] != 'PASS')


if __name__ == '__main__':
    main()
