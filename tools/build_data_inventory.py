"""Optional list of currently tracked problem files. Not required to run A.

No hashes, reconstruction manifests, automatic downloads, or pickle decoding.
Writes a local report, never overwrites the repository's running instructions.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=Path('.work/current_inputs.json'))
    args = parser.parse_args()
    proc = subprocess.run(['git', 'ls-files', '-z', '--', '题目'], cwd=ROOT,
                          capture_output=True, check=True)
    rows = []
    for name in proc.stdout.decode('utf-8').split('\0'):
        if not name or name.startswith('题目/E题/'):
            continue
        path = ROOT / name
        row = dict(path=name, available=path.is_file())
        if path.is_file():
            with path.open('rb') as f:
                pointer = f.read(128).startswith(b'version https://git-lfs.github.com/spec/v1')
            row.update(local_bytes=path.stat().st_size, lfs_pointer=pointer)
        rows.append(row)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    report = dict(generated_at=datetime.now(timezone.utc).isoformat(),
                  scope='Current tracked inputs only; local_bytes is NOT remote original size for LFS pointers.', files=rows)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(out)


if __name__ == '__main__':
    main()
