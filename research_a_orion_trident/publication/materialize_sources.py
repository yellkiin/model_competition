"""Publication only: reproduce previously delivered source bytes from pinned Git objects.

No solver, official evaluator, benchmark or repository audit is executed. The
readable edit records were generated from the already-delivered local commit.
"""
from pathlib import Path
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PREFIX = 'research_a_orion_trident/'


def main():
    rows = [row for path in sorted(HERE.glob('derived_*.json'))
            for row in json.loads(path.read_text(encoding='utf8'))['files']]
    for ref in sorted({row['ref'] for row in rows}):
        if not re.fullmatch(r'[0-9a-f]{40}', ref):
            raise ValueError('A frozen commit is required')
        subprocess.run(['git', 'fetch', '--depth=1', '--filter=blob:none', '--no-tags', 'origin', ref], cwd=ROOT, check=True)
    prepared = []
    for row in rows:
        target = ROOT / row['target']
        if not row['target'].startswith(PREFIX) or '..' in target.parts:
            raise ValueError('Publication target is outside Trident')
        content = subprocess.check_output(['git', 'show', row['ref'] + ':' + row['source']], cwd=ROOT).decode('utf8')
        for before, after in row['replacements']:
            content = content.replace(before, after)
        lines = content.splitlines(keepends=True)
        for edit in reversed(row['edits']):
            start = edit['at']
            end = start + len(edit['old'])
            if lines[start:end] != edit['old']:
                raise ValueError(f"Frozen source context differs: {row['target']} at {start}")
            lines[start:end] = edit['new']
        payload = ''.join(lines).encode('utf8')
        if len(payload) != row['bytes']:
            raise ValueError('Published byte length differs: ' + row['target'])
        prepared.append((target, payload, row))
    receipt = []
    for target, payload, row in prepared:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        receipt.append({'path':row['target'], 'bytes':len(payload), 'source_ref':row['ref'], 'source_path':row['source']})
        print(row['target'], len(payload), flush=True)
    (HERE / 'SOURCE_COPY_RECEIPT.json').write_text(json.dumps({'purpose':'source publication only', 'experiments_run':0, 'files':receipt}, ensure_ascii=False, indent=2) + '\n', encoding='utf8')


if __name__ == '__main__':
    main()
