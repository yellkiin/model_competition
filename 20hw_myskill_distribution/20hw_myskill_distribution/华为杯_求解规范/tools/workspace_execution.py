"""Run shared tools with an explicit workspace, local caches and integrity logs.

Python audit hooks intercept common Python filesystem writes. Native extensions
and external programs are not OS-sandboxed; their declared paths and before/after
shared-resource checks remain required.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

from workspace_context import (MANIFEST, bounded, atomic_json, changes, now,
                               shared_inventory, resolve_context)


def validate_arguments(context, args):
    """Reject root/runtime ambiguity before invoking any legacy CLI parser."""
    checks = {'--project-root': context.workspace_root, '--workspace-root': context.workspace_root,
              '--template-root': context.template_root, '--template-dir': context.template_root / '华为杯_论文规范模板'}
    for i, arg in enumerate(args):
        key, sep, inline = arg.partition('=')
        if key not in checks and key != '--runtime':
            continue
        if sep:
            value = inline
        elif i + 1 < len(args):
            value = args[i + 1]
        else:
            raise ValueError('缺少参数值: ' + key)
        if key == '--runtime':
            if value != context.runtime:
                raise ValueError('运行时参数与工作区冲突')
        elif Path(context.workspace_root / value).resolve() != checks[key]:
            raise ValueError('根目录参数与工作区清单冲突: ' + key)


def execute(context, tool, arguments, *, timeout=600, python=None):
    from environment_manager import ensure_stage, execution_environment
    tool_path = context.read_resource(tool)
    rel = tool_path.relative_to(context.template_root)
    if len(rel.parts) < 3 or rel.parts[0] not in {'华为杯_求解规范', '华为杯_论文规范模板'} or rel.parts[1] != 'tools' or tool_path.suffix != '.py':
        raise ValueError('只能执行两套规范 tools 中的 Python 入口')
    context = ensure_stage(context, tool)
    tool_path = context.read_resource(tool)
    validate_arguments(context, arguments)
    external_root = None
    if rel.as_posix() == '华为杯_求解规范/tools/reproduce_supporting_materials.py':
        values = []
        for i, arg in enumerate(arguments):
            if arg == '--work-root' and i + 1 < len(arguments):
                values.append(arguments[i + 1])
            elif arg.startswith('--work-root='):
                values.append(arg.split('=', 1)[1])
        if len(values) != 1:
            raise ValueError('独立复现必须明确提供唯一 --work-root')
        external_root = Path(values[0])
        if not external_root.is_absolute():
            raise ValueError('独立复现目录须使用明确绝对路径')
        external_root = bounded(external_root.anchor, external_root)
        if external_root.exists() or external_root.is_relative_to(context.template_root) or context.template_root.is_relative_to(external_root):
            raise ValueError('独立复现目录必须在模板及所有workshop之外，且尚不存在')
    pre = context.check_shared()
    if pre['status'] != 'PASS':
        raise ValueError('共享资源变化，运行前须核验依赖: ' + json.dumps(pre['changed_resources'], ensure_ascii=False))
    inputs = context.check_inputs()
    if inputs['status'] != 'PASS':
        raise ValueError('原始输入副本变化: ' + json.dumps(inputs['changed_inputs'], ensure_ascii=False))
    before = shared_inventory(context.template_root, include_generated=True)
    token = uuid.uuid4().hex
    folder = context.write_path('求解/验收输出/工作区运行/' + token)
    folder.mkdir(parents=True, exist_ok=False)
    selected_python, env = execution_environment(context, python)
    # A maintenance shell may launch normal runs. Its mode must not leak to
    # children that are authorized only for the selected shared workspace.
    env.pop('HUAWEI_WORKFLOW_MODE', None)
    env.pop('HUAWEI_LEGACY_ROOT', None)
    env.update(PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1',
               HUAWEI_WORKSPACE_MANIFEST=str(context.workspace_root / MANIFEST))
    env.pop('HUAWEI_REPRODUCTION_ROOT', None)
    if external_root:
        env['HUAWEI_REPRODUCTION_ROOT'] = str(external_root)
    for variable, tail in {'TEMP': 'temp', 'TMP': 'temp', 'MPLCONFIGDIR': 'matplotlib',
                           'XDG_CACHE_HOME': 'cache', 'NUMBA_CACHE_DIR': 'numba',
                           'PYTHONPYCACHEPREFIX': 'pycache'}.items():
        destination = context.write_path('求解/缓存/' + tail)
        destination.mkdir(parents=True, exist_ok=True)
        env[variable] = str(destination)
    bootstrap = context.read_resource('华为杯_求解规范/tools/workspace_execution.py')
    command = [str(selected_python), '-B', str(bootstrap), '--child',
               str(context.workspace_root), str(tool_path), *arguments]
    started = now()
    atomic_json(folder / '开始.json', {'command': command, 'started_at': started,
                                    'workspace_root': str(context.workspace_root), 'tool': rel.as_posix()})
    error = None
    try:
        process = subprocess.run(command, cwd=context.workspace_root, env=env, capture_output=True,
                                 text=True, encoding='utf8', errors='replace', timeout=timeout)
        code, stdout, stderr = process.returncode, process.stdout, process.stderr
    except subprocess.TimeoutExpired as exc:
        code, stdout, stderr = 124, str(exc.stdout or ''), str(exc.stderr or '')
        error = '运行超时；本次记录不授予完成状态'
    except OSError as exc:
        code, stdout, stderr, error = 1, '', str(exc), str(exc)
    (folder / 'stdout.log').write_text(stdout, encoding='utf8')
    (folder / 'stderr.log').write_text(stderr, encoding='utf8')
    drift = changes(before, shared_inventory(context.template_root, include_generated=True))
    post_inputs = context.check_inputs()
    report = {'status': 'PASS' if code == 0 and not drift and post_inputs['status'] == 'PASS' else 'FAIL',
              'returncode': code, 'error': error, 'started_at': started, 'finished_at': now(),
              'tool': rel.as_posix(), 'command': command, 'runtime': context.runtime,
              'cwd': str(context.workspace_root), 'shared_changes': drift, 'inputs': post_inputs,
              'independent_reproduction_root': str(external_root) if external_root else None,
              'stdout': (folder / 'stdout.log').relative_to(context.workspace_root).as_posix(),
              'stderr': (folder / 'stderr.log').relative_to(context.workspace_root).as_posix(),
              'assurance': '真实子进程和文件一致性检查；不代表科学或视觉审阅，不是 OS 沙箱。'}
    atomic_json(folder / '运行.json', report)
    report['report_path'] = str(folder / '运行.json')
    return report


def install_write_guard(context, external_root=None):
    """Common Python filesystem operations; external program isolation is separate."""
    guard_key = (str(context.workspace_root), str(external_root))
    installed = getattr(sys, '_huawei_write_guards', set())
    if guard_key in installed:
        return
    def check(raw):
        if isinstance(raw, int) or raw is None:
            return  # Already-open stdout/stderr descriptors.
        if isinstance(raw, bytes):
            raw = os.fsdecode(raw)
        if external_root is not None:
            try:
                bounded(external_root, Path.cwd() / raw)
                return
            except ValueError:
                pass
        # A child may chdir after startup. Check the actual OS-relative target,
        # not a second interpretation relative to the original workspace cwd.
        context.write_path(Path.cwd() / raw)

    def audit(event, args):
        if event == 'open':
            path, mode, flags = args
            writing = any(x in (mode or '') for x in 'wax+') or bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
            if writing:
                check(path)
        elif event in {'os.remove', 'os.rmdir', 'os.mkdir', 'os.chmod', 'os.utime', 'os.truncate'}:
            check(args[0])
        elif event in {'os.rename', 'os.link'}:
            check(args[0]); check(args[1])
        elif event == 'os.symlink':
            raise ValueError('运行期间不创建链接；请使用工作区内真实文件')
    sys.addaudithook(audit)
    sys._huawei_write_guards = installed | {guard_key}


def child(workspace, tool, args):
    import runpy
    sys.dont_write_bytecode = True
    context = resolve_context(workspace_root=Path(workspace))
    target = context.read_resource(tool)
    validate_arguments(context, args)
    os.chdir(context.workspace_root)
    # Preserve normal sibling imports across the two maintained tool trees.
    for group in ('华为杯_求解规范', '华为杯_论文规范模板'):
        sys.path.insert(0, str(context.template_root / group / 'tools'))
    sys.path.insert(0, str(target.parent))
    sys.argv = [str(target), *args]
    external_root = None
    if target.relative_to(context.template_root).as_posix() == '华为杯_求解规范/tools/reproduce_supporting_materials.py':
        value = os.environ.get('HUAWEI_REPRODUCTION_ROOT')
        if value:
            external_root = Path(value).resolve()
            if external_root.exists() or external_root.is_relative_to(context.template_root) or context.template_root.is_relative_to(external_root):
                raise ValueError('独立复现目录作用域失效')
    install_write_guard(context, external_root)
    runpy.run_path(str(target), run_name='__main__')


if __name__ == '__main__':
    if len(sys.argv) < 4 or sys.argv[1] != '--child':
        raise SystemExit('Use workshop.py run, not the internal child entrypoint')
    child(sys.argv[2], sys.argv[3], sys.argv[4:])
