"""Render a workspace DOCX through shared VBS with explicit output boundaries."""
from __future__ import annotations

if __name__ == '__main__':
    import sys as _workflow_sys
    _workflow_sys.dont_write_bytecode = True
    from pathlib import Path as _WorkflowPath
    _workflow_sys.path.insert(0, str(_WorkflowPath(__file__).resolve().parents[2] / '华为杯_求解规范/tools'))
    from workspace_cli import require_cli_mode
    require_cli_mode(__file__)

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import uuid


def render(context, source, output, report):
    source = context.read_path(source)
    output = context.write_path(output)
    report = context.write_path(report)
    if not source.is_file() or source.suffix.lower() != '.docx':
        raise ValueError('Word 渲染输入必须是工作区内已有 DOCX')
    if output.suffix.lower() != '.pdf' or report.suffix.lower() != '.json' or len({source, output, report}) != 3:
        raise ValueError('Word 渲染须使用独立的 DOCX、PDF 和 JSON 路径')
    script = context.read_resource('华为杯_论文规范模板/tools/render_word.vbs')
    executable = shutil.which('cscript')
    if not executable:
        raise RuntimeError('找不到 Windows cscript；无法执行可选 Word 渲染')
    # Native Word output is staged inside the run. A stale previous PDF cannot
    # be mistaken for this execution's successful result.
    stage = context.write_path('求解/缓存/word/' + uuid.uuid4().hex)
    stage.mkdir(parents=True)
    staged_pdf, staged_json = stage / 'render.pdf', stage / 'headings.json'
    command = [executable, '//nologo', str(script), str(source), str(staged_pdf), str(staged_json)]
    process = subprocess.run(command, cwd=context.workspace_root, capture_output=True, timeout=180)
    (stage / 'stdout.log').write_bytes(process.stdout)
    (stage / 'stderr.log').write_bytes(process.stderr)
    if process.returncode != 0:
        raise RuntimeError(f'Word 渲染失败，退出码 {process.returncode}；日志：{stage}')
    if not staged_pdf.is_file() or not staged_pdf.read_bytes().startswith(b'%PDF-'):
        raise ValueError('Word 未生成本次有效 PDF')
    evidence = json.loads(staged_json.read_text(encoding='utf-8-sig'))
    if not isinstance(evidence.get('physical_pages'), int) or evidence['physical_pages'] < 1:
        raise ValueError('Word 未返回有效页数')
    output.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(staged_pdf, output)
    shutil.copyfile(staged_json, report)
    return {'status': 'RENDERED_REVIEW_REQUIRED', 'command': command, 'pdf': str(output),
            'headings': str(report), 'physical_pages': evidence['physical_pages'], 'logs': str(stage)}


def main():
    from workspace_context import resolve_context
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--report', required=True)
    args = p.parse_args()
    context = resolve_context()
    print(json.dumps(render(context, args.input, args.output, args.report), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
