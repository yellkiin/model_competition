"""Restricted Windows discovery, PATH persistence, and verified download adapters."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import urllib.request
import uuid
import zipfile
from workspace_context import bounded, atomic_json, file_hash, now


def supported():
    return os.name == 'nt' and platform.machine().lower() in ('amd64', 'x86_64') and int(platform.version().split('.')[0]) >= 10


def run(argv, *, cwd=None, env=None, timeout=120):
    try:
        result = subprocess.run([str(v) for v in argv], cwd=cwd, env=env, capture_output=True,
                                text=True, encoding='utf8', errors='replace', timeout=timeout, shell=False,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    except subprocess.TimeoutExpired as exc:
        return {'name': Path(str(argv[0])).name, 'returncode': 124,
                'output': 'timeout: '+str(exc)}
    return {'name': Path(str(argv[0])).name, 'returncode': result.returncode,
            'output': (result.stdout + '\n' + result.stderr).strip()}


def user_root():
    if not supported():
        raise ValueError('正式环境准备仅支持 Windows 10/11 x64')
    return bounded(Path(os.environ['LOCALAPPDATA']), 'HuaweiCupWorkflow')


def path_key(value):
    import ntpath
    return ntpath.normpath(os.path.expandvars(value.strip().strip('"'))).casefold()


def append_path(previous, entries):
    # Keep existing entries verbatim, including expandable registry variables.
    parts, seen = [], set()
    for raw in previous.split(';'):
        if raw.strip() and path_key(raw) not in seen:
            parts.append(raw); seen.add(path_key(raw))
    for raw in entries:
        if raw and path_key(str(raw)) not in seen:
            parts.append(str(raw)); seen.add(path_key(str(raw)))
    return ';'.join(parts)


def persist(entries, variables):
    import winreg
    changes = []
    try:
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, 'Environment', 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
            for name, value in [('Path', entries), *variables.items()]:
                if name not in {'Path', 'DRAWIO_CLI'}:
                    raise ValueError('Unsupported environment variable')
                try: before, kind = winreg.QueryValueEx(key, name)
                except FileNotFoundError: before, kind = '', winreg.REG_EXPAND_SZ
                after = append_path(before, value) if name == 'Path' else value
                if after != before:
                    winreg.SetValueEx(key, name, 0, kind, after)
                changes.append(dict(variable=name, before=before, after=after, changed=after != before))
        return {'status': 'satisfied', 'changes': changes}
    except OSError as exc:
        return {'status': 'blocked', 'changes': changes, 'error': str(exc)}


def process_env(entries=(), variables=None, base=None):
    env = dict(os.environ if base is None else base)
    env['PATH'] = os.pathsep.join(dict.fromkeys([*(str(p) for p in entries), *env.get('PATH','').split(os.pathsep)]))
    env.update(variables or {})
    env.update(PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1')
    env.pop('PYTHONPATH', None); env.pop('PYTHONHOME', None)
    return env


def executables(name, extra=()):
    candidates = [*extra]
    paths = os.environ.get('PATH', '').split(os.pathsep)
    if os.name == 'nt':
        import winreg
        for hive, keyname in [(winreg.HKEY_CURRENT_USER, 'Environment'), (winreg.HKEY_LOCAL_MACHINE, r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment')]:
            try:
                with winreg.OpenKey(hive, keyname) as key:
                    paths.extend(os.path.expandvars(winreg.QueryValueEx(key, 'Path')[0]).split(';'))
            except OSError: pass
    suffixes = ('', '.exe', '.bat') if os.name == 'nt' else ('',)
    for folder in paths:
        if folder:
            candidates.extend(Path(folder.strip('"')) / (name+s) for s in suffixes)
    result=[]; seen=set()
    for p in candidates:
        if not p: continue
        p=Path(p)
        if path_key(str(p)) in seen: continue
        seen.add(path_key(str(p)))
        if p.is_file(): result.append(p.resolve())
    return result


def python_probe(exe, expected_prefix=None):
    if 'windowsapps' in str(exe).casefold():
        raise ValueError('拒绝 WindowsApps 占位别名；请使用实际解释器路径')
    script = "import sys,json,struct,venv,ensurepip; print(json.dumps(dict(executable=sys.executable,prefix=sys.prefix,base=sys.base_prefix,version=list(sys.version_info[:3]),bits=struct.calcsize('P')*8)))"
    r=run([exe,'-I','-c',script],timeout=30)
    if r['returncode']: raise ValueError(r['output'])
    data=json.loads(r['output'])
    if not (3,10) <= tuple(data['version'][:2]) < (3,14) or data['bits'] != 64:
        raise ValueError('需要 Python >=3.10,<3.14 x64')
    if Path(data['executable']).resolve() != Path(exe).resolve():
        raise ValueError('解释器路径不符')
    if expected_prefix and (Path(data['prefix']).resolve() != Path(expected_prefix).resolve() or data['base'] == data['prefix']):
        raise ValueError('不是本工作区独立虚拟环境')
    return data


def download(artifact, cache, events, opener=urllib.request.urlopen):
    """Only catalog artifacts enter here; verify publisher SHA-256 on every reuse."""
    cache=Path(cache); cache.mkdir(parents=True,exist_ok=True)
    name=artifact['filename']
    if Path(name).name != name or any(c in name for c in ':\\/'):
        raise ValueError('Invalid artifact filename')
    target=bounded(cache, artifact['sha256'][:16]+'-'+name)
    def valid(path):
        if file_hash(path) != artifact['sha256']: raise ValueError('发布方 SHA-256 校验失败')
        with path.open('rb') as f: magic=f.read(4)
        if not magic.startswith(b'MZ' if artifact['format']=='exe' else b'PK'):
            raise ValueError('下载内容不是声明的安装包格式')
    if target.exists():
        try:
            valid(target)
            events.append(dict(action='cache_reuse',path=str(target),sha256=artifact['sha256'],time=now()))
            return target
        except ValueError as exc:
            target.rename(target.with_name(target.name+'.rejected-'+uuid.uuid4().hex))
            events.append(dict(action='cache_rejected',error=str(exc),time=now()))
    for url in artifact['urls']:
        if not url.startswith('https://'): raise ValueError('仅允许 HTTPS')
        for attempt in range(2):
            part=target.with_name(target.name+'.part-'+uuid.uuid4().hex)
            try:
                req=urllib.request.Request(url,headers={'User-Agent':'HuaweiCupWorkflow/1.0'})
                with opener(req,timeout=45) as response, part.open('wb') as stream:
                    if response.status != 200 or 'text/html' in response.headers.get('Content-Type','').lower():
                        raise ValueError('HTTP 状态或文件类型无效')
                    final=response.geturl()
                    if not final.startswith('https://'): raise ValueError('拒绝非 HTTPS 重定向')
                    shutil.copyfileobj(response,stream,1024*1024)
                valid(part); os.replace(part,target)
                atomic_json(target.with_suffix(target.suffix+'.json'),dict(url=url,final_url=final,sha256=artifact['sha256'],publisher_reference=artifact['publisher_reference'],downloaded_at=now()))
                events.append(dict(action='download',url=url,attempt=attempt+1,status='satisfied',time=now()))
                return target
            except (OSError,ValueError) as exc:
                if part.exists(): part.rename(part.with_name(part.name+'.rejected'))
                events.append(dict(action='download',url=url,attempt=attempt+1,status='failed',error=str(exc),time=now()))
    raise ValueError('全部可信下载源失败；详见安装记录')


def extract_zip(archive, destination):
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('Archive links forbidden')
            bounded(destination, info.filename)
        z.extractall(destination)
