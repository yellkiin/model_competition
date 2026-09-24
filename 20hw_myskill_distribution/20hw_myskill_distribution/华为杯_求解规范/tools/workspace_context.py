"""Explicit shared-template reads and run-local writes; never infer a latest run.

This module does not install an OS sandbox. Callers must resolve outputs with
write_path and check snapshots around external processes as well.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import uuid
from contextlib import contextmanager

from filesystem_paths import native_path

MANIFEST = '工作区清单.json'
MODE_FILE = '工作流模式.json'
OPTIONAL_SHARED_FILES = (MODE_FILE, 'requirements.tex', 'Start-HuaweiCup.ps1',
                         '第二十三届研赛论文Word标准模板.docx')
SHARED = ('AGENTS.md', 'CLAUDE.md', '.agents', '.claude',
          '华为杯_求解规范', '华为杯_论文规范模板')
RUNTIMES = {'codex': '.agents', 'claude': '.claude'}
IGNORED = {'__pycache__', '.pytest_cache', '.git', '.venv', 'node_modules'}
RUN_NAME = re.compile(r'workshop_v([1-9][0-9]*)\Z')


def read_mode(root):
    path = bounded(root, MODE_FILE)
    if not native_path(path).exists():
        return None  # Older independent projects have no marker.
    data = json.loads(native_path(path).read_text(encoding='utf-8-sig'))
    if data != {'schema_version': '1.0', 'mode': 'template'}:
        raise ValueError('模板模式标记无效: ' + str(path))
    return 'template'


def now():
    return datetime.now(timezone.utc).isoformat()


def file_hash(path):
    result = hashlib.sha256()
    with native_path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def atomic_json(path, value):
    path = native_path(path)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def lexical(path):
    """Absolute path without following junctions, for lexical boundary checks."""
    value = str(path)
    if os.name == 'nt':
        if value.startswith('\\\\?\\UNC\\'):
            value = '\\\\' + value[8:]
        elif value.startswith('\\\\?\\'):
            value = value[4:]
    return Path(os.path.abspath(value))


def bounded(base, raw):
    base = lexical(base).resolve()
    candidate = lexical(base / raw)
    candidate.relative_to(base)
    # Reject links even if they currently resolve back inside the boundary.
    for part in (candidate, *candidate.parents):
        if part == base:
            break
        value = str(part)
        checked_part = Path('\\\\?\\UNC\\' + value[2:] if value.startswith('\\\\') else '\\\\?\\' + value) if os.name == 'nt' else part
        if checked_part.is_symlink() or (hasattr(checked_part, 'is_junction') and checked_part.is_junction()):
            raise ValueError('路径不得经过符号链接或目录联接: ' + str(part))
    resolved = candidate.resolve()
    resolved.relative_to(base)
    return resolved


def validate_template(root):
    root = Path(root).resolve()
    for name in SHARED:
        path = bounded(root, name)
        if not native_path(path).exists():
            raise ValueError('共享模板资源缺失: ' + str(path))
        if name.endswith('.md') != native_path(path).is_file():
            raise ValueError('共享资源类型错误: ' + str(path))
    return root


def shared_inventory(root, *, include_generated=False):
    root = validate_template(root)
    result = {}
    for name in (*SHARED, *(n for n in OPTIONAL_SHARED_FILES if native_path(root / n).exists())):
        base = root / name
        if native_path(base).is_file():
            paths = [native_path(base)]
        else:
            # pathlib.rglob silently misses deep Windows paths on some Python
            # builds; os.walk receives the extended path and reports them.
            paths = []
            for directory, directories, names in os.walk(str(native_path(base)), followlinks=False):
                for child in directories:
                    bounded(root, (Path(directory) / child).relative_to(native_path(root)))
                if not include_generated:
                    directories[:] = [d for d in directories if d not in IGNORED]
                else:
                    result[Path(directory).relative_to(native_path(root)).as_posix() + '/'] = '<directory>'
                paths.extend(Path(directory) / name for name in names)
        for path in paths:
            relative = path.relative_to(native_path(root))
            if not include_generated and (set(relative.parts) & IGNORED or path.suffix.lower() in {'.pyc', '.pyo'}):
                continue
            checked = bounded(root, relative)
            if native_path(checked).is_file():
                result[relative.as_posix()] = file_hash(checked)
    return result


def inventory_digest(files):
    return hashlib.sha256(json.dumps(files, sort_keys=True, separators=(',', ':')).encode('utf8')).hexdigest()


def changes(before, after):
    return [name for name in sorted(before.keys() | after.keys()) if before.get(name) != after.get(name)]


@dataclass(frozen=True)
class WorkspaceContext:
    template_root: Path
    workspace_root: Path
    runtime: str
    mode: str
    manifest: dict | None = None

    def read_resource(self, raw):
        """Only allow declared shared resource trees, never intake or other runs."""
        candidate = bounded(self.template_root, raw)
        rel = candidate.relative_to(self.template_root)
        if not rel.parts or rel.parts[0] not in (*SHARED, *OPTIONAL_SHARED_FILES):
            raise ValueError('不是共享资源白名单路径: ' + str(raw))
        if rel.parts[0] in {'.agents', '.claude'} and rel.parts[0] != RUNTIMES[self.runtime]:
            raise ValueError('禁止跨运行时读取 skill: ' + str(raw))
        if not native_path(candidate).exists():
            raise FileNotFoundError(candidate)
        return candidate

    def resource_relative(self, source, raw):
        source = self.read_resource(source)
        return self.read_resource(source.parent / raw)

    def read_path(self, raw):
        return bounded(self.workspace_root, raw)

    def write_path(self, raw, *, initializing_input=False):
        path = bounded(self.workspace_root, raw)
        rel = path.relative_to(self.workspace_root)
        if not rel.parts:
            raise ValueError('输出必须指定工作区内文件或子目录')
        if rel.parts[0] in (*SHARED, *OPTIONAL_SHARED_FILES) or RUN_NAME.fullmatch(rel.parts[0]):
            raise ValueError('不能写入共享资源或其他工作区: ' + str(raw))
        if not initializing_input and (rel.parts[0] == '题目' or rel.parts[:2] == ('数据', '原始')):
            raise ValueError('禁止回写原始输入副本: ' + str(raw))
        if rel.parts[0] == MANIFEST:
            raise ValueError('工作区清单只能由工作区管理接口更新')
        return path

    def skill(self, name):
        return self.read_resource(Path(RUNTIMES[self.runtime]) / 'skills' / name / 'SKILL.md').parent

    def check_shared(self):
        current = shared_inventory(self.template_root)
        expected = self.manifest['shared_resources']['files'] if self.manifest else current
        changed = changes(expected, current)
        return {'status': 'FAIL' if changed else 'PASS', 'changed_resources': changed,
                'current_digest': inventory_digest(current),
                'assurance': '文件当前性检查，不代表操作系统沙箱或科学审阅。'}

    def check_inputs(self):
        errors = []
        for entry in (self.manifest or {}).get('inputs', []):
            path = self.read_path(entry['workspace_path'])
            if not native_path(path).is_file() or native_path(path).stat().st_size != entry['size_bytes'] or file_hash(path) != entry['sha256']:
                errors.append(entry['workspace_path'])
        return {'status': 'FAIL' if errors else 'PASS', 'changed_inputs': errors}


def resolve_context(start=None, *, workspace_root=None, template_root=None, runtime=None, legacy=False):
    """Locate a manifest by ancestry, never by scanning/selecting child runs.

    Explicit relative CLI roots are relative to the caller; all serialized
    scientific paths are relative to the resolved workspace.
    """
    origin = Path(workspace_root or start or Path.cwd()).resolve()
    if origin.is_file():
        origin = origin.parent
    found = next((p for p in (origin, *origin.parents) if (p / MANIFEST).is_file()), None)
    if found:
        if legacy:
            raise ValueError('存在工作区清单，不能混用 legacy 模式')
        if workspace_root is not None and found != origin:
            raise ValueError('--workspace-root 必须指向工作区根目录')
        data = json.loads((found / MANIFEST).read_text(encoding='utf-8-sig'))
        validate_workspace_manifest(data)
        if data.get('schema_version') != '1.0' or data.get('mode') != 'shared':
            raise ValueError('不支持的工作区清单版本或模式')
        if data.get('runtime') not in RUNTIMES or runtime is not None and runtime != data['runtime']:
            raise ValueError('运行时与工作区清单冲突')
        if not isinstance(data.get('run_number'), int) or found.name != f"workshop_v{data['run_number']}":
            raise ValueError('工作区编号与目录名称冲突')
        association = data.get('template', {}).get('relative_path')
        if not isinstance(association, str) or not association or Path(association).is_absolute():
            raise ValueError('模板关联必须是相对工作区的相对路径')
        template = validate_template(found / association)
        if template_root is not None and template != Path(template_root).resolve():
            raise ValueError('模板参数与工作区清单冲突')
        resources = data.get('shared_resources', {})
        if not resources.get('files') or inventory_digest(resources['files']) != resources.get('digest'):
            raise ValueError('共享资源版本记录无效')
        return WorkspaceContext(template, found, data['runtime'], 'shared', data)
    if not legacy:
        raise ValueError('未找到工作区清单；请创建工作区或显式指定工作区，不自动选择最新目录')
    if read_mode(origin) == 'template':
        raise ValueError('模板根不能作为legacy求解项目')
    if runtime not in RUNTIMES:
        raise ValueError('legacy 模式也必须显式指定运行时')
    template = validate_template(template_root or origin)
    if template != origin:
        raise ValueError('legacy 独立项目不能静默借用外部模板；请使用共享工作区模式')
    return WorkspaceContext(template, origin, runtime, 'legacy')


def relative_record(raw):
    """Serialized paths are portable relative identifiers, never drive/ADS paths."""
    if not isinstance(raw, str) or not raw or '\\' in raw or ':' in raw or raw.startswith('/'):
        raise ValueError('记录路径必须为使用 / 的相对路径: ' + str(raw))
    if any(p in ('', '.', '..') for p in raw.split('/')):
        raise ValueError('记录路径不得包含空段、. 或 ..: ' + raw)
    return Path(raw)


def validate_workspace_manifest(data):
    # Import the established schema validator lazily; no runtime dependencies
    # are required to initialize a workspace. The schema is the executing
    # maintenance tool's sibling resource, never an arbitrary manifest path.
    from workspace_schema import errors as schema_errors
    schema_path = Path(__file__).resolve().parent.parent / '工作区清单.schema.json'
    schema = json.loads(native_path(schema_path).read_text(encoding='utf8'))
    errors = schema_errors(data, schema)
    if errors:
        raise ValueError('工作区清单不符合 schema: ' + '; '.join(errors[:12]))
    seen = set()
    for row in data['inputs']:
        source = relative_record(row['source_path'])
        target = relative_record(row['workspace_path'])
        if source.parts[0] not in ('题目', '数据') or len(source.parts) < 2:
            raise ValueError('输入来源不属于入口目录')
        if not (target.parts[0] == '题目' and len(target.parts) >= 2 or target.parts[:2] == ('数据', '原始') and len(target.parts) >= 3):
            raise ValueError('输入副本必须位于题目/或数据/原始/')
        key = row['workspace_path'].casefold()
        if key in seen:
            raise ValueError('清单输入目标路径重复')
        seen.add(key)
    for raw in data['shared_resources']['files']:
        if relative_record(raw).parts[0] not in (*SHARED, *OPTIONAL_SHARED_FILES):
            raise ValueError('共享版本包含白名单外资源')
    if data['status'] == 'complete' and (data['purpose'] != 'production' or not data['completed_at']):
        raise ValueError('演练或缺完成时间的工作区不得标记正式完成')
    if data['status'] != 'complete' and data['completed_at'] is not None:
        raise ValueError('未完成运行不能携带完成时间')
    if (data['status'] == 'complete') != ('completion' in data):
        raise ValueError('完成状态必须且只能携带最终审计登记')


@contextmanager
def manifest_lock(root):
    """Exclusive mutation lock; never break a possibly live owner's lock."""
    root = Path(root).resolve()
    lock = bounded(root, '求解/验收输出/工作区清单.lock')
    native_path(lock.parent).mkdir(parents=True, exist_ok=True)
    try:
        stream = native_path(lock).open('x', encoding='utf8')
    except FileExistsError as exc:
        raise ValueError('工作区清单正在被另一操作修改；请检查该操作状态后重试') from exc
    try:
        with stream:
            stream.write(json.dumps({'pid': os.getpid(), 'created_at': now()}))
        yield
    finally:
        native_path(lock).unlink()


def selected_inputs(template, inputs):
    selected, destinations = [], set()
    for raw in inputs:
        source = bounded(template, raw)
        rel = source.relative_to(template)
        if len(rel.parts) < 2 or rel.parts[0] not in {'题目', '数据'} or not native_path(source).is_file():
            raise ValueError('输入必须明确选择入口题目/数据中的文件: ' + str(raw))
        relative_record(rel.as_posix())
        tail = Path(*rel.parts[1:])
        if rel.parts[0] == '数据' and tail.parts[0] == '原始':
            tail = Path(*tail.parts[1:])
        target = Path('题目') / tail if rel.parts[0] == '题目' else Path('数据/原始') / tail
        relative_record(target.as_posix())
        if target.as_posix().casefold() in destinations:
            raise ValueError('输入副本路径重复: ' + target.as_posix())
        destinations.add(target.as_posix().casefold())
        selected.append((source, rel, target))
    return selected


def append_inputs(context, inputs, reason):
    """Explicit append only. Existing input bytes and earlier records never change."""
    if not inputs or not isinstance(reason, str) or len(reason.strip()) < 8:
        raise ValueError('追加输入须指定文件并说明本次用途（至少8字符）')
    with manifest_lock(context.workspace_root):
        context = resolve_context(workspace_root=context.workspace_root, runtime=context.runtime)
        if context.check_inputs()['status'] != 'PASS':
            raise ValueError('已有原始副本变化，不能继续追加掩盖问题')
        selected = selected_inputs(context.template_root, inputs)
        data = json.loads(json.dumps(context.manifest))
        known = {row['workspace_path'].casefold() for row in data['inputs']}
        for _, _, target in selected:
            if target.as_posix().casefold() in known or native_path(bounded(context.workspace_root, target)).exists():
                raise ValueError('追加输入不得覆盖已有路径: ' + target.as_posix())
        history = context.write_path('求解/验收输出/输入变更/' + uuid.uuid4().hex)
        native_path(history).mkdir(parents=True, exist_ok=False)
        atomic_json(history / '变更前清单.json', data)
        intent = {'status': 'PREPARING', 'started_at': now(), 'reason': reason,
                  'selected_sources': [r.as_posix() for _, r, _ in selected], 'files': []}
        atomic_json(history / '输入变更.json', intent)
        created = []
        try:
            # Stage all copies, validate original stability before publishing any.
            for source, rel, target in selected:
                digest = file_hash(source)
                staged = bounded(history, Path('暂存') / target)
                native_path(staged.parent).mkdir(parents=True, exist_ok=True)
                shutil.copyfile(native_path(source), native_path(staged))
                if file_hash(staged) != digest or file_hash(source) != digest:
                    raise ValueError('复制期间入口文件变化: ' + rel.as_posix())
                intent['files'].append({'source_path': rel.as_posix(), 'workspace_path': target.as_posix(),
                                        'size_bytes': native_path(staged).stat().st_size, 'sha256': digest, 'copied_at': now()})
            for row in intent['files']:
                source = bounded(history / '暂存', row['workspace_path'])
                target = bounded(context.workspace_root, row['workspace_path'])
                native_path(target.parent).mkdir(parents=True, exist_ok=True)
                # x mode prevents overwriting a concurrent, unregistered file.
                with native_path(source).open('rb') as src, native_path(target).open('xb') as dst:
                    created.append(target)
                    shutil.copyfileobj(src, dst)
                native_path(target).chmod(native_path(target).stat().st_mode & ~stat.S_IWUSR & ~stat.S_IWGRP & ~stat.S_IWOTH)
            data['inputs'].extend(intent['files'])
            if data['status'] == 'complete':
                data.update(status='incomplete', completed_at=None)
                data.pop('completion', None)
            validate_workspace_manifest(data)
            atomic_json(context.workspace_root / MANIFEST, data)
            intent.update(status='REGISTERED', finished_at=now())
        except Exception as exc:
            for path in created:
                bounded(context.workspace_root, path)
                native_path(path).chmod(stat.S_IWRITE | stat.S_IREAD)
                native_path(path).unlink()
            intent.update(status='FAILED', error=str(exc), finished_at=now())
            raise
        finally:
            atomic_json(history / '输入变更.json', intent)
        return {'status': 'REGISTERED', 'added': intent['files'],
                'report_path': str(history / '输入变更.json'),
                'assurance': '追加原始输入；不会批准任何科学阶段或更新旧审阅。'}


def shared_context(root, runtime=None):
    """Compatibility boundary for existing APIs taking an explicit project root.

    An actual manifest always wins, including conflict/validation failures.
    No manifest means the existing API is operating on a legacy local tree.
    New user-facing run entrypoints use resolve_context, which requires a mode.
    """
    origin = Path(root).resolve()
    if any((p / MANIFEST).is_file() for p in (origin, *origin.parents)):
        return resolve_context(origin, runtime=runtime)
    if read_mode(origin) == 'template':
        raise ValueError('模板根不能静默使用legacy路径；请使用workshop工作区')
    return None


def resource_path(root, raw, runtime):
    context = shared_context(root, runtime)
    if context:
        return context.read_resource(raw)
    if runtime not in RUNTIMES:
        raise ValueError('共享资源读取要求显式运行时')
    candidate = bounded(root, raw)
    rel = candidate.relative_to(Path(root).resolve())
    if not rel.parts or rel.parts[0] not in SHARED:
        raise ValueError('不是共享资源白名单路径: ' + str(raw))
    if rel.parts[0] in {'.agents', '.claude'} and rel.parts[0] != RUNTIMES[runtime]:
        raise ValueError('禁止跨运行时读取 skill')
    return candidate


def reference_path(root, raw, runtime):
    """Read a reference resource or local derived reference; never an output API."""
    parts = Path(raw).parts
    if parts and parts[0] in SHARED:
        return resource_path(root, raw, runtime)
    return bounded(root, raw)


def create_workspace(template_root, runtime, inputs=(), *, purpose='production'):
    """Reserve the next number with mkdir; failed runs keep their reservation."""
    template = validate_template(template_root)
    if runtime not in RUNTIMES or purpose not in {'production', 'demo'}:
        raise ValueError('必须指定合法的运行时和工作区用途')
    selected = selected_inputs(template, inputs)
    baseline = shared_inventory(template)
    while True:
        numbers = [int(m[1]) for p in template.iterdir() if (m := RUN_NAME.fullmatch(p.name))]
        number = max(numbers, default=0) + 1
        root = template / f'workshop_v{number}'
        try:
            root.mkdir(exist_ok=False)
            break
        except FileExistsError:
            continue
    data = {'schema_version': '1.0', 'mode': 'shared', 'run_id': uuid.uuid4().hex,
            'run_number': number, 'runtime': runtime, 'purpose': purpose,
            'created_at': now(), 'status': 'initializing', 'completed_at': None,
            'template': {'relative_path': os.path.relpath(template, root).replace(os.sep, '/')},
            'shared_resources': {'digest': inventory_digest(baseline), 'files': baseline}, 'inputs': []}
    atomic_json(root / MANIFEST, data)
    try:
        for name in ('题目', '数据/原始', '数据/中间', '数据/自主', '求解/验收输出',
                     '论文', '待选图库/图片', '提交附件'):
            bounded(root, name).mkdir(parents=True, exist_ok=True)
        for source, rel, target in selected:
            expected = file_hash(source)
            destination = bounded(root, target)
            native_path(destination.parent).mkdir(parents=True, exist_ok=True)
            shutil.copyfile(native_path(source), native_path(destination))
            if file_hash(destination) != expected or file_hash(source) != expected:
                raise ValueError('复制期间入口数据发生变化: ' + rel.as_posix())
            native_path(destination).chmod(native_path(destination).stat().st_mode & ~stat.S_IWUSR & ~stat.S_IWGRP & ~stat.S_IWOTH)
            data['inputs'].append({'source_path': rel.as_posix(), 'workspace_path': target.as_posix(),
                                   'size_bytes': native_path(destination).stat().st_size, 'sha256': expected, 'copied_at': now()})
        if changes(baseline, shared_inventory(template)):
            raise ValueError('初始化期间共享资源发生变化，须核验后恢复')
        data['status'] = 'ready'
    except Exception as exc:
        data.update(status='initialization_failed', error=str(exc))
        raise
    finally:
        atomic_json(root / MANIFEST, data)
    return resolve_context(workspace_root=root, runtime=runtime)
