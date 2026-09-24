"""Restore an ORION ZIP by concatenating its complete numbered parts."""
import json
from pathlib import Path
import shutil
import sys

manifest_path = Path(sys.argv[1]).resolve()
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
folder = manifest_path.parent
name = manifest['archive_name']
if Path(name).name != name:
    raise ValueError('Archive name must be a filename')
output = folder / name
if output.exists():
    raise FileExistsError(f'Preserve the existing archive: {output}')
offset = 0
paths = []
for part in manifest['parts']:
    if Path(part['name']).name != part['name']:
        raise ValueError('Part name must be a filename')
    path = folder / part['name']
    if part['offset'] != offset or path.stat().st_size != part['bytes']:
        raise ValueError(f'Missing, incomplete, or out-of-order part: {path}')
    paths.append(path)
    offset += part['bytes']
if offset != manifest['archive_bytes']:
    raise ValueError('Part sizes do not cover the archive')
with output.open('xb') as out:
    for path in paths:
        with path.open('rb') as source:
            shutil.copyfileobj(source, out, 1024 * 1024)
print(output)
