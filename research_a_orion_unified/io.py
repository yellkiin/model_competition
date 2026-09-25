"""Small portable records; no file fingerprints or environment benchmark."""
from __future__ import annotations
import csv, gzip, json, re, zipfile, os, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _binary_reader(path):
    """Windows readers explicitly allow rename; close owns the native handle."""
    if os.name != 'nt':
        return open(path, 'rb')
    import ctypes, msvcrt
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                       ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    create.restype = wintypes.HANDLE
    handle = create(str(Path(path).resolve()), 0x80000000, 0x00000007,
                    None, 3, 0x80, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    except Exception:
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle(handle)
        raise
    return os.fdopen(fd, 'rb')


def read(path):
    p=Path(path)
    with _binary_reader(p) as stream:
        data=stream.read()
    if p.suffix=='.gz':data=gzip.decompress(data)
    return json.loads(data.decode('utf-8-sig'))


WRITE_DEADLINE = None

def set_write_deadline(value):
    global WRITE_DEADLINE
    WRITE_DEADLINE=value


def write(path, value):
    """Same-directory complete-file replacement with a short bounded retry.

    No direct overwrite of a live JSON file and no global retry loop. Temp names
    are unique even if a previous writer was interrupted. Deadline applies to
    serialization and retries in a solver, not only to the official evaluator.
    """
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_name(p.name+f'.{os.getpid()}.{time.monotonic_ns()}.tmp')
    try:
        if WRITE_DEADLINE is not None and time.monotonic()>=WRITE_DEADLINE:
            raise TimeoutError('result write exceeded job deadline')
        op=gzip.open if p.suffix=='.gz' else open
        with op(tmp,'wt',encoding='utf8',**({'compresslevel':1} if p.suffix=='.gz' else {})) as f:
            json.dump(value,f,ensure_ascii=False,separators=(',',':'),allow_nan=False)
        for attempt in range(6):
            if WRITE_DEADLINE is not None and time.monotonic()>=WRITE_DEADLINE:
                raise TimeoutError('result write exceeded job deadline')
            try:
                os.replace(tmp,p)
                return
            except PermissionError:
                if attempt==5:raise
                delay=min(.08,.01*(2**attempt))
                if WRITE_DEADLINE is not None:
                    delay=min(delay,max(0.,WRITE_DEADLINE-time.monotonic()))
                time.sleep(delay)
    finally:
        try:tmp.unlink(missing_ok=True)
        except OSError:pass


def csv_read(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def csv_write(path, rows, fields=None):
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    fields = fields or list(dict.fromkeys(k for r in rows for k in r))
    with p.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fields, extrasaction='ignore'); w.writeheader(); w.writerows(rows)


def plan_key(plan):
    # Exact official labels and order; no unproved equivalence of ID renamings.
    return (tuple(sorted((int(u), s) for u,s in plan['node_to_subgraph'].items())),
            tuple(tuple(seq) for seq in plan['core_schedules']))


def score(response):
    raw = response.get('official_result', response)
    return int(raw['makespan']), int(raw['data_movement_bytes']['added_copy_bytes'])


def official_root(value=None):
    root = Path(value).resolve() if value else next((ROOT / '题目/A题').glob('*附件'))
    config = root / 'data/config.txt'
    if not config.is_file() or not (root / 'code/evaluation_validation.py').is_file():
        raise FileNotFoundError(f'Original A attachment incomplete: {root}')
    return root, config


def required_keys(case):
    return [(case, 0, 1)] + [(case, q, n) for q in (1, 2, 3) for n in range(2, 6)] + [(case, 3, 1)]


def key_name(case, q, n):
    return f'{case}_q{q}_n{n}'


def install_plan_archive(archive, destination):
    """Extract only official two-field plans, preserving q/n/case path layout."""
    dest = Path(destination); count = 0
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            m = re.search(r'(?:^|/)q([0-3])/n([1-5])/(case_\d{3})_multicore_res\.json$', info.filename)
            if not m: continue
            p = json.loads(z.read(info).decode('utf-8-sig'))
            if set(p) != {'node_to_subgraph', 'core_schedules'}:
                raise ValueError(f'Not an official plan: {info.filename}')
            q, n, case = m.groups()
            write(dest / f'q{q}' / f'n{n}' / f'{case}_multicore_res.json', p); count += 1
    if not count: raise ValueError('No plans with qN/nN/case_NNN_multicore_res.json layout')
    return count


def plan_path(root, case, q, n):
    return Path(root) / f'q{q}' / f'n{n}' / f'{case}_multicore_res.json'
