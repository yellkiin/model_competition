"""Run A experiments directly; no repository audit or test-suite prerequisite.

Use existing official A inputs, otherwise restore only missing/LFS-pointer files
from the local A zip, otherwise fetch only A through LFS. CPU and stdlib only.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import io
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ATTACHMENT_NAME = '通用神经网络处理器下的多核调度问题  附件'
SCRIPTS = ('contest_io.py', 'evaluation_validation.py',
           'multicore_cut_evaluate_problem_1.py', 'multicore_cut_evaluate_problem_2.py',
           'multicore_cut_evaluate_problem_3.py', 'schedule_step1.py',
           'schedule_step2.py', 'schedule_step3.py', 'singlecore_evaluate.py',
           'stub_multicore_cut_and_schedule.py')


def needs_input(path: Path) -> bool:
    if not path.is_file() or not path.stat().st_size:
        return True
    with path.open('rb') as stream:
        return stream.read(128).startswith(b'version https://git-lfs.github.com/spec/v1')


def missing_inputs(attachment: Path) -> list[str]:
    expected = ['data/config.txt'] + [f'data/case_{i:03d}.json' for i in range(1, 101)]
    expected += [f'code/{name}' for name in SCRIPTS]
    return [name for name in expected if needs_input(attachment / name)]


def attachment_path(root: Path) -> Path:
    found = sorted((root / '题目' / 'A题').glob('*附件'))
    if len(found) > 1:
        raise RuntimeError('Multiple A attachment directories: keep one active directory under 题目/A题.')
    return found[0] if found else root / '题目' / 'A题' / ATTACHMENT_NAME


@contextmanager
def attachment_zip(path: Path):
    with zipfile.ZipFile(path) as outer:
        candidates = [n for n in outer.namelist() if n.endswith('附件.zip') and '__MACOSX/' not in n]
        if candidates:
            if len(candidates) != 1:
                raise ValueError('More than one attachment ZIP; pass the A attachment ZIP directly.')
            with zipfile.ZipFile(io.BytesIO(outer.read(candidates[0]))) as inner:
                yield inner
        else:
            yield outer


def restore_inputs(archive: Path, target: Path) -> int:
    """Fill missing inputs only. Do not compare or overwrite existing real inputs."""
    written = 0
    with attachment_zip(archive) as source:
        names = [n for n in source.namelist() if n.endswith('data/case_001.json') and '__MACOSX/' not in n]
        if len(names) != 1:
            raise ValueError('Cannot locate A data/case_001.json in this archive.')
        prefix = names[0][:-len('data/case_001.json')]
        for entry in source.infolist():
            if entry.is_dir() or not entry.filename.startswith(prefix):
                continue
            relative = PurePosixPath(entry.filename[len(prefix):])
            if relative.is_absolute() or '..' in relative.parts or not relative.parts:
                continue
            if relative.parts[0] not in ('code', 'data', 'docs') and str(relative) != 'README.md':
                continue
            destination = target.joinpath(*relative.parts)
            if needs_input(destination):
                destination.parent.mkdir(parents=True, exist_ok=True)
                with source.open(entry) as src, destination.open('wb') as dst:
                    import shutil
                    shutil.copyfileobj(src, dst)
                written += 1
    return written


def ensure_inputs(root: Path, archive: str | None = None) -> Path:
    target = attachment_path(root)
    if not missing_inputs(target):
        print('Using existing A inputs.', flush=True)
        return target
    if archive:
        path = Path(archive).expanduser()
        if not path.is_absolute():
            path = root / path
        choices = [path]
    else:
        choices = [root / 'A题.zip', root / '题目' / 'A题.zip', root / '题目' / 'A题' / 'A题.zip',
                   root / (ATTACHMENT_NAME + '.zip'), root / '题目' / 'A题' / (ATTACHMENT_NAME + '.zip')]
    for path in choices:
        if path.is_file():
            print(f'Restoring missing A inputs from {path}', flush=True)
            restore_inputs(path, target)
            if not missing_inputs(target):
                return target
    print('Fetching only A inputs through Git LFS; no other problem data is requested.', flush=True)
    try:
        subprocess.run(['git', 'lfs', 'pull', '--include=题目/A题/**', '--exclude='], cwd=root, check=True)
    except (OSError, subprocess.CalledProcessError) as error:
        raise RuntimeError('A inputs unavailable. Put A题.zip in the repository root or pass --archive PATH.') from error
    missing = missing_inputs(target)
    if missing:
        raise RuntimeError('A inputs still missing: ' + ', '.join(missing[:5]))
    return target


def run_module(module: str, args: list[str], log: Path) -> None:
    env = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8', PYTHONUNBUFFERED='1')
    command = [sys.executable, '-X', 'utf8', '-u', '-m', module, *args]
    print('\n> ' + subprocess.list2cmdline(command), flush=True)
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open('a', encoding='utf-8') as stream:
        stream.write('\n> ' + subprocess.list2cmdline(command) + '\n')
        stream.flush()
        with subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace') as proc:
            try:
                for line in proc.stdout:
                    print(line, end='', flush=True)
                    stream.write(line)
                    stream.flush()
                status = proc.wait()
            except KeyboardInterrupt:
                proc.terminate()
                proc.wait()
                raise
        if status:
            raise RuntimeError(f'{module} failed (exit {status}). See {log}; completed results were not deleted.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['prepare', 'dev', 'main', 'cross', 'granularity', 'all'], nargs='?', default='all')
    parser.add_argument('--archive', help='Optional path to the original A ZIP or inner attachment ZIP')
    parser.add_argument('--out-root', default='research_a/runs')
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--main-variant', default='full', choices=['full', 'common', 'no_memory', 'coarse', 'fine', 'locality', 'spill', 'cache', 'critical', 'explore', 'portfolio', 'unranked'])
    args = parser.parse_args()
    if args.workers < 1:
        parser.error('--workers must be positive')
    os.chdir(ROOT)
    ensure_inputs(ROOT, args.archive)
    if args.stage == 'prepare':
        return
    out = Path(args.out_root).resolve()
    out.mkdir(parents=True, exist_ok=True)
    cases = out / 'cases.json'
    if args.stage != 'cross' and not cases.exists():
        run_module('research_a.run', ['prepare', '--out', str(cases)], out / 'prepare.log')
    # Fixed sequential stages, never concurrent experiments against the same output.
    stages = ['dev', 'main', 'cross'] if args.stage == 'all' else [args.stage]
    for stage in stages:
        log = out / f'{stage}.log'
        if stage in ('dev', 'main'):
            common = ['run', '--manifest', str(cases), '--questions', '1', '2', '3',
                      '--workers', str(args.workers), '--out', str(out / stage), '--resume']
            if stage == 'dev':
                common += ['--split', 'dev', '--cores', '2', '4', '--variants', 'common', 'full', 'no_memory', 'no_cache',
                           '--seeds', '0', '1', '2', '--budget', '24']
            else:
                common += ['--cores', '1', '2', '3', '4', '5', '--variants', 'rr', args.main_variant, '--seeds', '0', '--budget', '32']
            run_module('research_a.run', common, log)
            run_module('research_a.report', ['analyze', '--source', str(out / stage), '--out', str(out / (stage + '_report'))], log)
        elif stage == 'cross':
            run_module('research_a.run', ['cross', '--source', str(out / 'main'), '--variant', args.main_variant,
                       '--cores', '1', '2', '3', '4', '5', '--seeds', '0', '--out', str(out / 'cross'), '--resume'], log)
            run_module('research_a.report', ['cross', '--source', str(out / 'cross'), '--out', str(out / 'cross_report')], log)
        else:
            run_module('research_a.run', ['granularity', '--manifest', str(cases), '--split', 'dev', '--questions', '1', '2', '3',
                       '--cores', '2', '4', '5', '--out', str(out / 'granularity')], log)
    print(f'Completed requested stages. Results: {out}', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile) as exc:
        raise SystemExit(str(exc))
