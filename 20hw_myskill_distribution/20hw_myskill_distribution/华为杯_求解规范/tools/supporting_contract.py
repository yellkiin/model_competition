"""Shared submission layout; internal evidence never lives in the public package."""
from pathlib import Path
import hashlib
import json

SUPPORT_DIR_NAME = '支撑材料文件'
README_NAME = '支撑材料说明.md'
BUILD_MANIFEST_NAME = '_支撑材料构建清单.json'
HASH_NAME = 'SHA256SUMS.txt'
INTERNAL_DIR = '求解/验收输出/支撑材料'
FORBIDDEN_PARTS = {'.agents', '.claude', 'skills', '.venv', 'venv', '__pycache__', '.git', '.pytest_cache', 'node_modules', '待选图库'}

def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            h.update(block)
    return h.hexdigest()

def project_path(root, raw):
    from workspace_context import bounded
    return bounded(root, raw)

def chinese_number(n):
    digits = '零一二三四五六七八九'
    if not 1 <= n < 100:
        raise ValueError('问题数量应在 1 至 99 之间')
    if n < 10: return digits[n]
    return (digits[n // 10] if n >= 20 else '') + '十' + (digits[n % 10] if n % 10 else '')

def question_name(index):
    return '问题' + chinese_number(index)

def internal_root(root):
    return Path(root) / INTERNAL_DIR

def validate_manifest(manifest):
    import jsonschema
    schema = load_json(Path(__file__).resolve().parents[1] / '支撑材料清单.schema.json')
    jsonschema.Draft202012Validator(schema).validate(manifest)
    ids = [q['question_id'] for q in manifest['questions']]
    if len(ids) != len(set(ids)):
        raise ValueError('问题 ID 重复')
    for q in manifest['questions']:
        recipe = q.get('reproduction')
        if recipe:
            paths = [item['path'] for item in recipe['outputs']]
            if len(paths) != len(set(paths)):
                raise ValueError('复现输出路径重复：' + q['question_id'])
            purposes = [command['purpose'] for command in recipe['commands']]
            if purposes.index('validate') < purposes.index('solve'):
                raise ValueError('复现验证必须在求解之后：' + q['question_id'])
    data_ids = [d['data_id'] for d in manifest['external_data']]
    if len(data_ids) != len(set(data_ids)):
        raise ValueError('数据 ID 重复')

def attachment_summary(manifest, package):
    rows = []
    support = Path(package) / SUPPORT_DIR_NAME
    for i, q in enumerate(manifest['questions'], 1):
        name = question_name(i)
        if not (support / name).is_dir():
            raise ValueError(f'缺少目录：{name}')
        rows.append({'path': name, 'kind': '文件夹', 'description': q['summary']})
    for name in ['其他数据', '其他支撑材料']:
        directory = support / name
        if not directory.is_dir(): raise ValueError(f'缺少目录：{name}')
        has_files = any(p.is_file() for p in directory.rglob('*'))
        description = manifest['category_descriptions'][name] if has_files else '无'
        rows.append({'path': name, 'kind': '文件夹', 'description': description})
    return rows

def structure_errors(package, manifest):
    package = Path(package)
    errors = []
    def children(path):
        return {p.name for p in path.iterdir()} if path.is_dir() else set()
    if children(package) != {README_NAME, SUPPORT_DIR_NAME}:
        errors.append('提交附件顶层必须且只能有说明文件和支撑材料文件目录')
    if not (package / README_NAME).is_file(): errors.append('总说明不是文件')
    support = package / SUPPORT_DIR_NAME
    names = [question_name(i) for i in range(1, len(manifest['questions']) + 1)]
    if children(support) != set(names + ['其他数据', '其他支撑材料']):
        errors.append('问题数、中文目录名称或其他类别目录不符')
    for name in names:
        qroot = support / name
        if children(qroot) != {'代码环境说明.md', '源码', '中间图表'}:
            errors.append(f'{name}直属内容不符')
        if not (qroot / '代码环境说明.md').is_file(): errors.append(f'{name}环境说明缺失')
        for sub in ['源码', '中间图表']:
            if not (qroot / sub).is_dir(): errors.append(f'{name}/{sub}不是目录')
    for p in package.rglob('*'):
        rel = p.relative_to(package)
        if p.is_symlink() or FORBIDDEN_PARTS.intersection(rel.parts): errors.append(f'禁止路径：{rel}')
        if p.is_file() and (p.name in {BUILD_MANIFEST_NAME, HASH_NAME, '运行验证.json'} or p.suffix == '.log' or '.audit.' in p.name):
            errors.append(f'内部记录混入：{rel}')
    return errors
