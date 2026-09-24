#!/usr/bin/env python3
"""Run the actual appendix pipeline on a prepared isolated project.

No invented source results/references, mocked visual gates, destructive resets,
or automatically approved human reviews. Prepare actual project evidence first.
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
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from workspace_context import shared_context


def execution_context(root, runtime):
    context = shared_context(root, runtime)
    if context:
        if context.workspace_root != root:
            raise ValueError('附录演练的 project-root 必须是工作区根')
        if context.manifest['purpose'] != 'demo':
            raise ValueError('附录演练只允许 purpose=demo 的工作区，不运行正式赛题')
    elif not any('demo' in part.lower() for part in root.parts):
        raise ValueError('旧独立项目演练目录须明确包含 demo')
    return context


def run_stage(root, context, stage, tool, arguments, evidence):
    """Shared stages use the same guarded executor as normal production tools."""
    if context:
        from workspace_execution import execute
        result = execute(context, tool, arguments, timeout=1800)
        return dict(stage=stage, argv=result['command'],
                    returncode=0 if result['status'] == 'PASS' else result['returncode'] or 1,
                    stdout=str(root / result['stdout']), stderr=str(root / result['stderr']),
                    run_report=result['report_path'])
    command = [sys.executable, '-B', '-X', 'utf8', str(root / tool), '--legacy', *arguments]
    env = dict(os.environ, PYTHONIOENCODING='utf-8')
    env.pop('PYTHONPATH', None)
    stdout, stderr = evidence / (stage + '.stdout.log'), evidence / (stage + '.stderr.log')
    with stdout.open('wb') as out, stderr.open('wb') as err:
        result = subprocess.run(command, cwd=root, stdout=out, stderr=err, env=env)
    return dict(stage=stage, argv=command, returncode=result.returncode,
                stdout=str(stdout), stderr=str(stderr))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project-root', type=Path, required=True)
    p.add_argument('--work-root', type=Path, required=True)
    p.add_argument('--runtime', choices=('codex', 'claude'), required=True)
    p.add_argument('--xelatex')
    a = p.parse_args()
    root = a.project_root.resolve()
    context = execution_context(root, a.runtime)
    template = context.template_root if context else root
    evidence = root/'求解/验收输出/附录演练'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
    if context:
        context.write_path(evidence)
    evidence.mkdir(parents=True, exist_ok=False)
    report = dict(status='FAIL', project=str(root), stages=[], visual_review='PENDING',
        assurance='A rendered preview is not final acceptance. All production gates remain required.')

    def run(stage, tool, arguments):
        result = run_stage(root, context, stage, tool, arguments, evidence)
        report['stages'].append(result)
        if result['returncode']:
            raise RuntimeError(f"{stage} failed ({result['returncode']}); see {result['stdout']} and {result['stderr']}")

    try:
        solve, paper = '华为杯_求解规范/tools/', '华为杯_论文规范模板/tools/'
        runtime = ['--runtime', a.runtime]
        support = ['--manifest', '求解/支撑材料清单.json', '--project-root', str(root), '--output', '提交附件']
        run('abstract', paper+'audit_abstract.py', ['--manifest','论文/论文输入.json',
            '--report',str(evidence/'abstract.json')])
        run('figure_ledger', solve+'build_figure_accounting.py',
            ['--project-root',str(root),'--plan','求解/视觉计划.json','--stage','render']+runtime)
        run('package', solve+'build_supporting_materials.py', support+runtime+['--package-only'])
        run('reproduction', solve+'reproduce_supporting_materials.py', support+['--work-root',str(a.work_root)])
        run('package_and_auto_appendix', solve+'build_supporting_materials.py', support+runtime)
        manifest = json.loads((root/'求解/支撑材料清单.json').read_text(encoding='utf-8-sig'))
        for q in manifest['questions']:
            run('question_'+q['question_id'], solve+'audit_supporting_materials.py',
                support+runtime+['--stage','question','--question-id',q['question_id']])
        run('support_final', solve+'audit_supporting_materials.py', support+runtime+['--stage','final'])
        run('paper', paper+'build_latex.py', ['--manifest','论文/论文输入.json','--output','论文/论文.tex',
            '--template-dir',str(template/'华为杯_论文规范模板'),'--manifest-out','论文/论文.inputs.json',
            '--project-root',str(root)]+runtime)
        run('appendix', paper+'audit_appendix.py', ['--project-root',str(root),'--main-tex','论文/论文.tex']+runtime)
        run('tex', paper+'audit_tex.py', ['--manifest','论文/论文输入.json','--main','论文/论文.tex',
            '--report',str(evidence/'tex.json')]+runtime)
        run('compile', solve+'collect_academic_paper_review.py', ['--project-root',str(root),
            '--main-tex','论文/论文.tex','--plan','求解/视觉计划.json',
            '--output','论文/验收输出/图形入文.review.json']+runtime+
            (['--xelatex',a.xelatex] if a.xelatex else []))
        run('measured_figure_ledger', solve+'build_figure_accounting.py',
            ['--project-root',str(root),'--plan','求解/视觉计划.json','--stage','paper']+runtime)
        import pymupdf
        pdf_path = root/'论文/论文.pdf'
        pages = []
        with pymupdf.open(pdf_path) as pdf:
            start = None
            heading = str(len(manifest['questions'])+6)+'附录'
            for i, page in enumerate(pdf):
                text = re.sub(r'\s+', '', page.get_text())
                if heading in text and '附录1' in text and '附件文件及内容' in text and '文件夹名称' in text:
                    start = i
                    break
            if start is None:
                raise ValueError('Outer appendix heading and attachment table were not found')
            for i in range(start, len(pdf)):
                image = evidence/f'appendix-page-{i+1:03d}.png'
                pdf[i].get_pixmap(matrix=pymupdf.Matrix(1.7,1.7), alpha=False).save(image)
                pages.append(dict(page=i+1, image=str(image), reviewed=False, observation='', tool_ref=''))
        report.update(status='MACHINE_STAGES_PASS_VISUAL_REVIEW_PENDING', pdf=str(pdf_path),
            appendix_pages=pages, problem_count=len(manifest['questions']),
            remaining=['Actually review appendix and all figure pages',
                'Complete visual review, rebuild figure accounting --stage paper, then audit_visual_plan --stage paper and audit_paper'])
    except Exception as exc:
        report['error'] = str(exc)
    finally:
        (evidence/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(report,ensure_ascii=False,indent=2))
    return 1 if report['status']=='FAIL' else 0


if __name__ == '__main__':
    raise SystemExit(main())
