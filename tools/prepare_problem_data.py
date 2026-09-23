"""Safely expand problem ZIP/XZ inputs and record a SHA-256 audit trail.

Run from any directory. Archives are deleted only with --delete-archives,
after every expanded file has been read back and its SHA-256 checked.
Existing files are never overwritten; mismatched content aborts the run.
"""
import argparse
import hashlib
import json
import lzma
from pathlib import Path, PurePosixPath
import stat
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / '题目'
AUDIT = ROOT / '调研' / '数据整理记录.json'

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def rel(path):
    return path.relative_to(ROOT).as_posix()

def name_of(info):
    name = info.filename
    if not info.flag_bits & 0x800:
        try:
            name = name.encode('cp437').decode('gbk')
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    return name.replace('\\', '/')

def safe_target(base, name):
    parts = PurePosixPath(name)
    if parts.is_absolute() or '..' in parts.parts or ':' in name:
        raise ValueError(f'Unsafe archive path: {name}')
    target = (base / Path(*parts.parts)).resolve()
    if not target.is_relative_to(DATA.resolve()):
        raise ValueError(f'Path escapes problem directory: {target}')
    return target

def write_checked(stream, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    staged = target.with_name(target.name + '.extracting')
    if staged.exists():
        raise FileExistsError(staged)
    h = hashlib.sha256()
    size = 0
    with staged.open('xb') as out:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            out.write(chunk)
            h.update(chunk)
            size += len(chunk)
    expected = h.hexdigest()
    if digest(staged) != expected:
        raise RuntimeError(f'Read-back verification failed: {staged}')
    existed = target.exists()
    if existed:
        if digest(target) != expected:
            raise FileExistsError(f'Existing file differs; retained both files: {target}')
        staged.unlink()
    else:
        staged.rename(target)
    return {'path': rel(target), 'bytes': size, 'sha256': expected,
            'action': 'verified_existing' if existed else 'extracted'}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--delete-archives', action='store_true')
    args = parser.parse_args()
    records = json.loads(AUDIT.read_text(encoding='utf-8')) if AUDIT.exists() else []
    archives = sorted(p for p in DATA.rglob('*') if p.is_file() and p.suffix.lower() in {'.zip', '.xz'})
    for archive in archives:
        print('Processing', rel(archive), flush=True)
        record = {'archive': rel(archive), 'archive_bytes': archive.stat().st_size,
                  'archive_sha256': digest(archive), 'files': [], 'deleted': False}
        if archive.suffix.lower() == '.zip':
            with zipfile.ZipFile(archive) as z:
                entries = z.infolist()
                names = [name_of(i) for i in entries]
                roots = {PurePosixPath(n).parts[0] for n in names if PurePosixPath(n).parts}
                base = archive.parent if roots == {archive.stem} else archive.with_suffix('')
                for i, name in zip(entries, names):
                    if stat.S_ISLNK(i.external_attr >> 16):
                        raise ValueError(f'Symlink in archive: {name}')
                    target = safe_target(base, name)
                    if i.is_dir():
                        target.mkdir(parents=True, exist_ok=True)
                    else:
                        with z.open(i) as stream:
                            row = write_checked(stream, target)
                        if row['bytes'] != i.file_size:
                            raise RuntimeError(f'Size mismatch: {name}')
                        record['files'].append(row)
        else:
            with lzma.open(archive, 'rb') as stream:
                record['files'].append(write_checked(stream, archive.with_suffix('')))
        if args.delete_archives:
            # The source is a specific discovered file inside DATA, not a tree.
            if not archive.resolve().is_relative_to(DATA.resolve()):
                raise ValueError('Archive outside DATA')
            archive.unlink()
            record['deleted'] = True
        records.append(record)
        AUDIT.parent.mkdir(parents=True, exist_ok=True)
        AUDIT.write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print('Verified', len(record['files']), 'files;', 'deleted' if record['deleted'] else 'retained', rel(archive), flush=True)

if __name__ == '__main__':
    main()
