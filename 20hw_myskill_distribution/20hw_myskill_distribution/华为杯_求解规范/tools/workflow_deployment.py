"""Complete maintained deployment; never copy scientific state or QA approvals."""
from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import shutil
from filesystem_paths import native_path

SKILLS = (
    'academic-figure-skill', 'gmcm-abstract', 'gmcm-supporting-materials',
    'algorithm-mechanism-diagram', 'engineering-physics-mechanism-diagram',
    'comprehensive-graphic-text-flowchart',
    'sci-box-main/sci-box-main/skills/scibox-diagram',
    'sci-box-main/sci-box-main/skills/scibox-figure',
)
# Identity-based packages are supplied independently for each runtime. They are
# never mirrored from Codex into Claude by the legacy mirror operation.
SAME_RUNTIME_SKILLS = ('modelviz-skill',)
MAINTAINED = ('华为杯_求解规范', '华为杯_论文规范模板')
PROTECTED = ('论文', '数据', '题目', '提交附件', '求解')
SKIP = {'__pycache__', '.git', '.venv', 'node_modules', '.pytest_cache'}
REQUIRED = (
    '华为杯_求解规范/tools/workshop.py',
    '华为杯_求解规范/tools/workspace_context.py',
    '华为杯_求解规范/tools/workspace_cli.py',
    '华为杯_求解规范/tools/workspace_execution.py',
    '华为杯_求解规范/tools/workspace_schema.py',
    '华为杯_求解规范/工作区清单.schema.json',
    '华为杯_论文规范模板/gmcm-title.sty', '华为杯_论文规范模板/gmcm-layout.sty',
    '华为杯_论文规范模板/agent_manifest.schema.json', '华为杯_论文规范模板/摘要证据.schema.json',
    '华为杯_论文规范模板/参考文献证据.schema.json', '华为杯_论文规范模板/tools/ai_disclosure.py',
    '华为杯_论文规范模板/tools/build_latex.py',
    '华为杯_论文规范模板/tools/audit_paper.py', '华为杯_论文规范模板/tools/reference_evidence.py',
    '华为杯_论文规范模板/tools/abstract_evidence.py', '华为杯_论文规范模板/章节模板/附录模板.tex',
    '华为杯_求解规范/图数口径.schema.json', '华为杯_求解规范/academic_paper_review.schema.json',
    '华为杯_求解规范/tools/bibliography_inputs.py', '华为杯_求解规范/tools/figure_accounting.py',
    '华为杯_求解规范/tools/workflow_deployment.py',
    '华为杯_求解规范/tools/filesystem_paths.py',
    '华为杯_求解规范/tools/reproduce_supporting_materials.py',
    '华为杯_求解规范/tools/build_figure_accounting.py',
    '华为杯_求解规范/tools/visual_routes.py',
    '华为杯_求解规范/tools/audit_media_figures.py',
    '华为杯_求解规范/tools/inspect_visual_materials.py',
    '华为杯_求解规范/tools/extract_visual_materials.py',
    '华为杯_求解规范/tools/run_media_figure.py',
    '华为杯_求解规范/视觉素材证据.schema.json',
)

def sha(path):
    return hashlib.sha256(native_path(path).read_bytes()).hexdigest()

def copy_file(source, destination):
    # CPython's CopyFile2 path in shutil.copy2 needs an explicit extended path
    # for nested Windows skill assets, even when pathlib/open accept the path.
    shutil.copy2(native_path(source),native_path(destination))

def regular_files(base):
    extended=native_path(base)
    for p in sorted(extended.rglob('*')):
        relative=p.relative_to(extended)
        if set(relative.parts) & SKIP or p.suffix in ('.pyc', '.pyo'):
            continue
        if p.is_symlink() or (hasattr(p, 'is_junction') and p.is_junction()):
            raise ValueError('Deployment source cannot contain links: '+str(p))
        if p.is_file():
            p.resolve().relative_to(extended.resolve())
            yield base/relative

def source_plan(root, mirrors_only=False):
    root=Path(root).resolve()
    plan={}
    if not mirrors_only:
        for name in ('AGENTS.md','CLAUDE.md','README.md'):
            plan[name]=root/name
        for name in MAINTAINED:
            base=root/name
            if not base.is_dir():raise ValueError('Missing maintained tree: '+name)
            for path in regular_files(base):
                plan[path.relative_to(root).as_posix()]=path
        for name in REQUIRED:
            if name not in plan:raise ValueError('Missing required workflow input: '+name)
    for name in SKILLS:
        base=root/'.agents/skills'/name
        if not (base/'SKILL.md').is_file():raise ValueError('Missing skill entrypoint: '+name)
        for path in regular_files(base):
            tail=path.relative_to(base).as_posix()
            for runtime in (('.claude',) if mirrors_only else ('.agents','.claude')):
                plan[f'{runtime}/skills/{name}/{tail}']=path
    for rel,path in plan.items():
        if not native_path(path).is_file():raise ValueError('Missing maintained source: '+str(path))
        path.resolve().relative_to(root)
        if Path(rel).parts[0] in PROTECTED:raise ValueError('Scientific target in deployment inventory: '+rel)
    # Old deployment fixtures/projects have no template mode marker. Modern
    # templates require explicit same-runtime discovery; missing/ambiguous
    # packages fail before any copy. Different folder names remain intact.
    if (root/'工作流模式.json').is_file():
        if not mirrors_only:
            for name in ('tools/drawing_sources.py', 'tools/modelviz_bridge.py', 'tools/chart_policy.py',
                         'drawing_preflight.schema.json', 'modelviz_references.schema.json',
                         'modelviz_run.schema.json', 'modelviz_qa.schema.json', 'chart_family_map.json'):
                if '华为杯_求解规范/'+name not in plan:
                    raise ValueError('Missing dual-source workflow input: '+name)
        from drawing_sources import discover
        for runtime in ('codex','claude'):
            for identity in SAME_RUNTIME_SKILLS:
                base=discover(root,runtime,identity)
                if mirrors_only:
                    continue
                for path in regular_files(base):
                    plan[path.relative_to(root).as_posix()]=path
    return dict(sorted(plan.items()))

def protected(root):
    root=Path(root); result={}
    for name in PROTECTED:
        base=native_path(root/name)
        if base.is_dir():
            for path in base.rglob('*'):
                if path.is_file():result[(Path(name)/path.relative_to(base)).as_posix()]=sha(path)
    return result

def deploy_legacy(root, project=None, mirrors_only=False):
    root=Path(root).resolve()
    project=Path(project).resolve() if project is not None else root
    mirrors_only = mirrors_only or project == root
    if root.is_relative_to(project) and root != project:
        raise ValueError('Target cannot be an ancestor of the template')
    if mirrors_only and project != root:
        raise ValueError('Mirror-only deployment operates on the template root')
    plan=source_plan(root,mirrors_only)
    # Resolve every destination before writing; junctions must not redirect a
    # maintained file into scientific state or outside the requested project.
    for rel in plan:
        dst=project/rel
        resolved=dst.resolve()
        resolved.relative_to(project)
        if resolved.relative_to(project).parts[0] in PROTECTED:
            raise ValueError('Destination resolves into protected scientific state: '+rel)
        if native_path(dst).exists() and not native_path(dst).is_file():raise ValueError('Destination is not a file: '+str(dst))
    before=protected(project) if project.exists() else {}
    token=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
    history=root/'output/工作流部署'/token
    history.mkdir(parents=True,exist_ok=False)
    rows=[]
    for rel,source in plan.items():
        destination=project/rel
        digest=sha(source)
        changed=not native_path(destination).is_file() or sha(destination)!=digest
        row={'source':str(source),'destination':str(destination),'relative_path':rel,'sha256':digest,'changed':changed}
        if changed:
            if native_path(destination).is_file():
                backup=history/'before'/rel
                native_path(backup.parent).mkdir(parents=True,exist_ok=True)
                copy_file(destination,backup)
                row['backup']=str(backup);row['previous_sha256']=sha(backup)
            native_path(destination.parent).mkdir(parents=True,exist_ok=True)
            copy_file(source,destination)
        rows.append(row)
    after=protected(project)
    drift=sorted(k for k in before.keys()|after.keys() if before.get(k)!=after.get(k))
    verified=all(sha(Path(r['destination']))==r['sha256']==sha(Path(r['source'])) for r in rows)
    report={'status':'PASS' if verified and not drift else 'FAIL','verified':verified,
            'template_root':str(root),'project_root':str(project),'mirrors_only':mirrors_only,
            'copies':rows,'protected_files':len(before),'protected_differences':drift,
            'report_path':str(history/'deployment.json'),
            'scope':'Maintained workflow and mirrored skills; scientific state and acceptance records are excluded.'}
    (history/'deployment.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report


def deploy(root, project=None, mirrors_only=False, *, mode='shared', runtime=None, inputs=(), purpose='production'):
    """Shared runs are the default; copying requires an explicit maintenance mode."""
    from workspace_context import create_workspace, resolve_context, MANIFEST
    root = Path(root).resolve()
    if mode == 'legacy':
        if project is None or mirrors_only:
            raise ValueError('legacy 模式须指定独立项目；两端同步使用 maintenance 模式')
        if (Path(project) / MANIFEST).exists() or Path(project).name.startswith('workshop_v'):
            raise ValueError('禁止向共享工作区部署完整规范与 skill 副本')
        return deploy_legacy(root, project)
    if mode == 'maintenance':
        if not mirrors_only or project is not None and Path(project).resolve() != root:
            raise ValueError('maintenance 模式仅允许显式 mirrors-only')
        return deploy_legacy(root, mirrors_only=True)
    if mode != 'shared' or mirrors_only:
        raise ValueError('新工作区使用 shared；模板同步必须显式 maintenance')
    if project is None:
        context = create_workspace(root, runtime, inputs, purpose=purpose)
    else:
        if inputs:
            raise ValueError('续跑不自动导入新输入；须明确登记新增输入')
        context = resolve_context(workspace_root=project, template_root=root, runtime=runtime)
    integrity = context.check_shared()
    return {'status': integrity['status'], 'mode': 'shared', 'copies': [],
            'template_root': str(context.template_root), 'project_root': str(context.workspace_root),
            'runtime': context.runtime, 'integrity': integrity,
            'scope': '引用共享规则；不复制总控、规范或skill，不授予科学完成状态。'}
