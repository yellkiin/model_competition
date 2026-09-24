#!/usr/bin/env python3
"""Create or inspect an explicitly selected paper run without copying templates."""
import sys
# Avoid writing bytecode next to shared maintenance modules.
sys.dont_write_bytecode = True
import argparse
import json
from pathlib import Path
from workspace_context import create_workspace, resolve_context


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    create = sub.add_parser('create')
    create.add_argument('--template-root', type=Path, required=True)
    create.add_argument('--runtime', choices=('codex', 'claude'), required=True)
    create.add_argument('--input', action='append', default=[], help='模板入口中的明确文件，可重复传入')
    create.add_argument('--purpose', choices=('production', 'demo'), default='production')
    start = sub.add_parser('start', help='创建工作区并自动准备最小环境')
    start.add_argument('--template-root', type=Path, required=True)
    start.add_argument('--runtime', choices=('codex', 'claude'), required=True)
    start.add_argument('--input', action='append', default=[])
    start.add_argument('--purpose', choices=('production', 'demo'), default='production')
    start.add_argument('--offline', action='store_true')
    start.add_argument('--no-persist-user-environment', action='store_true')
    check = sub.add_parser('check')
    check.add_argument('--workspace-root', type=Path)
    check.add_argument('--template-root', type=Path)
    check.add_argument('--runtime', choices=('codex', 'claude'))
    finish = sub.add_parser('finish')
    finish.add_argument('--workspace-root', type=Path)
    finish.add_argument('--template-root', type=Path)
    finish.add_argument('--runtime', choices=('codex', 'claude'))
    listing = sub.add_parser('list')
    listing.add_argument('--template-root', type=Path, required=True)
    listing.add_argument('--runtime', choices=('codex', 'claude'))
    run = sub.add_parser('run')
    run.add_argument('--workspace-root', type=Path)
    run.add_argument('--template-root', type=Path)
    run.add_argument('--runtime', choices=('codex', 'claude'))
    run.add_argument('--tool', required=True)
    run.add_argument('--timeout', type=int, default=600)
    run.add_argument('arguments', nargs=argparse.REMAINDER)
    add = sub.add_parser('add-input')
    add.add_argument('--workspace-root', type=Path)
    add.add_argument('--template-root', type=Path)
    add.add_argument('--runtime', choices=('codex', 'claude'))
    add.add_argument('--input', action='append', required=True)
    add.add_argument('--reason', required=True)
    adopt = sub.add_parser('adopt-resources')
    adopt.add_argument('--workspace-root', type=Path)
    adopt.add_argument('--template-root', type=Path)
    adopt.add_argument('--runtime', choices=('codex', 'claude'))
    adopt.add_argument('--reason', required=True)
    relink = sub.add_parser('relink-template')
    relink.add_argument('--workspace-root', type=Path, required=True)
    relink.add_argument('--template-root', type=Path, required=True)
    relink.add_argument('--runtime', choices=('codex', 'claude'), required=True)
    env = sub.add_parser('env', help='专用环境检测、登记与准备入口')
    env.add_argument('action', choices=('prepare', 'check', 'register'))
    env.add_argument('--workspace-root', type=Path)
    env.add_argument('--template-root', type=Path)
    env.add_argument('--runtime', choices=('codex', 'claude'))
    env.add_argument('--requirements', type=Path, help='增量需求 JSON；仅 register 使用')
    env.add_argument('--offline', action='store_true')
    env.add_argument('--base-python', type=Path)
    env.add_argument('--no-persist-user-environment', action='store_true')
    a = p.parse_args()
    try:
        if a.command == 'list':
            from workspace_completion import list_runs
            print(json.dumps(list_runs(a.template_root, a.runtime), ensure_ascii=False, indent=2))
            return 0
        if a.command == 'relink-template':
            from workspace_resources import rebind_template
            print(json.dumps(rebind_template(a.workspace_root, a.template_root, a.runtime), ensure_ascii=False, indent=2))
            return 0
        if a.command in {'create', 'start'}:
            context = create_workspace(a.template_root, a.runtime, a.input, purpose=a.purpose)
        else:
            context = resolve_context(workspace_root=a.workspace_root, template_root=a.template_root, runtime=a.runtime)
        if a.command == 'finish':
            from workspace_completion import finish
            result = finish(context)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return result['status'] != 'COMPLETE'
        if a.command == 'add-input':
            from workspace_context import append_inputs
            print(json.dumps(append_inputs(context, a.input, a.reason), ensure_ascii=False, indent=2))
            return 0
        if a.command == 'adopt-resources':
            from workspace_resources import adopt_resources
            print(json.dumps(adopt_resources(context, a.reason), ensure_ascii=False, indent=2))
            return 0
        if a.command == 'start':
            from environment_manager import prepare
            result = prepare(context, offline=a.offline, base_python=sys.executable,
                             persist_user=not a.no_persist_user_environment)
            print(json.dumps({'status': result['status'], 'workspace_root': str(context.workspace_root),
                              'environment': result}, ensure_ascii=False, indent=2))
            return result['status'] != 'satisfied'
        if a.command == 'env':
            from environment_manager import prepare, check as check_environment, register
            if a.action == 'register':
                if not a.requirements:
                    raise ValueError('env register 需要 --requirements')
                result = register(context, a.requirements)
            elif a.action == 'check':
                result = check_environment(context)
            else:
                result = prepare(context, offline=a.offline, base_python=a.base_python,
                                 persist_user=not a.no_persist_user_environment)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return (result.get('status') not in {None, 'satisfied'}) if a.action != 'register' else 0
        if a.command == 'run':
            from workspace_execution import execute
            arguments = a.arguments[1:] if a.arguments[:1] == ['--'] else a.arguments
            report = execute(context, a.tool, arguments, timeout=a.timeout)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return report['status'] != 'PASS'
        shared, inputs = context.check_shared(), context.check_inputs()
        environment = None
        if context.manifest.get('environment'):
            from environment_manager import check as check_environment
            environment = check_environment(context)
        report = {'status': 'PASS' if shared['status'] == inputs['status'] == 'PASS' and
                  (environment is None or environment['status'] == 'satisfied') else 'FAIL',
                  'workspace_root': str(context.workspace_root), 'template_root': str(context.template_root),
                  'runtime': context.runtime, 'mode': context.mode, 'shared': shared, 'inputs': inputs,
                  'environment': environment}
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return report['status'] != 'PASS'
    except (ValueError, OSError) as exc:
        print(json.dumps({'status': 'FAIL', 'error': str(exc)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
