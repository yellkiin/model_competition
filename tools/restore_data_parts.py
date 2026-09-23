"""Restore oversized raw inputs from uncompressed, SHA-256 checked Git LFS parts.

Run `git lfs pull` first. Existing originals are verified, never overwritten.
--verify-only validates every part and the combined hash without creating files.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
BLOCK = 8 * 1024 * 1024

def safe_path(root, name):
    relative = PurePosixPath(name)
    if relative.is_absolute() or '..' in relative.parts or ':' in name or '\\' in name:
        raise ValueError(f'Unsafe manifest path: {name}')
    target = (root / Path(*relative.parts)).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError(f'Path escapes repository: {name}')
    return target

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(BLOCK), b''):
            h.update(block)
    return h.hexdigest()

def restore_entry(root, entry, verify_only=False):
    target = safe_path(root, entry['path'])
    exists = target.exists()
    if exists and (target.stat().st_size != entry['bytes'] or digest(target) != entry['sha256']):
        raise FileExistsError(f'Existing original differs; will not overwrite: {target}')
    parts = []
    for part in entry['parts']:
        path = safe_path(root, part['path'])
        if not path.is_file() or path.stat().st_size != part['bytes']:
            raise ValueError(f'Part missing or still an LFS pointer: {path}. Run git lfs pull.')
        parts.append((path, part))
    if sum(p['bytes'] for _, p in parts) != entry['bytes']:
        raise ValueError('Part sizes do not sum to original size')
    staged = target.with_name(target.name + '.reassembling')
    out = None
    created = False
    try:
        if not verify_only and not exists:
            target.parent.mkdir(parents=True, exist_ok=True)
            out = staged.open('xb')
            created = True
        combined = hashlib.sha256()
        for path, part in parts:
            h = hashlib.sha256()
            with path.open('rb') as source:
                for block in iter(lambda: source.read(BLOCK), b''):
                    h.update(block)
                    combined.update(block)
                    if out is not None:
                        out.write(block)
            if h.hexdigest() != part['sha256']:
                raise ValueError(f'Part SHA-256 mismatch: {path}')
        if combined.hexdigest() != entry['sha256']:
            raise ValueError(f'Combined SHA-256 mismatch: {target}')
        if out is not None:
            out.close()
            out = None
            if digest(staged) != entry['sha256']:
                raise ValueError('Read-back verification failed')
            # Windows rename does not replace an existing destination.
            if target.exists():
                raise FileExistsError(f'Destination appeared during reconstruction: {target}')
            staged.rename(target)
            created = False
    finally:
        if out is not None:
            out.close()
        if created:
            staged.unlink()
    return 'verified_existing' if exists else ('verified_parts' if verify_only else 'restored')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    manifest = json.loads((ROOT/'data-parts'/'manifest.json').read_text(encoding='utf-8'))
    if manifest['version'] != 1:
        raise ValueError('Unsupported manifest version')
    for entry in manifest['files']:
        action = restore_entry(ROOT, entry, args.verify_only)
        print(f'{action}: {entry["path"]}', flush=True)

if __name__ == '__main__':
    main()
