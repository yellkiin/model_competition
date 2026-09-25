"""Install a clean writing-agent root inside the current Codex project."""
from __future__ import annotations
import json, shutil, sys, zipfile
from pathlib import Path
from common import read,write,within,fresh,stamp
from paths import DEFAULT_DATA_ROOT,project_paths,template_candidates

BASE_ITEMS=['AGENTS.md','CLAUDE.md','README.md','Start-HuaweiCup.ps1','工作流模式.json',
            '.agents','.claude','华为杯_求解规范','华为杯_论文规范模板']
REQUIRED=['AGENTS.md','工作流模式.json','华为杯_求解规范/tools/workshop.py',
          '华为杯_论文规范模板/README.md','.agents/skills']
SKILLS=['academic-figure-skill/SKILL.md','modelviz-skill-main/SKILL.md',
        'gmcm-abstract/SKILL.md','gmcm-supporting-materials/SKILL.md',
        'algorithm-mechanism-diagram/SKILL.md','engineering-physics-mechanism-diagram/SKILL.md',
        'comprehensive-graphic-text-flowchart/SKILL.md',
        'sci-box-main/sci-box-main/skills/scibox-diagram/SKILL.md']


def probe(template):
    root=Path(template).resolve()
    missing=[x for x in REQUIRED if not(root/x).exists()]
    for x in SKILLS:
        if not(root/'.agents/skills'/x).is_file():missing.append('.agents/skills/'+x)
    return dict(template_root=str(root),ready=not missing,missing=missing,
                note='File availability only; original skills perform their own asset and figure checks.')


def locate_template(project='.', explicit=None):
    checked=[probe(p) for p in template_candidates(project,explicit)]
    return dict(selected=next((r['template_root'] for r in checked if r['ready']),None),candidates=checked)


def install(template,home,package,project_root=None,data_root=DEFAULT_DATA_ROOT,repo=None):
    source=Path(template).resolve();package=Path(package).resolve();home=Path(home).resolve()
    project=Path(project_root).resolve() if project_root else home.parent
    home.relative_to(project)
    if source==home or home in source.parents:raise ValueError('Choose a new agent subdirectory, distinct from the template')
    # Source may be the current project itself. Copy only enumerated shared items.
    for name in BASE_ITEMS:
        p=source/name
        if p==home or p in home.parents:raise ValueError('Agent destination is inside a shared template item')
    status=probe(source)
    if not status['ready']:raise ValueError(json.dumps(status,ensure_ascii=False))
    fresh(home)
    for name in BASE_ITEMS:
        p=source/name
        if p.is_dir():shutil.copytree(p,home/name,ignore=shutil.ignore_patterns('__pycache__','.venv','node_modules'))
        elif p.is_file():shutil.copy2(p,home/name)
    shutil.copytree(package,home/'paper_a_workbench',ignore=shutil.ignore_patterns('__pycache__'))
    # Retain original authorship/entry text and append this user's current task policy.
    with (home/'AGENTS.md').open('a',encoding='utf-8') as f:
        f.write('\n\n# 当前 ORION 论文任务的用户优先约定\n')
        f.write((package/'policies/WRITING_CONSTITUTION.md').read_text(encoding='utf-8'))
        f.write('\n完整执行 ORION_论文总控提示词.md；THEORY/ALGORITHM/TERMS已作为必需输入接入。\n')
    for name,dest in [('LOCAL_CODEX_PROMPT.md','ORION_论文总控提示词.md'),
                      ('UPDATE_CODEX_PROMPT.md','ORION_论文更新提示词.md')]:
        shutil.copy2(package/name,home/dest)
    for skill in (package/'skills').iterdir():
        if skill.is_dir():shutil.copytree(skill,home/'.agents/skills'/skill.name)
    (home/'题目').mkdir(exist_ok=True);(home/'数据/ORION_论文资料').mkdir(parents=True,exist_ok=True)
    resolved=project_paths(project,home,repo,data_root)
    state=dict(installed_at=stamp(),template_source=str(source),**resolved,workspace_root=None,
               snapshot=None,mode='prepare',paper_complete=False,theory_binding=None,
               data_policy='local_raw_read_only; github_code_theory_literature_reports')
    write(home/'.orion_paper/SESSION.json',state)
    return state


def package_inputs(home,snapshot):
    """Register actual FILE inputs; local raw archives stay in their source directory."""
    from theory import prepare
    home=Path(home).resolve();snapshot=Path(snapshot).resolve();snapshot.relative_to(home/'数据')
    lock=read(snapshot/'SOURCE_LOCK.json')
    required={g['id'] for g in lock['profile']['sources'] if g.get('required',True)}
    missing=[r for r in lock['files'] if r['source'] in required and r['status']!='present']
    missing += [e for e in lock['errors'] if e.get('required')]
    if missing:raise ValueError('Required inputs missing: '+json.dumps(missing[:8],ensure_ascii=False))
    binding=prepare(home,snapshot)
    questions=[within(snapshot,r['local']) for r in lock['files'] if r['source']=='problem' and r['path'].endswith('.docx') and r['status']=='present']
    if len(questions)!=1:raise ValueError('Select exactly one original question DOCX')
    target=home/'数据'/('ORION_论文资料_'+lock['snapshot_id']+'.zip')
    question=home/'题目'/('A题_'+lock['snapshot_id']+'.docx')
    if target.exists() or question.exists():raise FileExistsError(target if target.exists() else question)
    question.parent.mkdir(parents=True,exist_ok=True)
    temporary=target.with_name(target.name+'.tmp')
    state=read(home/'.orion_paper/SESSION.json')
    with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED,compresslevel=3) as z:
        for p in sorted(snapshot.rglob('*')):
            if p.is_file():z.write(p,p.relative_to(snapshot))
        for p in sorted(Path(binding['input_root']).iterdir()):
            if p.is_file():z.write(p,'paper_theory/'+p.name)
        if state.get('local_catalogue'):
            z.write(state['local_catalogue'],'local_data/LOCAL_CATALOGUE.json')
    shutil.copy2(questions[0],question)
    temporary.replace(target)
    command=[sys.executable,'-B',str(home/'华为杯_求解规范/tools/workshop.py'),'start',
             '--template-root',str(home),'--runtime','codex','--input',str(question.relative_to(home)),
             '--input',str(target.relative_to(home))]
    write(home/'.orion_paper/START_COMMAND.json',dict(argv=command,snapshot=str(snapshot),
        rule='Host reads original workflow and copyright, then executes the returned file-input command.'))
    state.update(snapshot=str(snapshot));write(home/'.orion_paper/SESSION.json',state)
    return dict(inputs=[str(question),str(target)],start_argv=command,theory_binding=binding,
                raw_data='Read selected local archives/directories; this capsule contains their catalogue, not another raw-data copy.')


def bind(home,workspace):
    from theory import prepare
    home=Path(home).resolve();workspace=Path(workspace).resolve();workspace.relative_to(home)
    if read(workspace/'工作区清单.json').get('runtime')!='codex':raise ValueError('Workspace runtime must be codex')
    state=read(home/'.orion_paper/SESSION.json');state['workspace_root']=str(workspace)
    write(home/'.orion_paper/SESSION.json',state)
    if state.get('snapshot'):prepare(home,state['snapshot'],workspace)
    return read(home/'.orion_paper/SESSION.json')


def template_source(repo,revision,destination,prefix='20hw_myskill_distribution/20hw_myskill_distribution'):
    """Restore only authorized shared resources, not earlier project outputs."""
    from sources import GitSource
    git=GitSource(repo);rev=git.resolve(revision);out=fresh(destination);records=[]
    for item in BASE_ITEMS:
        for path,blob in git.entries(rev,prefix+'/'+item):
            data=git.get(rev,path)
            if data.startswith(b'version https://git-lfs.github.com/spec/'):
                git.hydrate(rev,[path]);data=git.lfs_data(data)
            rel=str(Path(path).relative_to(prefix));target=within(out,rel)
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
            records.append(dict(source=path,revision=rev,blob=blob,local=rel,bytes=len(data)))
    write(out/'TEMPLATE_SOURCE.json',dict(files=records,revision=rev,source=prefix))
    return probe(out)
