"""Windows capability preparation. Only this explicit entry may install software.

No natural-language commands/URLs are executed. Catalog adapters own every argv.
The general workspace write guard is deliberately not widened.
"""
from __future__ import annotations
import copy
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import uuid
from environment_contract import load_catalog, read_json, validate, validate_needs, merge_needs, active, ENV_DIR
from environment_platform import (run, supported, user_root, python_probe, process_env,
                                  persist, download, extract_zip)
from environment_probes import package_probe, python_function, tex_candidates, tex_probe, draw_candidates, draw_probe
from environment_reports import write_reports
from workspace_context import atomic_json, file_hash, now, manifest_lock, resolve_context, MANIFEST, validate_workspace_manifest

NEEDS='求解/软件需求.json'
REPORT='求解/环境检测.json'


def integrity(context):
    if context.check_shared()['status'] != 'PASS':
        raise ValueError('共享资源变化；先显式 adopt-resources 并重核受影响证据')
    if context.check_inputs()['status'] != 'PASS': raise ValueError('原始输入变化')


def initialize(context):
    path=context.write_path(NEEDS)
    if path.exists(): return validate_needs(read_json(path))
    needs=validate_needs(read_json(ENV_DIR/'基础需求.json'))
    formats={Path(r['workspace_path']).suffix.lower() for r in context.manifest['inputs']}
    for cap,extensions in [('pdf',{'.pdf'}),('tables',{'.csv','.xlsx','.xls','.tsv'}),('word',{'.docx'})]:
        if formats & extensions:
            needs=merge_needs(needs,{'schema_version':'1.0','requirements':[dict(capability=cap,necessity='required',enabled=True,sources=['data_format'],reason='登记输入格式需要最小读取能力：'+', '.join(sorted(formats & extensions)),provider=None)]})
    atomic_json(path,needs)
    return needs


def register(context, additions):
    integrity(context)
    with manifest_lock(context.workspace_root):
        needs=initialize(context)
        merged=merge_needs(needs,validate_needs(read_json(context.read_path(additions))))
        catalog=load_catalog();providers={p['id'] for p in catalog['providers']}
        for row in merged['requirements']:
            if row['provider'] and row['provider'] not in providers: raise ValueError('Unknown provider selection')
        atomic_json(context.write_path(NEEDS),merged)
    return merged


def venv_python(context):
    return context.write_path('.venv/Scripts/python.exe')


def ensure_venv(context, base, events):
    target=venv_python(context);root=target.parent.parent
    if target.is_file():
        try:
            data=python_probe(target,root)
            pip=run([target,'-I','-m','pip','--version'])
            if pip['returncode']: raise ValueError(pip['output'])
            events.append(dict(action='venv_reuse',path=str(target),version=data['version'],time=now()))
            return target
        except (ValueError,OSError) as exc:
            events.append(dict(action='venv_invalid',error=str(exc),time=now()))
    info=python_probe(base)
    if root.exists():
        # Preserve the broken/moved environment. Never recursively delete it.
        backup=context.write_path('求解/缓存/失效虚拟环境/'+uuid.uuid4().hex)
        backup.parent.mkdir(parents=True,exist_ok=True);root.rename(backup)
    r=run([base,'-I','-m','venv',root],timeout=180)
    events.append(dict(action='venv_create',**r,time=now()))
    if r['returncode']: raise ValueError('venv 创建失败: '+r['output'])
    python_probe(target,root)
    if run([target,'-I','-m','pip','--version'])['returncode']: raise ValueError('venv pip 不可用')
    return target


def pip_install(python, packages, catalog, events, folder, offline=False):
    cache=user_root()/'cache/pip';cache.mkdir(parents=True,exist_ok=True)
    env=process_env([python.parent]);env['PIP_CONFIG_FILE']=os.devnull
    for key in list(env):
        if key.startswith('PIP_') and key!='PIP_CONFIG_FILE': env.pop(key)
    # Wheelhouse is project-specific; pip verifies downloaded wheels against index hashes.
    wheelhouse=user_root()/'cache/wheels';wheelhouse.mkdir(parents=True,exist_ok=True)
    specs=list(dict.fromkeys(p['requirement'] for p in packages))
    common=[python,'-I','-m','pip','--isolated','--disable-pip-version-check']
    local=run([*common,'install','--no-index','--find-links',wheelhouse,*specs],cwd=folder,env=env,timeout=600)
    events.append(dict(action='pip_offline_cache',**local,time=now()))
    if local['returncode']==0: return
    if offline: raise ValueError('离线缓存不能满足缺失依赖')
    for index in catalog['pip_indexes']:
        # Build sdists into wheels while the index is available. A later
        # --no-index install then needs neither network nor undeclared build deps.
        cmd=[*common,'wheel','--index-url',index,'--retries','1','--timeout','30','--cache-dir',cache,'--wheel-dir',wheelhouse,*specs]
        result=run(cmd,cwd=folder,env=env,timeout=1200)
        events.append(dict(action='pip_download',source=index,**result,time=now()))
        if result['returncode']: continue
        result=run([*common,'install','--no-index','--find-links',wheelhouse,*specs],cwd=folder,env=env,timeout=600)
        events.append(dict(action='pip_install',source=index,**result,time=now()))
        if result['returncode']==0: return
    raise ValueError('Python 依赖安装失败；详见安装记录')


def install_external(provider,catalog,events,offline):
    if offline: raise ValueError('离线模式不安装缺失外部软件')
    adapter=provider['adapter'];artifact=provider['artifact']
    if adapter not in {'texlive','drawio'} or not artifact: raise ValueError('没有经过核验的自动安装适配器')
    cache=user_root()/'cache/downloads';software=user_root()/'software';software.mkdir(parents=True,exist_ok=True)
    archive=download(artifact,cache,events)
    stage=software/('staging-'+uuid.uuid4().hex);stage.mkdir()
    if adapter=='drawio':
        extract_zip(archive,stage)
        files=list(stage.rglob('draw.io.exe'))
        if len(files)!=1: raise ValueError('draw.io 发行物布局不符')
        destination=software/'drawio'
        if destination.exists(): destination=software/('drawio-'+uuid.uuid4().hex)
        stage.rename(destination)
        exe=destination/files[0].relative_to(stage)
    else:
        r=run([archive,'-y'],cwd=stage,timeout=600)
        events.append(dict(action='tinytex_extract',**r,time=now()))
        if r['returncode']: raise ValueError('TinyTeX 自解压失败')
        files=list(stage.rglob('xelatex.exe'))
        if len(files)!=1: raise ValueError('TinyTeX 发行物布局不符')
        destination=software/'TinyTeX'
        if destination.exists(): destination=software/('TinyTeX-'+uuid.uuid4().hex)
        texroot=files[0].parent.parent.parent
        rel=files[0].relative_to(texroot);texroot.rename(destination);exe=destination/rel
    events.append(dict(action='software_install',provider=provider['id'],path=str(exe),time=now()))
    return exe


def repair_tex(exe,provider,catalog,events,offline):
    if offline: raise ValueError('离线模式不能补齐 TeX 宏包')
    env=process_env([exe.parent])
    if provider=='miktex':
        miktex=exe.with_name('miktex.exe')
        if not miktex.is_file(): raise ValueError('MiKTeX 管理命令缺失')
        # Explicit per-command repository; no global source setting or auto-install UI.
        repos=['https://mirrors.tuna.tsinghua.edu.cn/CTAN/systems/win32/miktex/tm/packages/','https://ctan.math.illinois.edu/systems/win32/miktex/tm/packages/']
        for repo in repos:
            r=run([miktex,'packages','require','--repository',repo,*catalog['tex_packages']],env=env,timeout=1200)
            events.append(dict(action='miktex_packages',source=repo,**r,time=now()))
            if r['returncode']==0:return
        raise ValueError('MiKTeX 缺包修复失败；没有另装发行版')
    tlmgr=exe.with_name('tlmgr.bat')
    if not tlmgr.is_file(): raise ValueError('TeX Live 包管理器缺失')
    version=run([exe,'--version'],env=env)['output']
    match=re.search(r'TeX Live (\d{4})',version)
    if not match: raise ValueError('无法确认 TeX Live 年度')
    local_year=match[1]
    # Ask tlmgr about remote release before installing; it rejects cross-year updates.
    import urllib.request
    for repo in catalog['tex_repositories']:
        try:
            with urllib.request.urlopen(repo+'/tlpkg/texlive.tlpdb',timeout=30) as response:
                text=response.read(2*1024*1024).decode('utf8','replace')
            year=re.search(r'depend release/(\d{4})',text)
            if not year or year[1]!=local_year:
                events.append(dict(action='tex_repository_rejected',source=repo,local_year=local_year,reason='年度不兼容或不能确认',time=now()));continue
            r=run([tlmgr,'--repository',repo,'install',*catalog['tex_packages']],env=env,timeout=1800)
            events.append(dict(action='tex_packages',source=repo,**r,time=now()))
            if r['returncode']==0:return
        except (OSError,ValueError) as exc: events.append(dict(action='tex_packages',source=repo,error=str(exc),time=now()))
    raise ValueError('TeX 宏包补齐失败或仓库年度不兼容；不升级/另装用户发行版')


def detect(context, catalog, needs, folder, *, prepare=False, offline=False, base_python=None, persist_user=True):
    events=[];results=[];paths=[];variables={};python=venv_python(context)
    persistent='unexamined'
    if not supported(): raise ValueError('仅实现 Windows 10/11 x64 环境准备')
    if prepare:
        python=ensure_venv(context,Path(base_python or sys.executable),events)
    caps={c['id']:c for c in catalog['capabilities']};providers={p['id']:p for p in catalog['providers']}
    env=process_env([python.parent])
    ordered=sorted(needs['requirements'],key=lambda r:({'python':0,'workflow-core':1,'pdf':2,'paper-python':3,'latex':5,'fonts':6,'drawio':7}.get(r['capability'],4)))
    for requirement in ordered:
        cid=requirement['capability'];row=dict(capability=cid,status='unexamined',provider=None,version='',path=None,detail='',tests=[])
        results.append(row)
        if not active(requirement):row.update(status='not_applicable',detail='未启用的条件或可选需求');continue
        cap=caps.get(cid)
        if not cap:row.update(status='unresolved',detail='目录未支持；须维护时核验官方来源和适配器');continue
        selected=requirement['provider']
        if selected and selected not in cap['providers']: raise ValueError('提供者不提供此能力: '+selected)
        ids=[selected] if selected else cap['providers']
        work=folder/cid;work.mkdir(parents=True,exist_ok=True)
        try:
            if cid=='python':
                data=python_probe(python,python.parent.parent)
                pip=run([python,'-I','-m','pip','--version']);row['tests']=[pip]
                if pip['returncode']:raise ValueError('venv pip 不可用')
                row.update(status='satisfied',provider='cpython',path=str(python),version='.'.join(map(str,data['version'])))
                continue
            if providers[ids[0]]['adapter']=='python_packages':
                p=providers[ids[0]];row['provider']=p['id']
                probe=package_probe(python,p['packages'],work,env)
                row['tests'].append(probe)
                if probe['returncode'] and prepare:
                    row['status']='installing'
                    pip_install(python,p['packages'],catalog,events,work,offline)
                    probe=package_probe(python,p['packages'],work,env);row['tests'].append(probe)
                if probe['returncode']: raise ValueError('工作区依赖导入/版本检查失败')
                function=python_function(cid,python,work,env)
                if function:row['tests'].append(function)
                if function and function['returncode']:raise ValueError('最小功能测试失败')
                row.update(status='satisfied',version=probe['output'],path=str(python));continue
            if cid in {'latex','fonts'}:
                candidates=tex_candidates()
                # A successful provider is a binding for this workspace. On a
                # later run probe it first and stop as soon as it passes, so a
                # second installed TeX distribution cannot trigger repairs.
                prior_path = None
                try:
                    previous = validate(read_json(context.read_path(REPORT)), '环境检测')
                    prior = next((x for x in previous['results'] if x['capability'] == cid and x['status'] == 'satisfied'), None)
                    if prior and prior.get('path') and Path(prior['path']).is_file():
                        prior_path = Path(prior['path']).resolve()
                        candidates = [prior_path] + [x for x in candidates if x.resolve() != prior_path]
                except (OSError, ValueError, StopIteration):
                    pass
                if not candidates and prepare and cid=='latex': candidates=[install_external(providers['texlive'],catalog,events,offline)]
                if not candidates: raise ValueError('没有可用 XeLaTeX；字体检测也需要 XeLaTeX')
                failed_candidates=[]
                for index,exe in enumerate(candidates):
                    version=run([exe,'--version'])['output'];pid='miktex' if 'miktex' in version.casefold() else 'texlive'
                    if cid=='latex' and pid not in ids:continue
                    tests=tex_probe(exe,work/str(index),python,context.template_root,cid=='fonts')
                    row['tests'].extend(tests)
                    if all(t['returncode']==0 for t in tests):
                        row.update(status='satisfied',provider='system-fonts' if cid=='fonts' else pid,path=str(exe),version=version.split('\n')[0]);paths.append(str(exe.parent));break
                    failed_candidates.append((index,exe,pid,tests,version))
                if row['status']!='satisfied' and prepare and cid=='latex':
                    # Only repair after every installed provider has failed.
                    # Font absence is not a package-manager problem.
                    for index,exe,pid,tests,version in failed_candidates:
                        if any('Missing required font' in t['output'] for t in tests):continue
                        try:
                            repair_tex(exe,pid,catalog,events,offline)
                            repaired=tex_probe(exe,work/(str(index)+'-repaired'),python,context.template_root)
                            row['tests'].extend(repaired)
                            if all(t['returncode']==0 for t in repaired):
                                row.update(status='satisfied',provider=pid,path=str(exe),version=version.split('\n')[0]);paths.append(str(exe.parent));break
                        except (ValueError,OSError) as exc:row['detail']=str(exc)
                if row['status']!='satisfied':raise ValueError(row['detail'] or '中文/XeLaTeX/字体功能测试失败；字体必须合法安装，不替换样式')
            elif cid=='drawio':
                candidates=draw_candidates()
                if not candidates and prepare:candidates=[install_external(providers['drawio'],catalog,events,offline)]
                for index,exe in enumerate(candidates):
                    tests=draw_probe(exe,work/str(index),python);row['tests'].extend(tests)
                    if all(t['returncode']==0 for t in tests):
                        row.update(status='satisfied',provider='drawio',path=str(exe),version='PNG/PDF 功能测试通过');paths.append(str(exe.parent));variables['DRAWIO_CLI']=str(exe);break
                if row['status']!='satisfied':raise ValueError('draw.io PNG/PDF 导出或解码失败')
        except (OSError,ValueError,TimeoutError) as exc:
            row.update(status='blocked' if prepare else 'missing',detail=str(exc))
    if prepare and persist_user:
        # Base Python only; never persist a workspace Scripts directory.
        data=python_probe(python,python.parent.parent)
        base=Path(data['base']);base_entries=[str(base),str(base/'Scripts')]
        persistence=persist([*base_entries,*paths],variables);persistent=persistence['status']
        events.append(dict(action='user_environment',**persistence,time=now()))
    states={r['status'] for r in results}
    if persistent=='blocked' or 'blocked' in states: status='blocked'
    elif 'failed' in states: status='failed'
    elif states-{'satisfied','not_applicable'}: status='missing'
    else: status='satisfied'
    report=dict(schema_version='1.0',status=status,checked_at=now(),workspace=str(context.workspace_root),requirements_sha256=file_hash(context.read_path(NEEDS)),catalog_sha256=file_hash(ENV_DIR/'软件目录.json'),python=str(python) if python.is_file() else None,path_entries=list(dict.fromkeys(paths)),variables=variables,persistent_status=persistent,results=results)
    validate(report,'环境检测')
    return report,events


def prepare(context, *, offline=False, base_python=None, persist_user=True):
    integrity(context)
    with manifest_lock(context.workspace_root):
        needs=initialize(context);catalog=load_catalog()
        folder=context.write_path('求解/验收输出/环境/'+uuid.uuid4().hex);folder.mkdir(parents=True)
        # Save failures as well as success; never convert plans into satisfied entries.
        try:
            report,events=detect(context,catalog,needs,folder,prepare=True,offline=offline,base_python=base_python,persist_user=persist_user)
        except Exception as exc:
            atomic_json(folder/'失败.json',dict(status='failed',error=str(exc),time=now()));raise
        write_dependency_files(context,catalog,needs,report)
        validate(report,'环境检测')
        atomic_json(folder/'安装记录.json',{'schema_version':'1.0','events':events})
        atomic_json(folder/'环境检测.json',report);atomic_json(context.write_path(REPORT),report)
        atomic_json(context.write_path('求解/安装记录.json'),{'schema_version':'1.0','latest':str((folder/'安装记录.json').relative_to(context.workspace_root)).replace('\\','/')})
        write_reports(context,catalog,needs,report)
        data=copy.deepcopy(context.manifest)
        data['environment']={'schema_version':'1.0','requirements_path':NEEDS,'report_path':REPORT,'status':report['status']}
        validate_workspace_manifest(data);atomic_json(context.workspace_root/MANIFEST,data)
    integrity(resolve_context(workspace_root=context.workspace_root,runtime=context.runtime))
    return report


def write_dependency_files(context,catalog,needs,report):
    caps={c['id']:c for c in catalog['capabilities']};providers={p['id']:p for p in catalog['providers']};specs=[]
    for row in needs['requirements']:
        if active(row) and row['capability'] in caps:
            p=providers[row['provider'] or caps[row['capability']]['providers'][0]]
            specs.extend(i['requirement'] for i in p['packages'])
    context.write_path('requirements.txt').write_text('# Generated direct dependencies; resolved versions are in requirements.lock.txt\n'+'\n'.join(sorted(set(specs)))+'\n',encoding='utf8')
    python=venv_python(context)
    if python.is_file():
        r=run([python,'-I','-m','pip','list','--format=json'])
        if r['returncode']==0:
            packages=json.loads(r['output'])
            context.write_path('requirements.lock.txt').write_text('# Resolved workspace environment, including transitive dependencies\n'+'\n'.join(sorted(x['name']+'=='+x['version'] for x in packages))+'\n',encoding='utf8')
        check=run([python,'-I','-m','pip','check'])
        if check['returncode']:
            report['status']='failed';atomic_json(context.write_path(REPORT),report)


def check(context):
    """No workspace writes or installs; temporary functional outputs auto-cleaned."""
    integrity(context)
    path=context.read_path(NEEDS)
    if not path.is_file():return {'status':'missing','detail':'尚未初始化需求；运行 env prepare'}
    with tempfile.TemporaryDirectory(prefix='huawei-env-check-') as folder:
        report,_=detect(context,load_catalog(),validate_needs(read_json(path)),Path(folder))
    return report


def execution_environment(context, python=None):
    if not context.manifest.get('environment'):
        return python or sys.executable,process_env()  # Explicit adoption needed for historical runs.
    needs=validate_needs(read_json(context.read_path(NEEDS)))
    report=validate(read_json(context.read_path(REPORT)),'环境检测')
    if report['workspace']!=str(context.workspace_root) or report['requirements_sha256']!=file_hash(context.read_path(NEEDS)) or report['catalog_sha256']!=file_hash(ENV_DIR/'软件目录.json'):
        raise ValueError('环境记录已过期或目录搬迁；运行 env prepare 重新探测')
    selected=venv_python(context);python_probe(selected,selected.parent.parent)
    if python and Path(python).resolve()!=selected.resolve():raise ValueError('拒绝非本工作区解释器')
    for entry in report['path_entries']:
        if not Path(entry).is_dir():raise ValueError('工具路径失效；运行 env prepare')
    return selected,process_env([selected.parent,*report['path_entries']],report['variables'])


def stage_needs(context,tool):
    """Known tool consumers, not a natural-language intent classifier."""
    name=Path(tool).name;caps=['workflow-core']
    if any(s in name for s in ('paper','figure','gallery','diagram','media','drawing')):caps+=['pdf']
    if name in {'collect_academic_paper_review.py','run_appendix_smoke.py'}:caps+=['paper-python','pdf','latex','fonts']
    if name in {'build_latex.py','audit_tex.py','build_appendix.py','audit_abstract.py','audit_citations.py'}:caps+=['paper-python']
    if 'docx' in name:caps+=['word']
    return {'schema_version':'1.0','requirements':[dict(capability=c,necessity='required',enabled=True,sources=['rendering'],reason='执行已选共享工具 '+name,provider=None) for c in dict.fromkeys(caps)]}


def ensure_stage(context,tool):
    if not context.manifest.get('environment'):return context
    current=validate_needs(read_json(context.read_path(NEEDS)));merged=merge_needs(current,stage_needs(context,tool))
    required={r['capability'] for r in stage_needs(context,tool)['requirements']}
    if merged==current:
        try:
            report=validate(read_json(context.read_path(REPORT)),'环境检测')
            quick=(report['workspace']==str(context.workspace_root) and
                   report['requirements_sha256']==file_hash(context.read_path(NEEDS)) and
                   report['catalog_sha256']==file_hash(ENV_DIR/'软件目录.json') and
                   all(Path(p).is_dir() for p in report['path_entries']))
            statuses={r['capability']:r['status'] for r in report['results']}
            if quick and all(statuses.get(cap)=='satisfied' for cap in required):
                execution_environment(context)
                return context
        except (OSError,ValueError,KeyError):pass
    else:
        with manifest_lock(context.workspace_root):atomic_json(context.write_path(NEEDS),merged)
    result=prepare(context)
    failed=[r['capability'] for r in result['results'] if r['capability'] in required and r['status']!='satisfied']
    if failed:raise ValueError('当前阶段能力受阻: '+', '.join(failed))
    return resolve_context(workspace_root=context.workspace_root,runtime=context.runtime)
