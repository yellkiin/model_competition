"""Explicit modes for direct maintained CLIs, before they create any outputs.

The shared wrapper remains the production entry. Legacy and maintenance flags
are consumed here, so old individual parsers need no duplicate mode arguments.
"""
from __future__ import annotations
import os
from pathlib import Path
import sys


def argument_value(arguments, flag):
    values = []
    for i, arg in enumerate(arguments):
        if arg == flag:
            if i + 1 >= len(arguments):
                raise ValueError('缺少参数值: ' + flag)
            values.append(arguments[i + 1])
        elif arg.startswith(flag + '='):
            values.append(arg.split('=', 1)[1])
    if len(values) > 1:
        raise ValueError('重复路径参数: ' + flag)
    return values[0] if values else None


def require_cli_mode(tool, arguments=None):
    from workspace_context import MANIFEST, SHARED, read_mode, resolve_context
    args = list(sys.argv[1:] if arguments is None else arguments)
    front = args[:args.index('--')] if '--' in args else args
    flags = [x for x in front if x in ('--legacy', '--maintenance')]
    if len(flags) > 1:
        raise ValueError('工作流模式只能声明一次')
    manifest = os.environ.get('HUAWEI_WORKSPACE_MANIFEST')
    if manifest:
        if flags:
            raise ValueError('共享工作区调用不能混入 legacy/maintenance 模式')
        if Path(manifest).name != MANIFEST:
            raise ValueError('工作区清单入口无效')
        context = resolve_context(workspace_root=Path(manifest).parent)
        context.read_resource(Path(tool).resolve())
        if Path.cwd().resolve() != context.workspace_root:
            raise ValueError('共享子工具 cwd 必须为工作区根；请使用 workshop.py run')
        if context.check_shared()['status'] != 'PASS' or context.check_inputs()['status'] != 'PASS':
            raise ValueError('共享资源或原始输入发生变化，不能直接沿用旧工作区证据')
        # Normal runpy child already has the guard; separately launched helper
        # processes need their own Python audit hook as hooks are not inherited.
        from workspace_execution import install_write_guard, validate_arguments
        validate_arguments(context, args)
        external = os.environ.get('HUAWEI_REPRODUCTION_ROOT')
        install_write_guard(context, Path(external).resolve() if external else None)
        return 'shared'
    if flags and arguments is None:
        sys.argv.remove(flags[0])
    if '--help' in front or '-h' in front:
        return 'help'
    mode = flags[0][2:] if flags else os.environ.get('HUAWEI_WORKFLOW_MODE')
    if mode not in ('legacy', 'maintenance'):
        raise ValueError('未声明工作流模式：新运行请使用 workshop.py run；旧独立项目显式 --legacy，模板维护显式 --maintenance')
    root_arg = argument_value(front, '--project-root')
    root = Path(root_arg or os.environ.get('HUAWEI_LEGACY_ROOT') or Path.cwd()).resolve()
    if any((p / MANIFEST).is_file() for p in (root, *root.parents)):
        raise ValueError('共享workshop不能作为legacy或maintenance项目运行；请使用 workshop.py run')
    if mode == 'legacy':
        owner = next((p for p in (root, *root.parents)
                      if read_mode(p) == 'template' or all((p / name).exists() for name in SHARED)), None)
        if owner is not None and read_mode(owner) == 'template':
            raise ValueError('模板根不是legacy求解目录；请创建workshop')
        os.environ['HUAWEI_LEGACY_ROOT'] = str(root)
    os.environ['HUAWEI_WORKFLOW_MODE'] = mode
    sys.stderr.write('工作流模式：' + mode + '\n')
    return mode
