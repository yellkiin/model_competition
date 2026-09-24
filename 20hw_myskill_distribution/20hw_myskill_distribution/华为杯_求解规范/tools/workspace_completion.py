"""Completion is a fresh final audit plus a current artifact snapshot, not mkdir.

Editable records are traceability, not cryptographic proof of scientific review.
Final auditors still require the actual scientific and visual evidence.
"""
import copy
import json
import os
from pathlib import Path
import uuid

from workspace_context import (MANIFEST, RUN_NAME, atomic_json, bounded, file_hash,
    inventory_digest, manifest_lock, native_path, now, resolve_context,
    validate_template, validate_workspace_manifest)


def artifact_inventory(root):
    """Bind inputs, scientific sources, QA and deliverables; omit runtime churn."""
    inventory = {}
    for tree in ('题目', '数据', '求解', '论文', '待选图库', '提交附件'):
        base = bounded(root, tree)
        if not native_path(base).exists():
            continue
        for directory, children, names in os.walk(native_path(base), followlinks=False):
            relative = Path(directory).relative_to(native_path(root))
            keep = []
            for name in children:
                bounded(root, relative / name)
                if name in {'__pycache__', '缓存', '.venv'}:
                    continue
                if relative == Path('求解/验收输出') and name in {'工作区运行', '完成登记'}:
                    continue
                keep.append(name)
            children[:] = keep
            for name in names:
                raw = relative / name
                if raw.as_posix() == '求解/验收输出/工作区清单.lock':
                    continue
                path = bounded(root, raw)
                inventory[raw.as_posix()] = file_hash(path)
    return inventory


def completion_state(context):
    """A changed output invalidates the count without rewriting old evidence."""
    if context.manifest['purpose'] != 'production' or context.manifest['status'] != 'complete':
        return {'valid': False, 'reason': 'not_completed_production'}
    try:
        pointer = context.manifest['completion']
        path = bounded(context.workspace_root, pointer['report_path'])
        if file_hash(path) != pointer['sha256']:
            raise ValueError('完成报告哈希变化')
        report = json.loads(native_path(path).read_text(encoding='utf8'))
        if report['status'] != 'COMPLETE' or report['run_id'] != context.manifest['run_id']:
            raise ValueError('完成报告与运行不匹配')
        if context.check_shared()['status'] != 'PASS' or context.check_inputs()['status'] != 'PASS':
            raise ValueError('共享资源或原始输入变化')
        if report['resource_digest'] != context.manifest['shared_resources']['digest']:
            raise ValueError('完成报告使用另一模板版本')
        if artifact_inventory(context.workspace_root) != report['artifacts']:
            raise ValueError('完成后的输入、源码、审核或成果变化')
        if [row['name'] for row in report.get('gates', [])] != ['support', 'appendix', 'tex', 'paper'] or any(row['status'] != 'PASS' for row in report['gates']):
            raise ValueError('缺少通过的实际最终审计')
        for row in report['gates']:
            for raw, digest in row['files'].items():
                if file_hash(bounded(context.workspace_root, raw)) != digest:
                    raise ValueError('最终审计证据变化: ' + raw)
        return {'valid': True, 'reason': 'current_final_audit', 'completed_at': context.manifest['completed_at']}
    except (ValueError, OSError, KeyError, TypeError) as exc:
        return {'valid': False, 'reason': str(exc)}


def list_runs(template_root, runtime=None):
    root = validate_template(template_root)
    rows = []
    for path in sorted(root.iterdir(), key=lambda p: int(RUN_NAME.fullmatch(p.name)[1]) if RUN_NAME.fullmatch(p.name) else -1):
        if not RUN_NAME.fullmatch(path.name):
            continue
        try:
            context = resolve_context(workspace_root=path, template_root=root)
            if runtime and context.runtime != runtime:
                continue
            rows.append({'workspace': path.name, 'runtime': context.runtime,
                         'purpose': context.manifest['purpose'], 'status': context.manifest['status'],
                         **completion_state(context)})
        except (ValueError, OSError, KeyError) as exc:
            rows.append({'workspace': path.name, 'valid': False, 'reason': str(exc)})
    return {'runs': rows, 'completed_paper_count': sum(row['valid'] for row in rows),
            'assurance': '仅统计通过实际最终审计且成果与资源仍一致的正式运行；DEMO不计数。'}


def finish(context):
    """Invoke maintained auditors now; never accept an arbitrary old PASS file."""
    from workspace_execution import execute
    with manifest_lock(context.workspace_root):
        context = resolve_context(workspace_root=context.workspace_root, runtime=context.runtime)
        if context.manifest['purpose'] != 'production':
            raise ValueError('DEMO不能登记为完成论文')
        if not any(row['workspace_path'].startswith('题目/') for row in context.manifest['inputs']):
            raise ValueError('正式完成必须有已登记的真实题目输入')
        if context.check_shared()['status'] != 'PASS' or context.check_inputs()['status'] != 'PASS':
            raise ValueError('完成前须修复共享资源或原始输入变化')
        root = context.workspace_root
        for raw in ('论文/论文输入.json', '论文/论文.tex', '论文/论文.pdf',
                    '求解/视觉计划.json', '求解/支撑材料清单.json', '求解/候选图清单.json'):
            if not native_path(context.read_path(raw)).is_file():
                raise ValueError('完成所需文件缺失: ' + raw)
        before_artifacts = artifact_inventory(root)
        folder = context.write_path('求解/验收输出/完成登记/' + uuid.uuid4().hex)
        native_path(folder).mkdir(parents=True, exist_ok=False)
        atomic_json(folder / '变更前清单.json', context.manifest)
        relative = folder.relative_to(root)
        common = ['--runtime', context.runtime]
        commands = [
            ('support', '华为杯_求解规范/tools/audit_supporting_materials.py',
             ['--manifest', '求解/支撑材料清单.json', '--stage', 'final', '--project-root', '.', '--output', '提交附件']),
            ('appendix', '华为杯_论文规范模板/tools/audit_appendix.py', ['--project-root', '.', '--main-tex', '论文/论文.tex']),
            ('tex', '华为杯_论文规范模板/tools/audit_tex.py', ['--manifest', '论文/论文输入.json', '--main', '论文/论文.tex']),
            ('paper', '华为杯_论文规范模板/tools/audit_paper.py',
             ['--manifest', '论文/论文输入.json', '--source', '论文/论文.tex', '--pdf', '论文/论文.pdf',
              '--plan', '求解/视觉计划.json', '--project-root', '.']),
        ]
        gates = []
        for name, tool, arguments in commands:
            audit_path = relative / (name + '.json')
            run = execute(context, tool, [*arguments, *common, '--report', audit_path.as_posix()], timeout=1800)
            gate = {'name': name, 'status': run['status'], 'run_report': Path(run['report_path']).relative_to(root).as_posix(),
                    'audit_report': audit_path.as_posix()}
            if run['status'] == 'PASS':
                actual = json.loads(native_path(bounded(root, audit_path)).read_text(encoding='utf8'))
                if actual.get('status') not in {'PASS', 'PASS_WITH_WARNINGS'}:
                    gate['status'] = 'FAIL'
                gate['files'] = {raw: file_hash(bounded(root, raw)) for raw in
                    (gate['run_report'], gate['audit_report'], run['stdout'], run['stderr'])}
            gates.append(gate)
            if gate['status'] != 'PASS':
                break
        completed = len(gates) == len(commands) and all(g['status'] == 'PASS' for g in gates)
        after_artifacts = artifact_inventory(root)
        changed_during_audit = before_artifacts != after_artifacts or context.check_shared()['status'] != 'PASS'
        completed = completed and not changed_during_audit
        report = {'status': 'COMPLETE' if completed else 'FINAL_AUDIT_FAILED', 'run_id': context.manifest['run_id'],
                  'created_at': now(), 'gates': gates, 'changed_during_audit': changed_during_audit,
                  'resource_digest': context.manifest['shared_resources']['digest']}
        data = copy.deepcopy(context.manifest)
        data.pop('completion', None)
        if completed:
            report['artifacts'] = after_artifacts
            report['artifact_digest'] = inventory_digest(report['artifacts'])
        path = folder / '完成报告.json'
        atomic_json(path, report)
        data.update(status='complete' if completed else 'incomplete', completed_at=report['created_at'] if completed else None)
        if completed:
            data['completion'] = {'report_path': path.relative_to(root).as_posix(), 'sha256': file_hash(path)}
        validate_workspace_manifest(data)
        atomic_json(root / MANIFEST, data)
        return {**report, 'report_path': str(path)}
