"""Create a separate local writing-agent root; preserve the original template."""
from __future__ import annotations
import json, shutil, subprocess, sys, zipfile
from pathlib import Path
from common import read,write,within,fresh,stamp

BASE_ITEMS=['AGENTS.md','CLAUDE.md','README.md','Start-HuaweiCup.ps1','工作流模式.json',
            '.agents','.claude','华为杯_求解规范','华为杯_论文规范模板']
REQUIRED=['AGENTS.md','工作流模式.json','华为杯_求解规范/tools/workshop.py',
          '华为杯_论文规范模板/README.md','.agents/skills']
SKILLS=['academic-figure-skill/SKILL.md','modelviz-skill-main/SKILL.md',
        'gmcm-abstract/SKILL.md','gmcm-supporting-materials/SKILL.md']


def probe(template):
    root=Path(template).resolve()
    missing=[x for x in REQUIRED if not(root/x).exists()]
    for x in SKILLS:
        if not(root/'.agents/skills'/x).is_file():missing.append('.agents/skills/'+x)
    return {'template_root':str(root),'ready':not missing,'missing':missing,
            'note':'Checks actual file locations. Skill assets and visual quality are reviewed in their own stages.'}


def install(template, home, package):
    source=Path(template).resolve();package=Path(package).resolve();home=Path(home).resolve()
    if source==home or source in home.parents or home in source.parents:
        raise ValueError('Choose a separate sibling root for the new agent')
    status=probe(source)
    if not status['ready']:raise ValueError(json.dumps(status,ensure_ascii=False))
    fresh(home)
    for name in BASE_ITEMS:
        p=source/name
        if p.is_dir():shutil.copytree(p,home/name,ignore=shutil.ignore_patterns('__pycache__','.venv','node_modules'))
        elif p.is_file():shutil.copy2(p,home/name)
    shutil.copytree(package,home/'paper_a_workbench',ignore=shutil.ignore_patterns('__pycache__','review','examples'))
    # The copyright block and original AGENTS text remain byte-for-byte at the front.
    with (home/'AGENTS.md').open('a',encoding='utf-8') as f:
        f.write('\n\n# 本次 ORION 论文任务的用户优先约定\n')
        f.write((package/'policies'/'WRITING_CONSTITUTION.md').read_text(encoding='utf-8'))
        f.write('\n先完整读取 ORION_论文总控提示词.md。资料接入只写输入区，论文必须通过原 workshop.py 创建/登记。\n')
    for name in ('LOCAL_CODEX_PROMPT.md','UPDATE_CODEX_PROMPT.md'):
        dest='ORION_论文总控提示词.md' if name.startswith('LOCAL') else 'ORION_论文更新提示词.md'
        shutil.copy2(package/name,home/dest)
    for skill in (package/'skills').iterdir():
        if skill.is_dir():shutil.copytree(skill,home/'.agents/skills'/skill.name)
    (home/'题目').mkdir(exist_ok=True);(home/'数据'/'ORION_论文资料').mkdir(parents=True,exist_ok=True)
    state={'installed_at':stamp(),'template_source':str(source),'agent_root':str(home),'workspace_root':None,
           'snapshot':None,'mode':'prepare','paper_complete':False}
    write(home/'.orion_paper'/'SESSION.json',state)
    return state


def package_inputs(home,snapshot):
    """One actual FILE for workshop.py --input, plus the original question DOCX."""
    home=Path(home).resolve();snapshot=Path(snapshot).resolve();snapshot.relative_to(home/'数据')
    lock=read(snapshot/'SOURCE_LOCK.json')
    required={g['id'] for g in lock['profile']['sources'] if g.get('required',True)}
    missing=[r for r in lock['files'] if r['source'] in required and r['status']!='present']
    missing += [e for e in lock['errors'] if e.get('required')]
    if missing:raise ValueError('Required inputs still need materialization: '+json.dumps(missing[:8],ensure_ascii=False))
    questions=[snapshot/r['local'] for r in lock['files'] if r['source']=='problem' and r['path'].endswith('.docx') and r['status']=='present']
    if len(questions)!=1:raise ValueError('Select exactly one original question DOCX')
    target=home/'数据'/('ORION_论文资料_'+lock['snapshot_id']+'.zip')
    if target.exists():raise FileExistsError(target)
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=3) as z:
        for p in sorted(snapshot.rglob('*')):
            if p.is_file():z.write(p,p.relative_to(snapshot))
    question=home/'题目'/('A题_'+lock['snapshot_id']+'.docx');shutil.copy2(questions[0],question)
    command=[sys.executable,'-B',str(home/'华为杯_求解规范/tools/workshop.py'),'start',
             '--template-root',str(home),'--runtime','codex','--input',str(question.relative_to(home)),
             '--input',str(target.relative_to(home))]
    write(home/'.orion_paper'/'START_COMMAND.json',{'argv':command,'snapshot':str(snapshot),
        'rule':'Host displays the preserved copyright once, then executes the original entry. No workspace id is guessed.'})
    return {'inputs':[str(question),str(target)],'start_argv':command}


def bind(home,workspace):
    home=Path(home).resolve();workspace=Path(workspace).resolve();workspace.relative_to(home)
    manifest=read(workspace/'工作区清单.json')
    if manifest.get('runtime')!='codex':raise ValueError('Workspace runtime must be codex')
    state=read(home/'.orion_paper'/'SESSION.json');state['workspace_root']=str(workspace)
    write(home/'.orion_paper'/'SESSION.json',state)
    return state


def template_source(repo, revision, destination, prefix='20hw_myskill_distribution/20hw_myskill_distribution'):
    """Restore the user's authorized base resources, excluding historical workshops/data."""
    from sources import GitSource
    git=GitSource(repo);rev=git.resolve(revision);out=fresh(destination);records=[]
    for item in BASE_ITEMS:
        for path,blob in git.entries(rev,prefix+'/'+item):
            data=git.get(rev,path)
            if data.startswith(b'version https://git-lfs.github.com/spec/'):
                # Explicit input hydration only; no checkout or writes to existing projects.
                git.run('lfs','fetch','--include='+prefix+'/'+item,'--exclude=','origin',rev)
                data=git.lfs_data(data)
            rel=str(Path(path).relative_to(prefix));target=within(out,rel)
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
            records.append({'source':path,'revision':rev,'blob':blob,'local':rel,'bytes':len(data)})
    write(out/'TEMPLATE_SOURCE.json',{'files':records,'revision':rev,'source':prefix})
    return probe(out)
