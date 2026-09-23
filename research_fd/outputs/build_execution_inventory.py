"""Collect evidence paths and statuses without inventing missing experiment results."""
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

runs = []
for path in sorted((OUT / 'logs').glob('*.json')):
    obj = read(path)
    if not isinstance(obj, dict) or 'command' not in obj:
        continue
    runs.append({'label': path.stem, 'record': str(path.relative_to(OUT)),
                 **{k: obj.get(k) for k in ('command', 'started', 'finished', 'elapsed_s', 'status', 'returncode')}})
validations = []
for path in sorted(OUT.rglob('validation.json')):
    if 'pip_cache' in path.parts:
        continue
    obj = read(path)
    if not isinstance(obj, dict):
        continue
    validations.append({'path': str(path.relative_to(OUT)),
                        **{k: obj.get(k) for k in ('status', 'transport_valid', 'radio_valid', 'relay_valid', 'joint_valid', 'plan')},
                        'issue_count': len(obj.get('issues', []))})
scripts = {}
for path in sorted(OUT.rglob('*.py')):
    if any(x in path.parts for x in ('pip_cache', '__pycache__', 'tmp')):
        continue
    scripts[str(path.relative_to(OUT))] = hashlib.sha256(path.read_bytes()).hexdigest()
result = {
    'generated_at_utc': datetime.now(timezone.utc).isoformat(),
    'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
    'tracked_worktree_status': subprocess.check_output(['git', 'status', '--short'], cwd=ROOT, text=True).strip(),
    'official_input_sha256': hashlib.sha256((OUT / 'd_official.json').read_bytes()).hexdigest(),
    'logged_runs': runs, 'plan_validations': validations, 'output_script_sha256': scripts,
    'interpretation': 'A process exit code 0 is not evidence of mathematical feasibility. Read solver stages and plan validation. Missing records are not executed results.'}
(OUT / 'execution_inventory.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'runs': len(runs), 'validations': len(validations), 'scripts': len(scripts),
                  'tracked_worktree_status': result['tracked_worktree_status']}, ensure_ascii=False))
