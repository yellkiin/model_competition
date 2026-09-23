"""Run a real experiment with immutable logs under outputs. Usage: LABEL -- COMMAND..."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
label = sys.argv[1]
if not label.replace('_', '').replace('-', '').isalnum():
    raise ValueError('Use a simple label')
args = sys.argv[2:]
if args and args[0] == '--':
    args = args[1:]
logs = OUT / 'logs'
logs.mkdir(exist_ok=True)
meta = logs / f'{label}.json'
log = logs / f'{label}.log'
if meta.exists() or log.exists():
    raise FileExistsError(f'Previous attempt retained; use a new label: {label}')
env = os.environ.copy()
env.update(PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', MPLCONFIGDIR=str(OUT/'mplconfig'), TEMP=str(OUT/'tmp'), TMP=str(OUT/'tmp'))
command = [sys.executable, *args]
source_paths = [*(ROOT/'research_fd').glob('d_*.py'), *(OUT/'runtime/research_fd').glob('d_*.py')]
record = {'command': command, 'cwd': str(ROOT), 'started': datetime.datetime.now().astimezone().isoformat(), 'python': platform.python_version(), 'status': 'running', 'source_sha256': {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths}}
meta.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
t = time.monotonic()
print(f'Running {label}; log: {log}', flush=True)
try:
    with log.open('w', encoding='utf-8') as f:
        result = subprocess.run(command, cwd=ROOT, env=env, stdout=f, stderr=subprocess.STDOUT)
    record.update(status='completed' if result.returncode == 0 else 'failed', returncode=result.returncode)
except BaseException as exc:
    record.update(status='runner_error', error=repr(exc), returncode=1)
finally:
    record.update(elapsed_s=time.monotonic()-t, finished=datetime.datetime.now().astimezone().isoformat())
    meta.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k: record[k] for k in ('status', 'returncode', 'elapsed_s')}, ensure_ascii=False), flush=True)
sys.exit(record['returncode'])
