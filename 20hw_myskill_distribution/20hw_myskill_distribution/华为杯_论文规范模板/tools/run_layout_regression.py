#!/usr/bin/env python3
"""Real XeLaTeX regression: generate compliant and intentionally broken layouts.

No test fixture is eligible for scientific figure quotas or final delivery.
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
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
from audit_pdf_layout import audit_layout
from run_layout_smoke import create_fixture, compile_fixture

CASES = [
    ('q1', 1, 'valid', None),
    ('q4', 4, 'valid', None),
    ('long-caption', 1, 'long_caption', 'compile'),
    ('boxed-caption', 1, 'boxed_multiline_caption', 'caption_one_physical_line:'),
    ('small-caption', 1, 'small_caption', 'caption_prescribed_font:'),
    ('normal-heading', 1, 'normal_heading', 'heading_bold:subsubsection.'),
    ('inline-chapter', 1, 'inline_chapter', 'chapter_new_page:'),
    ('short-restatement-padded', 1, 'restatement_short_padded', 'restatement_prose_at_least_one_page'),
    ('evaluation-q3', 3, 'valid', None),
    ('long-evaluation', 1, 'evaluation_long', None),
    ('short-evaluation', 1, 'evaluation_short', 'evaluation_prose_at_least_one_page'),
    ('padded-evaluation', 1, 'evaluation_padded', 'evaluation_prose_at_least_one_page'),
    ('spaced-evaluation', 1, 'evaluation_large_spacing', 'source_structure'),
    ('large-font-evaluation', 1, 'evaluation_large_font', 'evaluation_prose_'),
]


def run_case(output: Path, xelatex: str, case: tuple) -> dict:
    name, q, variant, expected = case
    entry = create_fixture(output / name, q, variant)
    compile_report = compile_fixture(entry, xelatex)
    (entry.parent / 'compile-report.json').write_text(json.dumps(compile_report, ensure_ascii=False, indent=2), encoding='utf-8')
    if expected == 'compile':
        logs = '\n'.join(Path(r['log']).read_text(encoding='utf-8', errors='replace') for r in compile_report['runs'])
        passed = compile_report['status'] == 'FAIL' and 'Caption exceeds one line' in logs
        return {'case': name, 'ok': passed, 'expected': expected, 'compile': compile_report['status']}
    if compile_report['status'] != 'PASS':
        return {'case': name, 'ok': False, 'reason': 'Unexpected compiler failure', 'compile': compile_report}
    audit = audit_layout(entry.with_suffix('.pdf'), entry, entry.parent / '论文输入.json')
    (entry.parent / 'layout-audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
    actual = [f['code'] for f in audit['failures']]
    passed = audit['status'] == 'PASS' if expected is None else any(c.startswith(expected) for c in actual)
    return {'case': name, 'ok': passed, 'expected': expected, 'actual_failures': actual,
            'pdf': str(entry.with_suffix('.pdf'))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--xelatex', required=True)
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    results = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {pool.submit(run_case, args.output.resolve(), args.xelatex, case): case[0] for case in CASES}
        for future in as_completed(futures):
            try:
                result = future.result()
            except Exception as exc:
                result = {'case': futures[future], 'ok': False, 'error': f'{type(exc).__name__}: {exc}'}
            results.append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)
    report = {'status': 'PASS' if all(r['ok'] for r in results) else 'FAIL',
              'scope': 'real-compile layout behaviors including role-based evaluation; not scientific acceptance', 'cases': results}
    (args.output / 'regression-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    raise SystemExit(report['status'] != 'PASS')


if __name__ == '__main__':
    main()
