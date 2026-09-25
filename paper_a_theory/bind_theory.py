"""Install a theory reading package into a NEW, run-specific paper input folder.

Standard library only. No network, solving, experiments, branch checkout, AGENTS
editing, template replacement, or writes to source/result directories. This checks
input locations and selected source files, not mathematical or empirical validity.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

PACKAGE = Path(__file__).resolve().parent
COMMIT = re.compile(r'^[0-9a-fA-F]{40}$')
IDENT = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$')


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(value, dict):
        raise ValueError(f'Expected a JSON object: {path}')
    return value


def existing(value, base: Path, kind: str) -> Path:
    if not isinstance(value, str) or not value or 'REPLACE_' in value:
        raise ValueError(f'Unresolved {kind} path: {value!r}')
    p = Path(value).expanduser()
    p = (p if p.is_absolute() else base / p).resolve()
    valid = p.is_dir() if kind == 'directory' else p.is_file()
    if not valid:
        raise ValueError(f'Missing {kind}: {p}')
    return p


def normalized_text(raw: bytes) -> str:
    if raw.startswith(b'version https://git-lfs.github.com/spec/v1'):
        raise ValueError('A Git LFS pointer is not the source file')
    return raw.decode('utf-8-sig').replace('\r\n', '\n')


def inspect_binding(spec: dict, spec_dir: Path, package_commit: str) -> dict:
    if spec.get('schema_version') != 1:
        raise ValueError('Unsupported binding schema; expected 1')
    ident = spec.get('binding_id', '')
    if not isinstance(ident, str) or not IDENT.fullmatch(ident):
        raise ValueError('binding_id must be a short unique ASCII name')
    if not COMMIT.fullmatch(package_commit):
        raise ValueError('--package-commit must be the fetched 40-character commit')
    ws = existing(spec.get('workspace'), spec_dir, 'directory')
    if ws.name.lower() == 'workshop_v1':
        raise ValueError('Create a new paper workspace; preserve workshop_v1')
    repo = existing(spec.get('repo_root'), spec_dir, 'directory')
    impl = existing(spec.get('implementation_root'), repo, 'directory')
    commit = spec.get('implementation_commit', '')
    if not isinstance(commit, str) or not COMMIT.fullmatch(commit):
        raise ValueError('Declare the actual 40-character implementation commit')
    file_names = spec.get('implementation_files')
    if not isinstance(file_names, list) or not file_names:
        raise ValueError('Declare the actual entrypoint and important dependency files')
    mode = spec.get('source_mode', 'git')
    if mode not in ('git', 'archived_execution'):
        raise ValueError('source_mode must be git or archived_execution')
    execution = None
    if spec.get('execution_manifest') is not None:
        execution = existing(spec['execution_manifest'], repo, 'file')
    if mode == 'archived_execution' and execution is None:
        raise ValueError('Archived source requires an actual execution manifest')
    checks = []
    for name in file_names:
        if not isinstance(name, str) or Path(name).is_absolute() or '..' in Path(name).parts:
            raise ValueError(f'Invalid implementation-relative file: {name!r}')
        path = existing(name, impl, 'file')
        actual = normalized_text(path.read_bytes())
        row = {'path': str(path), 'checked_against_git': False}
        if mode == 'git':
            try:
                relative = path.relative_to(repo).as_posix()
            except ValueError as exc:
                raise ValueError('Git source must be within repo_root') from exc
            result = subprocess.run(
                ['git', '-C', str(repo), 'show', f'{commit}:{relative}'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
                timeout=45,
            )
            if result.returncode:
                raise ValueError(f'Cannot read declared source {commit}:{relative}; fetch it into a separate checkout first')
            if actual != normalized_text(result.stdout):
                raise ValueError(f'Local source differs from declared commit: {relative}. Do not switch an active experiment checkout; prepare a separate source snapshot')
            row.update(checked_against_git=True, comparison='UTF-8 text, CRLF normalized to LF')
        checks.append(row)
    problem = existing(spec.get('problem_file'), repo, 'file')
    official = existing(spec.get('official_root'), repo, 'directory')
    config = existing(spec.get('config_file'), repo, 'file')
    literature = existing(spec.get('literature_root'), repo, 'directory')
    workbench = None
    if spec.get('workbench_entry') is not None:
        workbench = existing(spec['workbench_entry'], ws, 'file')
    runs = []
    for item in spec.get('result_runs', []):
        if not isinstance(item, dict) or not item.get('run_id'):
            raise ValueError('Each result run requires run_id, path and role')
        if item.get('role') not in ('main', 'baseline', 'diagnostic', 'sensitivity', 'cumulative_best'):
            raise ValueError('Separate main, baseline, diagnostic, sensitivity and cumulative_best results')
        path = existing(item.get('path'), repo, 'directory')
        runs.append({**item, 'path': str(path), 'evidence_validation': 'pending'})
    manifest = load(PACKAGE / 'MANIFEST.json')
    for name in manifest['files']:
        if Path(name).name != name or not (PACKAGE / name).is_file():
            raise ValueError(f'Incomplete or unsafe theory package member: {name}')
    destination = ws / 'theory_input' / manifest['package_id'] / ident
    if destination.exists():
        raise FileExistsError(f'Binding already exists; choose a new binding_id: {destination}')
    return {
        'schema_version': 1,
        'binding_id': ident,
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'package_id': manifest['package_id'],
        'package_version': manifest['version'],
        'package_commit_declared': package_commit.lower(),
        'theoretical_anchor': manifest['theoretical_anchor'],
        'workspace': str(ws), 'destination': str(destination),
        'repo_root': str(repo), 'implementation_root': str(impl),
        'implementation_commit': commit.lower(), 'source_mode': mode,
        'entrypoint_checks': checks,
        'execution_manifest': str(execution) if execution else None,
        'problem_file': str(problem), 'official_root': str(official),
        'config_file': str(config), 'literature_root': str(literature),
        'workbench_entry': str(workbench) if workbench else None,
        'result_runs': runs, 'result_adapter': spec.get('result_adapter', {}),
        'status': 'paths_bound_semantic_and_result_review_pending',
        'automatic_check_scope': 'Package members, input paths and declared entrypoint text only; imported dependencies, mathematics and run metrics require review',
        'no_experiments_executed': True,
        'next_required_reads': manifest['reading_order'],
        'review_outputs_required': [
            'THEORY_ALIGNMENT.md', 'TERM_SYMBOL_LEDGER.json',
            'METHOD_TO_CODE.md', 'RESULT_BINDING.json', 'PENDING_EVIDENCE.md'
        ],
    }


def install(binding: dict, spec: dict) -> Path:
    destination = Path(binding['destination'])
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.theory-bind-', dir=destination.parent))
    try:
        package_dir = stage / 'package'
        package_dir.mkdir()
        for name in load(PACKAGE / 'MANIFEST.json')['files']:
            shutil.copy2(PACKAGE / name, package_dir / name)
        (stage / 'THEORY_BINDING.json').write_text(
            json.dumps(binding, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        (stage / 'BINDING_INPUT.json').write_text(
            json.dumps(spec, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        order = '\n'.join(f'{i}. package/{f}' for i, f in enumerate(binding['next_required_reads'], 1))
        handoff = (
            '# 论文理论输入：正文生成前读取\n\n'
            '本目录为新增输入，不替换写作Agent、AGENTS.md或既有稿件。\n'
            '请先读THEORY_BINDING.json，再按以下顺序读取材料：\n\n' + order + '\n\n'
            '当前状态仅表示路径绑定完成。先产出THEORY_ALIGNMENT、术语符号表和METHOD_TO_CODE；'
            '逐项核对真实执行版本，然后沿统一模型路线起草正文。\n'
            '结果尚未完成时继续方法写作，PENDING_EVIDENCE中列出缺项；终稿数值以原方案和原响应为依据。\n'
            '目录迁移通过新绑定处理；算法或执行语义改变时同步修订理论与伪代码。\n'
        )
        (stage / 'THEORY_HANDOFF.md').write_text(handoff, encoding='utf-8')
        if destination.exists():
            raise FileExistsError(f'Another process created this binding: {destination}')
        stage.rename(destination)
        return destination
    except Exception:
        if stage.exists():
            shutil.rmtree(stage)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec', type=Path, required=True)
    parser.add_argument('--package-commit', required=True)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    try:
        spec_path = args.spec.resolve()
        spec = load(spec_path)
        binding = inspect_binding(spec, spec_path.parent, args.package_commit)
        if args.check_only:
            print(json.dumps(binding, ensure_ascii=False, indent=2))
        else:
            destination = install(binding, spec)
            print(destination / 'THEORY_HANDOFF.md')
            print('Source paths bound. Semantic alignment and experiment validation remain required.')
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f'Theory binding stopped: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
