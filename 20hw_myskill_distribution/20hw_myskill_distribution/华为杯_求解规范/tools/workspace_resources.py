"""Resource-version transitions preserve old evidence; gates compare dependencies.

Adoption accepts a new tool/reference version for future work, not its scientific
results. It never edits a previous QA record or sets a scientific PASS field.
"""
import copy
import json
import os
from pathlib import Path
import uuid

from workspace_context import (SHARED, RUNTIMES, MANIFEST, native_path, bounded,
    shared_context, shared_inventory, inventory_digest, changes, now,
    resolve_context, validate_template, validate_workspace_manifest, atomic_json, manifest_lock)

SKILL_SCOPES = {
    'environment': (),
    'academic': ('academic-figure-skill',),
    'modelviz': ('modelviz-skill-main',),
    'drawing': ('academic-figure-skill', 'modelviz-skill-main'),
    'media': (),
    'structure': ('algorithm-mechanism-diagram', 'engineering-physics-mechanism-diagram',
                  'comprehensive-graphic-text-flowchart', 'sci-box-main/sci-box-main/skills/scibox-diagram'),
    'paper': ('gmcm-abstract', 'gmcm-supporting-materials'),
    'support': ('gmcm-supporting-materials',),
}


def dependencies(root, runtime, scope):
    """Scientific gates share the maintained tool/schema contract, not test code.

    The relevant skill package is the dependency unit: its production helpers
    can read sibling references at runtime. Media does not inherit the atlas.
    """
    if scope not in SKILL_SCOPES:
        raise ValueError('未知资源依赖范围: ' + str(scope))
    context = shared_context(root, runtime)
    if not context:
        return None
    files = shared_inventory(context.template_root)
    if changes(context.manifest['shared_resources']['files'], files):
        raise ValueError('共享资源变化；先明确采用新版本，再重新核验受影响证据')
    return dependency_snapshot(files, runtime, scope)


def dependency_snapshot(files, runtime, scope):
    prefixes = [f'{RUNTIMES[runtime]}/skills/{name}/' for name in SKILL_SCOPES[scope]]
    # ModelViz folder names are not identities. Include all same-runtime skill
    # files in these scopes so renamed packages and new assets invalidate QA.
    if scope in {'modelviz', 'drawing'}:
        prefixes.append(f'{RUNTIMES[runtime]}/skills/')
    selected = {}
    for raw, digest in files.items():
        p = Path(raw)
        if p.name.startswith('test_') or p.suffix.lower() in {'.pyc', '.pyo'}:
            continue
        if p.parts[0] in {'华为杯_求解规范', '华为杯_论文规范模板'}:
            # The coupled build/audit tools and normative contracts are a shared
            # dependency. Unrelated demonstration images are not included.
            if p.suffix.lower() in {'.py', '.json', '.md', '.cls', '.sty', '.bst', '.tex', '.vbs'}:
                selected[raw] = digest
        elif raw == '工作流模式.json' or (scope == 'paper' and raw == '第二十三届研赛论文Word标准模板.docx') or raw == ('AGENTS.md' if runtime == 'codex' else 'CLAUDE.md') or any(raw.startswith(prefix) for prefix in prefixes):
            selected[raw] = digest
    return {'schema_version': '1.0', 'runtime': runtime, 'scope': scope,
            'files': selected, 'digest': inventory_digest(selected)}


def evidence_current(root, runtime, scope, record):
    expected = dependencies(root, runtime, scope)
    return expected is None or record.get('resource_dependencies') == expected


def affected_evidence(root, before, after):
    changed = set(changes(before, after))
    result = []
    for tree in ('求解', '论文'):
        base = bounded(root, tree)
        if not base.exists():
            continue
        for directory, children, names in os.walk(native_path(base)):
            children[:] = [n for n in children if n not in {'缓存', '__pycache__', '资源版本', '输入变更'}]
            for name in names:
                if not name.endswith('.json'):
                    continue
                path = Path(directory) / name
                try:
                    value = json.loads(path.read_text(encoding='utf-8-sig'))
                except (ValueError, OSError):
                    continue
                if not isinstance(value, dict):
                    continue
                stamp = value.get('resource_dependencies')
                status = str(value.get('status', '')).lower()
                if stamp:
                    used = set(stamp.get('files', {}))
                    if stamp.get('scope') in SKILL_SCOPES and stamp.get('runtime') in RUNTIMES:
                        # Newly added helpers/references were absent from the old
                        # receipt but change the dependency unit just as edits do.
                        used |= set(dependency_snapshot(after, stamp['runtime'], stamp['scope'])['files'])
                    hit = sorted(used & changed)
                    if hit:
                        result.append({'record': path.relative_to(native_path(root)).as_posix(),
                                       'changed_dependencies': hit, 'action': 'rerun_and_review'})
                elif status in {'pass', 'qa_pass', 'executed_review_required'}:
                    result.append({'record': path.relative_to(native_path(root)).as_posix(),
                                   'changed_dependencies': [], 'action': 'legacy_unstamped_requires_revalidation'})
    return result


def adopt_resources(context, reason):
    if not isinstance(reason, str) or len(reason.strip()) < 12:
        raise ValueError('采用资源新版本须记录实际变更原因（至少12字符）')
    with manifest_lock(context.workspace_root):
        context = resolve_context(workspace_root=context.workspace_root, runtime=context.runtime)
        before = context.manifest['shared_resources']['files']
        after = shared_inventory(context.template_root)
        changed = changes(before, after)
        if not changed:
            return {'status': 'UNCHANGED', 'changed_resources': [], 'affected_evidence': []}
        report = {'status': 'ADOPTED_REVALIDATION_REQUIRED', 'created_at': now(), 'reason': reason,
                  'before_digest': inventory_digest(before), 'after_digest': inventory_digest(after),
                  'changed_resources': changed, 'affected_evidence': affected_evidence(context.workspace_root, before, after),
                  'assurance': '仅采用后续运行的资源版本；不批准科学结果，不改写旧审核。'}
        folder = context.write_path('求解/验收输出/资源版本/' + uuid.uuid4().hex)
        native_path(folder).mkdir(parents=True, exist_ok=False)
        atomic_json(folder / '变更前清单.json', context.manifest)
        atomic_json(folder / '资源变更.json', report)
        data = copy.deepcopy(context.manifest)
        data['shared_resources'] = {'digest': inventory_digest(after), 'files': after}
        if data['status'] == 'complete':
            data.update(status='incomplete', completed_at=None)
            data.pop('completion', None)
        validate_workspace_manifest(data)
        # A racing maintenance edit must not silently become the accepted version.
        if changes(after, shared_inventory(context.template_root)):
            raise ValueError('采用版本期间模板再次变化，保留旧关联并重试')
        atomic_json(context.workspace_root / MANIFEST, data)
        report['report_path'] = str(folder / '资源变更.json')
        return report


def rebind_template(workspace, target, runtime):
    """Relink a moved workspace only to byte-identical recorded resources."""
    root = Path(workspace).resolve()
    target = validate_template(target)
    with manifest_lock(root):
        path = bounded(root, MANIFEST)
        data = json.loads(native_path(path).read_text(encoding='utf-8-sig'))
        validate_workspace_manifest(data)
        if data['runtime'] != runtime:
            raise ValueError('运行时与工作区清单冲突')
        if root.name != f"workshop_v{data['run_number']}":
            raise ValueError('编号与目录名称冲突')
        actual = shared_inventory(target)
        if inventory_digest(actual) != data['shared_resources']['digest'] or actual != data['shared_resources']['files']:
            raise ValueError('重新关联目标资源身份不同；不能把新版本冒充原模板')
        folder = bounded(root, '求解/验收输出/资源版本/' + uuid.uuid4().hex)
        native_path(folder).mkdir(parents=True, exist_ok=False)
        atomic_json(folder / '变更前清单.json', data)
        original = data['template']['relative_path']
        data['template']['relative_path'] = os.path.relpath(target, root).replace(os.sep, '/')
        atomic_json(path, data)
        report = {'status': 'RELINKED_IDENTICAL_RESOURCES', 'created_at': now(),
                  'old_relative_path': original, 'new_relative_path': data['template']['relative_path'],
                  'resource_digest': data['shared_resources']['digest']}
        atomic_json(folder / '重新关联.json', report)
        return report
