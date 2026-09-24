"""Execute a same-runtime skill script inside workshop.py's guarded child."""
from __future__ import annotations

# Shared execution is explicit; direct legacy/maintenance CLIs must declare mode.
if __name__ == "__main__":
    import sys as _workflow_sys
    _workflow_sys.dont_write_bytecode = True
    from workspace_cli import require_cli_mode
    require_cli_mode(__file__)


import argparse
import os
from pathlib import Path
import runpy
import sys

from workspace_context import MANIFEST, resolve_context


def prepare(context, raw, arguments):
    target = context.read_resource(raw)
    relative = target.relative_to(context.template_root)
    if (relative.parts[0] not in {'.agents', '.claude'}
            or target.suffix != '.py' or target.parent.name != 'scripts'
            or not context.read_resource(target.parent.parent / 'SKILL.md').is_file()):
        raise ValueError('入口必须是同端 skill 的 scripts/ 直属 Python 文件')
    arguments = list(arguments)
    if target.name == 'render_template.py' and target.parent.parent.name == 'scibox-figure':
        if '--list' not in arguments:
            if context.manifest.get('purpose') != 'demo':
                raise ValueError('内置模拟数据复刻仅限 DEMO；正式普通科学图使用 academic 真实结果链')
            values = []
            for i, arg in enumerate(arguments):
                if arg == '--project':
                    if i + 1 == len(arguments) or arguments[i + 1].startswith('--'):
                        raise ValueError('--project 缺少目录值')
                    values.append(arguments[i + 1])
                elif arg.startswith('--project='):
                    values.append(arg.split('=', 1)[1])
            if len(values) > 1:
                raise ValueError('--project 只能指定一次')
            if values:
                context.write_path(values[0])
            else:
                arguments += ['--project', str(context.write_path('求解/模板演练/绘图复刻'))]
    return target, arguments


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script', required=True, help='同端共享 skill 脚本，路径相对 template_root')
    parser.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    manifest = os.environ.get('HUAWEI_WORKSPACE_MANIFEST')
    if not manifest or Path(manifest).name != MANIFEST:
        parser.error('请通过 workshop.py run 调用，以启用工作区缓存、写入边界和前后核验')
    context = resolve_context(workspace_root=Path(manifest).parent)
    target, arguments = prepare(context, args.script, args.arguments[1:] if args.arguments[:1] == ['--'] else args.arguments)
    sys.path.insert(0, str(target.parent))
    sys.argv = [str(target), *arguments]
    runpy.run_path(str(target), run_name='__main__')


if __name__ == '__main__':
    main()
