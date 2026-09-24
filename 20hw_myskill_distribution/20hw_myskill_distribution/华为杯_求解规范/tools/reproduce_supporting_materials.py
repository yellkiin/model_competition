#!/usr/bin/env python3
"""Run the public package in a fresh directory and compare declared results.

This executes project-owned commands explicitly. It is directory isolation, not
an OS security sandbox, and its editable receipts are not process attestations.
The read-only audit never launches a process or substitutes for scientific QA.
"""
from __future__ import annotations

# Shared execution is explicit; direct legacy/maintenance CLIs must declare mode.
if __name__ == "__main__":
    import sys as _workflow_sys
    _workflow_sys.dont_write_bytecode = True
    from workspace_cli import require_cli_mode
    require_cli_mode(__file__)


import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from supporting_contract import (BUILD_MANIFEST_NAME, SUPPORT_DIR_NAME,
    internal_root, load_json, project_path, question_name, sha256, validate_manifest)


def receipt_path(root, qid):
    return internal_root(root) / '独立复现' / f'{qid}.json'


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def inventory(root):
    result = {}
    for p in sorted(root.rglob('*')):
        if p.is_symlink() or (hasattr(p, 'is_junction') and p.is_junction()):
            raise ValueError(f'Reproduction input cannot contain links: {p}')
        if p.is_file():
            result[p.relative_to(root).as_posix()] = sha256(p)
    return result


def equal_json(a, b, absolute, relative):
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return math.isfinite(a) and math.isfinite(b) and math.isclose(a, b, abs_tol=absolute, rel_tol=relative)
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(equal_json(a[k], b[k], absolute, relative) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(equal_json(x, y, absolute, relative) for x, y in zip(a, b))
    return a == b


def compare(actual, expected, spec):
    if spec['comparison'] == 'sha256':
        return sha256(actual) == sha256(expected)
    return equal_json(load_json(actual), load_json(expected), spec.get('abs_tol', 0), spec.get('rel_tol', 0))


def package_inputs(root, package, manifest_path):
    build = load_json(internal_root(root) / BUILD_MANIFEST_NAME)
    if build['source_manifest_sha256'] != sha256(manifest_path):
        raise ValueError('Rebuild package after manifest changes')
    expected = {e['package_path']: e['sha256'] for e in build['entries']}
    actual = inventory(package)
    if actual != expected:
        raise ValueError('Public package differs from build inventory')
    for e in build['entries']:
        if sha256(project_path(root, e['source_path'])) != e['sha256']:
            raise ValueError('Source changed after packaging: ' + e['source_path'])
    return actual


def reproduce(root, manifest_path, package, work_root, python=sys.executable, question_id=None, timeout=3600):
    root, package, work_root = root.resolve(), package.resolve(), work_root.resolve()
    from workspace_context import shared_context
    from workspace_resources import dependencies
    context = shared_context(root)
    resources = dependencies(root, context.runtime, 'support') if context else None
    manifest = load_json(manifest_path)
    validate_manifest(manifest)
    if work_root.is_relative_to(root) or root.is_relative_to(work_root):
        raise ValueError('Independent work directory must be outside the project')
    if work_root.exists():
        raise ValueError('Refusing to reuse a reproduction directory')
    current_package = package_inputs(root, package, manifest_path)
    questions = manifest['questions']
    ids = [q['question_id'] for q in questions]
    if question_id and question_id not in ids:
        raise ValueError('Unknown question ID: ' + question_id)
    selected = set(ids if question_id is None else [question_id])
    for q in reversed(questions):
        if q['question_id'] in selected:
            selected.update(q.get('depends_on', []))
    if not selected <= set(ids):
        raise ValueError('Unknown reproduction dependency')
    for index, q in enumerate(questions):
        if q['question_id'] not in selected:
            continue
        if q['status'] != 'complete' or not q.get('reproduction'):
            raise ValueError('Completed question needs a reproduction recipe: ' + q['question_id'])
        if not set(q.get('depends_on', [])) <= set(ids[:index]):
            raise ValueError('Dependencies must precede the current question')
    work_root.mkdir(parents=True)
    # Windows packaged apps can redirect AppData when the directory is first
    # created. Bind the existing physical path, not the pre-creation spelling.
    work_root = work_root.resolve()
    if work_root.is_relative_to(root) or root.is_relative_to(work_root):
        raise ValueError('Resolved work directory is not independent')
    clone = work_root / '提交附件'
    shutil.copytree(package, clone)
    if inventory(clone) != current_package:
        raise ValueError('Copy differs from the public package')
    env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONNOUSERSITE='1', PYTHONDONTWRITEBYTECODE='1')
    env.pop('PYTHONPATH', None)
    reports = []
    for i, q in enumerate(questions, 1):
        qid = q['question_id']
        if qid not in selected:
            continue
        cwd = clone / SUPPORT_DIR_NAME / question_name(i) / '源码'
        recipe = q['reproduction']
        report = dict(schema_version='1.0', question_id=qid, status='FAIL',
            resource_dependencies=resources,
            source_manifest_sha256=sha256(manifest_path), package_inventory=current_package,
            work_root=str(work_root), cwd=str(cwd), python=str(Path(python).resolve()),
            recipe=recipe, runs=[], comparisons=[], errors=[],
            assurance='Directory reproduction and output comparison; not an OS sandbox or unforgeable execution attestation.')
        try:
            for item in recipe['outputs']:
                if project_path(cwd, item['path']).exists():
                    raise ValueError('Expected output already exists before execution: ' + item['path'])
                # Reference results must be present before running, not created by the reproduction.
                expected = project_path(root, item['expected_path'])
                if not expected.is_file():
                    raise ValueError('Missing reference result: ' + item['expected_path'])
            expected_hashes = [sha256(project_path(root, item['expected_path'])) for item in recipe['outputs']]
            for n, command in enumerate(recipe['commands'], 1):
                argv = [str(Path(python).resolve()) if arg == '{python}' else arg for arg in command['argv']]
                started = datetime.now(timezone.utc).isoformat()
                tick = time.monotonic()
                stdout, stderr = work_root / f'{qid}-{n}.stdout.log', work_root / f'{qid}-{n}.stderr.log'
                # Logs stream to disk, so long numerical runs do not fill memory.
                with stdout.open('wb') as out, stderr.open('wb') as err:
                    try:
                        completed = subprocess.run(argv, cwd=cwd, env=env, stdout=out, stderr=err, timeout=timeout, shell=False)
                        code = completed.returncode
                    except (OSError, subprocess.TimeoutExpired) as exc:
                        err.write(str(exc).encode('utf-8'))
                        code = -1
                report['runs'].append(dict(argv=argv, purpose=command['purpose'], returncode=code,
                    started_at=started, elapsed_seconds=time.monotonic()-tick,
                    stdout=str(stdout), stdout_sha256=sha256(stdout), stderr=str(stderr), stderr_sha256=sha256(stderr)))
                if code != 0:
                    raise ValueError(f'Command {n} exited {code}')
            for item, before in zip(recipe['outputs'], expected_hashes):
                actual, expected = project_path(cwd, item['path']), project_path(root, item['expected_path'])
                matched = expected.is_file() and sha256(expected) == before and actual.is_file() and compare(actual, expected, item)
                report['comparisons'].append(dict(spec=item, expected_sha256=before,
                    actual_sha256=sha256(actual) if actual.is_file() else None, matched=matched, absent_before_run=True))
                if not matched:
                    report['errors'].append('Result differs or is missing: ' + item['path'])
            # Input mutation invalidates the run; generated files are permitted.
            after = inventory(clone)
            if any(after.get(p) != digest for p, digest in current_package.items()):
                report['errors'].append('Packaged input was modified by execution')
            if package_inputs(root, package, manifest_path) != current_package:
                report['errors'].append('Original package changed during execution')
            if not report['errors']:
                report['status'] = 'PASS'
        except Exception as exc:
            report['errors'].append(str(exc))
        report['finished_at'] = datetime.now(timezone.utc).isoformat()
        save(receipt_path(root, qid), report)
        reports.append(report)
        if report['status'] != 'PASS':
            break
    return dict(status='PASS' if len(reports) == len(selected) and all(r['status']=='PASS' for r in reports) else 'FAIL',
                work_root=str(work_root), questions=reports)


def audit_reproduction(root, manifest_path, package, question, index):
    """Check retained execution facts against the current package, without running it."""
    errors = []
    try:
        qid = question['question_id']
        report = load_json(receipt_path(root, qid))
        from workspace_context import shared_context
        from workspace_resources import evidence_current
        context = shared_context(root)
        if context and not evidence_current(root, context.runtime, 'support', report):
            errors.append('Reproduction resource dependencies changed; rerun with the adopted version')
        recipe = question['reproduction']
        if report.get('schema_version') != '1.0' or report.get('question_id') != qid or report.get('status') != 'PASS':
            errors.append('Missing successful structured reproduction receipt')
        if report.get('source_manifest_sha256') != sha256(manifest_path) or report.get('recipe') != recipe:
            errors.append('Reproduction receipt is stale')
        actual_package = package_inputs(root, package, manifest_path)
        if report.get('package_inventory') != actual_package:
            errors.append('Reproduction used another package')
        work = Path(report['work_root']).resolve()
        if work.is_relative_to(root.resolve()) or root.resolve().is_relative_to(work):
            errors.append('Work directory is not independent')
        clone = work / '提交附件'
        cwd = clone / SUPPORT_DIR_NAME / question_name(index) / '源码'
        if Path(report.get('cwd', '')).resolve() != cwd.resolve():
            errors.append('Wrong reproduction working directory')
        retained = inventory(clone)
        for p, digest in actual_package.items():
            if retained.get(p) != digest:
                errors.append('Retained input changed: '+p)
        runs = report.get('runs', [])
        if len(runs) != len(recipe['commands']):
            errors.append('Incomplete command execution')
        for run, command in zip(runs, recipe['commands']):
            argv = [report['python'] if arg == '{python}' else arg for arg in command['argv']]
            if run.get('argv') != argv or run.get('purpose') != command['purpose'] or run.get('returncode') != 0:
                errors.append('Failed or different command')
            if not run.get('started_at') or not isinstance(run.get('elapsed_seconds'), (int,float)) or run['elapsed_seconds'] < 0:
                errors.append('Missing execution time')
            for kind in ('stdout', 'stderr'):
                log = project_path(work, run[kind])
                if sha256(log) != run[kind+'_sha256']:
                    errors.append('Execution log changed: ' + kind)
        comparisons = report.get('comparisons', [])
        if len(comparisons) != len(recipe['outputs']):
            errors.append('Incomplete result comparison')
        for item, result in zip(recipe['outputs'], comparisons):
            actual, expected = project_path(cwd, item['path']), project_path(root, item['expected_path'])
            if result.get('spec') != item or result.get('absent_before_run') is not True or result.get('matched') is not True:
                errors.append('Invalid output provenance: ' + item['path'])
            if sha256(actual) != result.get('actual_sha256') or sha256(expected) != result.get('expected_sha256') or not compare(actual, expected, item):
                errors.append('Reproduced result or reference changed: ' + item['path'])
    except Exception as exc:
        errors.append(str(exc))
    return dict(status='FAIL' if errors else 'PASS', errors=errors)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project-root', type=Path, default=Path('.'))
    p.add_argument('--manifest', default='求解/支撑材料清单.json')
    p.add_argument('--output', default='提交附件')
    p.add_argument('--work-root', type=Path, required=True)
    p.add_argument('--python', default=sys.executable)
    p.add_argument('--question-id')
    p.add_argument('--timeout', type=int, default=3600)
    a = p.parse_args()
    if a.timeout <= 0:
        p.error('--timeout must be positive')
    root = a.project_root.resolve()
    result = reproduce(root, project_path(root, a.manifest), project_path(root, a.output), a.work_root, a.python, a.question_id, a.timeout)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['status'] == 'PASS' else 1)


if __name__ == '__main__':
    main()
