"""One-time transfer of the locally tested, hash-locked authored files. Removed before PR."""
import hashlib
import json
import lzma
from pathlib import Path

root = Path.cwd().resolve()
base = root / '.github/migration-bootstrap'
packed = b''.join((base / f'part{i}.bin').read_bytes() for i in range(4))
assert hashlib.sha256(packed).hexdigest() == 'b86c0bf2ff8df34609df4764056b7973ba17d3f71915047840b91295510c1b13'
files = json.loads(lzma.decompress(packed))
assert isinstance(files, dict) and len(files) == 34
prefixes = ('各种建模agent/华为杯整合Agent/', '各种建模agent/hwb-math-modeling-skills/数模资料/优秀论文索引/近期论文原文/')
for name, content in files.items():
    assert isinstance(content, str)
    assert name in ('AGENTS.md', 'tools/huaweicup.py') or name.startswith(prefixes), name
    path = root / name
    path.resolve().relative_to(root)
    assert not path.exists(), f'Refuse to overwrite existing file: {name}'
for name, content in files.items():
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content.encode('utf-8'))
    print('TRANSFERRED', name, hashlib.sha256(path.read_bytes()).hexdigest())
