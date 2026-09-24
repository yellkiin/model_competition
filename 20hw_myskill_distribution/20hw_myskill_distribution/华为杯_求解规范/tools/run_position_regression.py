"""Actual XeLaTeX float-position probes. No scientific/overview approval is granted."""
from __future__ import annotations

# Shared execution is explicit; direct legacy/maintenance CLIs must declare mode.
if __name__ == "__main__":
    import sys as _workflow_sys
    _workflow_sys.dont_write_bytecode = True
    from workspace_cli import require_cli_mode
    require_cli_mode(__file__)

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '华为杯_论文规范模板/tools'))

from audit_diagram_positions import source_positions, physical_positions
from audit_pdf_layout import audit_layout
from collect_academic_paper_review import compile_evidence, verify_evidence
from run_layout_smoke import create_fixture


def run(root, variant, xelatex):
    import pymupdf as fitz
    root.mkdir(parents=True, exist_ok=True)
    main = create_fixture(root, 1)
    doc = fitz.open()
    page = doc.new_page(width=120/25.4*72, height=40/25.4*72)
    page.draw_rect(fitz.Rect(10, 10, page.rect.width-10, page.rect.height-10))
    page.insert_text((22, 52), 'LAYOUT PROBE / NOT SCIENTIFIC EVIDENCE', fontsize=10)
    doc.save(root / 'position-probe.pdf')
    doc.close()
    chapter = root / 'c4.tex'
    text = chapter.read_text(encoding='utf-8')
    first = text.index(r'\fbox{')
    last = text.index(r'\caption', first)
    text = text[:first] + '\\includegraphics[width=120mm]{position-probe.pdf}\n' + text[last:]
    if variant == 'float_after_second_subsection':
        text = text.replace(r'\begin{figure}[htbp]', r'\begin{figure}[p]')
        preamble = main.read_text(encoding='utf-8').replace(r'\begin{document}',
            r'\makeatletter\patchcmd{\subsection}{\FloatBarrier}{}{}{\errmessage{patch failed}}\makeatother'+'\n'+r'\begin{document}')
        main.write_text(preamble, encoding='utf-8')
    elif variant == 'source_after_second_subsection':
        start = text.index(r'\begin{figure}')
        end = text.index(r'\end{figure}', start) + len(r'\end{figure}')
        block = text[start:end]
        text = text[:start]+text[end:]
        text = text.replace(r'\subsection{模型与验证}', r'\subsection{模型与验证}'+block)
    elif variant not in ('valid', 'roadmap_valid', 'roadmap_in_background'):
        raise ValueError(variant)
    chapter.write_text(text, encoding='utf-8')
    manifest_path = root / '论文输入.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    pc = next(c for c in manifest['chapters'] if c['role'] == 'problem')
    diagram = {'diagram_id': 'position-only', 'problem_id': 'q1', 'kind': 'comprehensive', 'placement': 'body',
               'paper': {'label': 'fig:layout', 'caption': '布局示例'},
               'outputs': {'vector': 'position-probe.pdf'}}
    mapping = [{'overview_id': 'position-only', 'chapter_id': pc['chapter_id']}]
    diagrams = [diagram]
    specs = [{'figure_id': 'position-only', 'vector_path': 'position-probe.pdf', 'target_width_mm': 120}]
    if variant.startswith('roadmap_'):
        (root/'roadmap-probe.pdf').write_bytes((root/'position-probe.pdf').read_bytes())
        diagram = {'diagram_id': 'roadmap-only', 'problem_id': None, 'kind': 'flowchart', 'placement': 'body',
                   'paper': {'label': 'fig:roadmap', 'caption': '路线位置探针'},
                   'outputs': {'vector': 'roadmap-probe.pdf'}}
        diagrams.append(diagram)
        specs.append({'figure_id': 'roadmap-only', 'vector_path': 'roadmap-probe.pdf', 'target_width_mm': 120})
        first = root/'c1.tex'
        text = first.read_text(encoding='utf-8')
        block = ('\n总体路线位置检查见图\\ref{fig:roadmap}，此图仅测试版面不代表科研内容。\n'
                 '\\begin{figure}[htbp]\\centering\\includegraphics[width=120mm]{roadmap-probe.pdf}'
                 '\\caption{路线位置探针}\\label{fig:roadmap}\\end{figure}\n')
        if variant == 'roadmap_valid':
            text += block
        else:
            text = text.replace(r'\subsection{问题重述}', block+r'\subsection{问题重述}')
        first.write_text(text, encoding='utf-8')
    source = source_positions(manifest, manifest_path, main, root, diagrams, mapping)
    review = compile_evidence(root, main, root/'position-review.json', 'codex', specs, xelatex)
    verified = verify_evidence(root, review, main, 'codex', specs, require_visual=False)
    layout = audit_layout(main.with_suffix('.pdf'), main, manifest_path)
    positions = physical_positions(source, review, layout, main, root)
    report = {'variant': variant, 'source': source, 'evidence_failures': verified,
              'layout': layout, 'positions': positions,
              'scope': 'position and rendering regression only; no scientific or visual review approval'}
    expected_source = variant not in ('source_after_second_subsection', 'roadmap_in_background')
    expected_physical = variant in ('valid', 'roadmap_valid')
    report['expected_behavior_pass'] = (not verified and layout['status']=='PASS' and
        all(r['status']=='PASS' for r in source) == expected_source and
        all(r['status']=='PASS' for r in positions) == expected_physical)
    (root/'position-audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return {'variant': variant, 'expected_behavior_pass': report['expected_behavior_pass'],
            'source': source, 'evidence_failures': verified, 'layout_failures': layout['failures'], 'positions': positions}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--xelatex', required=True)
    ap.add_argument('--variant', action='append')
    args = ap.parse_args()
    rows = [run(args.output.resolve()/variant, variant, args.xelatex) for variant in
            (args.variant or ('valid', 'float_after_second_subsection', 'source_after_second_subsection'))]
    (args.output/'results.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(rows, ensure_ascii=False))
    raise SystemExit(not all(r['expected_behavior_pass'] for r in rows))


if __name__ == '__main__':
    main()
