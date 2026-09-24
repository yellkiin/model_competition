"""File-based host bridge for ModelViz. No API keys, mock model or automatic visual PASS."""
from __future__ import annotations
import argparse
import ast
import importlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import types
from datetime import datetime, timezone

from build_academic_figure_asset_index import safe, sha, digest, write_json
from drawing_sources import discover, template_root, package_files, catalog, blank_review, review_ok
from visual_routes import figures, modelviz_panels, contract_digest, primary_output


def sidecar(plan):
    return Path(plan).with_suffix('.modelviz.json')


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def original_schemas(skill):
    """Load original Pydantic schemas under a unique package, avoiding src collisions."""
    name = '_gmcm_modelviz_' + digest(str(skill))[:12]
    if name not in sys.modules:
        module = types.ModuleType(name); module.__path__ = [str(skill / 'src')]
        sys.modules[name] = module
    return importlib.import_module(name + '.schemas')


def strict_model(model, value):
    from jsonschema import Draft202012Validator
    schema = model.model_json_schema()
    def close(node):
        if isinstance(node, dict):
            if node.get('type') == 'object' and 'properties' in node:
                node['additionalProperties'] = False
            for v in node.values(): close(v)
        elif isinstance(node, list):
            for v in node: close(v)
    close(schema)
    Draft202012Validator(schema).validate(value)
    return model.model_validate(value)


def dataset(path, sheet=None):
    import pandas as pd
    if path.suffix.lower() == '.csv':
        frame = pd.read_csv(path)
    elif path.suffix.lower() in {'.xlsx','.xls'}:
        book = pd.ExcelFile(path)
        if sheet is None and len(book.sheet_names) != 1:
            raise ValueError('Explicit sheet required for multi-sheet data')
        frame = pd.read_excel(book, sheet_name=sheet if sheet is not None else 0)
    else:
        raise ValueError('Use a reproducible conversion to CSV/XLSX; retain source hash, fields and units')
    if frame.empty or frame.columns.duplicated().any():
        raise ValueError('Empty data or duplicate fields')
    return {'file_name':path.name,'file_type':path.suffix[1:],'sheet_name':sheet,
            'row_count':len(frame),'column_count':len(frame.columns),'column_names':list(map(str,frame.columns)),
            'head_records':json.loads(frame.head(20).to_json(orient='records')),
            'sample_records':json.loads(frame.sample(min(20,len(frame)),random_state=42).to_json(orient='records')),
            'sampled':len(frame)>20,'sample_strategy':'First 20 and deterministic seed-42 sample; facts only',
            'warnings':['Data samples do not imply semantic understanding.']}


def prepare(root, plan_path, runtime, purpose='production'):
    plan = load(plan_path); template = template_root(root,runtime)
    skill = discover(template,runtime,'modelviz-skill'); rows={x['id']:x for x in catalog(skill)}
    if sidecar(plan_path).exists():
        raise ValueError('Preserve existing modelviz records; explicit archived migration required')
    records=[]
    for f in figures(plan):
        panels=modelviz_panels(f)
        if not panels: continue
        fid=f['figure_id']
        if not re.fullmatch(r'[\w-]+',fid): raise ValueError('Unsafe Figure ID')
        job=f'求解/绘图作业/{fid}'
        record={'figure_id':fid,'source_skill':'modelviz-skill','skill_root':skill.relative_to(template).as_posix(),
                'resource_digest':digest(package_files(skill)),'job_dir':job,'target_width_mm':0,
                'paper_geometry':{'source_tex':'','source_sha256':'','basis':''},'panels':[],
                'dependencies':[],'run_record_path':job+'/run_001.json','qa_path':job+'/qa_001.json','status':'planned'}
        for panel in panels:
            row=rows[panel['template_id']]
            record['panels'].append({'panel_id':panel['panel_id'],'template_id':row['id'],
                'template_sha256':sha(safe(skill,row['code_path'])),
                'preview_sha256':sha(safe(skill,row['preview'])) if safe(skill,row['preview']).is_file() else '',
                'source_locator':'','reference_review':blank_review(),'field_mapping':[],
                'preserved_design':[],'adaptation_reason':'','limitations':''})
            folder=safe(root,job)/panel['panel_id']; folder.mkdir(parents=True,exist_ok=True)
            context=dataset(safe(root,panel['result_file']))
            write_json(folder/'dataset_context.json',context)
            write_json(folder/'template.json',row)
            (folder/'reference.py').write_text(safe(skill,row['code_path']).read_text(encoding='utf-8-sig'),encoding='utf8')
        records.append(record)
    value={'schema_version':'1.0','runtime':runtime,'purpose':purpose,'figures':records,'paper_review_path':''}
    write_json(sidecar(plan_path),value)
    return value


def validate_host(root,f,rec,skill):
    """Validate original model outputs against real candidates, columns and working code."""
    schemas=original_schemas(skill); rows={r['id']:r for r in catalog(skill)}
    job=safe(root,rec['job_dir']); candidate_ids={c['reference_id'] for c in f['selection']['candidates'] if c['source_skill']=='modelviz-skill'}
    full_result=strict_model(schemas.AdaptationResult,load(job/'adaptation_result.json'))
    script=safe(root,f['script'])
    if script.read_text(encoding='utf-8-sig') != full_result.adapted_code:
        raise ValueError('adaptation_result.adapted_code differs from working script')
    tree=ast.parse(full_result.adapted_code)
    forbidden={'fit','fit_transform','train','optimize','GridSearchCV','RandomizedSearchCV','shap_values','partial_dependence'}
    if any(isinstance(n,ast.Call) and (getattr(n.func,'attr','') in forbidden or getattr(n.func,'id','') in forbidden) for n in ast.walk(tree)):
        raise ValueError('Training/fitting/analysis belongs to saved solving results, not plotting')
    imports={alias.name.split('.')[0] for n in ast.walk(tree) if isinstance(n,ast.Import) for alias in n.names}
    imports|={n.module.split('.')[0] for n in ast.walk(tree) if isinstance(n,ast.ImportFrom) and n.module}
    missing=[n for n in imports if n not in sys.stdlib_module_names and importlib.util.find_spec(n) is None]
    if missing: raise ValueError('Selected adaptation dependencies unavailable: '+','.join(sorted(missing)))
    columns=set()
    for p in modelviz_panels(f):
        folder=job/p['panel_id']; facts=dataset(safe(root,p['result_file']))
        if load(folder/'dataset_context.json') != facts: raise ValueError('Dataset context is stale')
        col=set(facts['column_names']); columns|=col
        s=strict_model(schemas.FinalTemplateSelection,load(folder/'final_template_selection.json'))
        context=schemas.FinalSelectionValidationContext(candidate_ids_to_names={k:rows[k]['name'] for k in candidate_ids},column_names=list(col))
        schemas.validate_final_selection_references(s,context)
        if s.needs_clarification or s.selected_template_id != p['template_id']: raise ValueError('Unresolved or inconsistent selected template')
        a=strict_model(schemas.AdaptationPlan,load(folder/'adaptation_plan.json'))
        if not a.can_proceed or a.required_preprocessing or a.template_id != p['template_id'] or a.template_name != rows[p['template_id']]['name']:
            raise ValueError('Adaptation must reference selected template and already-computed results')
        used=set(a.selected_columns)|{m.data_column for m in a.column_mappings}
        if not used or not used<=col or not set(p['fields'])<=col: raise ValueError('Nonexistent or missing mapped fields')
        rp=next(r for r in rec['panels'] if r['panel_id']==p['panel_id'])
        if {(m.data_column,m.template_role) for m in a.column_mappings}!={(m['data_column'],m['template_role']) for m in rp['field_mapping']}:
            raise ValueError('Sidecar and adaptation field mappings differ')
    if not set(full_result.data_columns_used)<=columns or not full_result.preserved_style_elements or not full_result.changes_summary:
        raise ValueError('Actual columns, template design inheritance and changes required')
    return {'imports':sorted(imports),'missing':missing,'interpreter':sys.executable}


def input_files(root,f,rec,runtime):
    from workspace_context import reference_path
    raw={f['script']}|{p['result_file'] for p in f['panels']}|{d['path'] for d in rec['dependencies']}
    job=safe(root,rec['job_dir'])
    raw.add((job/'adaptation_result.json').relative_to(root).as_posix())
    for p in modelviz_panels(f):
        raw.update((job/p['panel_id']/name).relative_to(root).as_posix() for name in
                   ('dataset_context.json','final_template_selection.json','adaptation_plan.json'))
    result={p:sha(safe(root,p)) for p in raw}
    geometry=rec['paper_geometry']['source_tex']; result[geometry]=sha(reference_path(root,geometry,runtime))
    return result


def audit_modelviz(plan_path,stage,root,runtime,allow_demo=False,main_tex=None,figure_ids=None):
    root=Path(root).resolve(); errors=[]
    try:
        plan=load(plan_path); selected=[f for f in figures(plan) if modelviz_panels(f) and (figure_ids is None or f['figure_id'] in figure_ids)]
        if not selected: return {'status':'PASS','failures':[]}
        data=load(sidecar(plan_path))
        from jsonschema import Draft202012Validator
        Draft202012Validator(load(Path(__file__).parent.parent/'modelviz_references.schema.json')).validate(data)
        if data['runtime']!=runtime: raise ValueError('ModelViz runtime mismatch')
        from workspace_context import shared_context, reference_path
        context=shared_context(root,runtime)
        if data['purpose']=='demo' and (not allow_demo or stage=='paper' or not (context and context.manifest['purpose']=='demo') and 'DEMO' not in str(plan_path).upper()):
            raise ValueError('DEMO requires isolated test workspace and cannot pass production paper')
        if context and context.manifest['purpose'] != data['purpose']: raise ValueError('Workspace purpose mismatch')
        recs={r['figure_id']:r for r in data['figures']}
        if len(recs)!=len(data['figures']) or set(recs)!={f['figure_id'] for f in figures(plan) if modelviz_panels(f)}:
            raise ValueError('ModelViz figure records must match actual provider panels')
        for f in selected:
            fid=f['figure_id']
            try:
                rec=recs[fid]; template=template_root(root,runtime); skill=discover(template,runtime,'modelviz-skill',rec['skill_root'])
                if rec['resource_digest']!=digest(package_files(skill)): raise ValueError('ModelViz package changed; selection and QA are stale')
                job=safe(root,rec['job_dir'])
                paths=[f['script'],*f['outputs'].values(),f['statistics_report'],rec['run_record_path'],rec['qa_path']]
                if not all(safe(root,p).is_relative_to(job) for p in paths): raise ValueError('Every Figure script/output/report must stay in its job_dir')
                if any(job==safe(root,r['job_dir']) or job.is_relative_to(safe(root,r['job_dir'])) or safe(root,r['job_dir']).is_relative_to(job) for r in data['figures'] if r['figure_id']!=fid):
                    raise ValueError('Figure job directories overlap')
                if not rec['target_width_mm']>0 or sha(reference_path(root,rec['paper_geometry']['source_tex'],runtime))!=rec['paper_geometry']['source_sha256'] or len(rec['paper_geometry']['basis'])<8:
                    raise ValueError('Actual paper width/geometry evidence required')
                from visual_routes import academic_panels
                if not academic_panels(f) and f['qa_report']!=rec['qa_path']: raise ValueError('ModelViz canonical QA path mismatch')
                pids=[p['panel_id'] for p in rec['panels']]
                if len(pids)!=len(set(pids)) or set(pids)!={p['panel_id'] for p in modelviz_panels(f)}: raise ValueError('Exact panel records required')
                rows={r['id']:r for r in catalog(skill)}
                for p in modelviz_panels(f):
                    r=next(x for x in rec['panels'] if x['panel_id']==p['panel_id']); row=rows[p['template_id']]
                    if r['template_id']!=row['id'] or r['template_sha256']!=sha(safe(skill,row['code_path'])) or r['preview_sha256']!=sha(safe(skill,row['preview'])):
                        raise ValueError('Selected original source/preview not current')
                    if not review_ok(r['reference_review']) or not r['preserved_design'] or any(len(r[k].strip())<8 for k in ('source_locator','adaptation_reason','limitations')):
                        raise ValueError('Actual source/preview detail review and design adaptation required')
                    if {m['data_column'] for m in r['field_mapping']}!=set(p['fields']) or {m['unit'] for m in r['field_mapping']}!=set(p['units']):
                        raise ValueError('Field/unit mapping differs from panel')
                for d in rec['dependencies']:
                    if sha(safe(root,d['path']))!=d['sha256']: raise ValueError('Declared dependency changed')
                validate_host(root,f,rec,skill)
                if stage in {'render','paper'}: audit_render(root,f,rec,runtime)
            except Exception as exc:
                errors.append({'code':fid+':modelviz_evidence','error':str(exc)})
        if stage=='paper':
            from collect_academic_paper_review import verify_evidence
            from visual_routes import paper_specs
            if main_tex is None: raise ValueError('Actual main TeX required')
            errors += [{'code':e} for e in verify_evidence(root,load(safe(root,data['paper_review_path'])),main_tex,runtime,paper_specs(plan_path))]
    except Exception as exc:
        errors.append({'code':'modelviz_gate_input_error','error':str(exc)})
    return {'status':'FAIL' if errors else 'PASS','failures':errors}


def artifacts(root,f,rec):
    from PIL import Image, ImageStat
    import pymupdf as fitz
    png=safe(root,f['outputs']['preview']); vector=safe(root,primary_output(f)); errors=[]
    with Image.open(png) as im:
        if min(im.info.get('dpi',(0,0)))<299 or min(im.size)<100 or max(ImageStat.Stat(im.convert('RGB')).var)<1:
            errors.append('PNG resolution or blank image')
    with fitz.open(vector) as doc:
        if vector.suffix.lower()=='.svg': doc=fitz.open('pdf',doc.convert_to_pdf())
        if len(doc)!=1 or abs(doc[0].rect.width/72*25.4-rec['target_width_mm'])>0.5 or not doc[0].get_drawings():
            errors.append('Single vector page at target width required')
    statistics=load(safe(root,f['statistics_report']))
    if not isinstance(statistics,dict) or not statistics: errors.append('Nonempty structured statistics required')
    return errors


def expected_views(root,f,rec,runtime):
    from prepare_academic_figure_qa import raster
    from run_media_figure import comparison_image
    skill=discover(template_root(root,runtime),runtime,'modelviz-skill',rec['skill_root']); rows={r['id']:r for r in catalog(skill)}
    final=raster(safe(root,f['outputs']['preview']))[0]
    tiles=[]
    for p in rec['panels']:
        row=rows[p['template_id']]
        tiles.extend((row['id'],im) for im in raster(safe(skill,row['preview'])))
    tiles.append(('CURRENT / '+f['figure_id'],final))
    return {'final':final,'grayscale':final.convert('L').convert('RGB'),
            'vector_page':raster(safe(root,primary_output(f)))[0], 'comparison':comparison_image(tiles)}


def prepare_qa(root,plan_path,figure_id,runtime):
    f=next(f for f in figures(load(plan_path)) if f['figure_id']==figure_id)
    rec=next(r for r in load(sidecar(plan_path))['figures'] if r['figure_id']==figure_id)
    path=safe(root,rec['qa_path'])
    if path.exists(): raise ValueError('Preserve previous QA; choose a new qa_path')
    views=[]
    for kind,im in expected_views(root,f,rec,runtime).items():
        dest=path.parent/(path.stem+'_'+kind+'.png'); im.save(dest)
        views.append({'kind':kind,'path':dest.relative_to(root).as_posix(),'sha256':sha(dest),**blank_review()})
    from workspace_resources import dependencies
    result={'status':'REVIEW_REQUIRED','contract_sha256':contract_digest(f,rec),
            'resource_dependencies':dependencies(root,runtime,'modelviz'),
            'inputs':input_files(root,f,rec,runtime),'outputs':{p:sha(safe(root,p)) for p in set(f['outputs'].values())|{f['statistics_report']}},
            'technical_failures':artifacts(root,f,rec),'views':views,
            'dimensions':{k:{'status':'REVIEW_REQUIRED','observation':''} for k in ('scientific_validity','reference_fidelity','print_readability')}}
    write_json(path,result); return result


def audit_render(root,f,rec,runtime):
    from workspace_resources import evidence_current
    from PIL import Image
    run=load(safe(root,rec['run_record_path'])); qa=load(safe(root,rec['qa_path']))
    from jsonschema import Draft202012Validator
    for name,value in [('modelviz_run.schema.json',run),('modelviz_qa.schema.json',qa)]:
        Draft202012Validator(load(Path(__file__).parent.parent/name)).validate(value)
    inputs=input_files(root,f,rec,runtime); outputs={p:sha(safe(root,p)) for p in set(f['outputs'].values())|{f['statistics_report']}}
    if not all(evidence_current(root,runtime,'modelviz',v) for v in (run,qa)): raise ValueError('Resource dependencies changed')
    if not (run['contract_sha256']==qa['contract_sha256']==contract_digest(f,rec) and run['inputs_before']==run['inputs_after']==qa['inputs']==inputs and run['outputs']==qa['outputs']==outputs):
        raise ValueError('Source/data/selection/style/output changed after run or review')
    if run['returncode'] or run['failures'] or run['runtime']!=runtime or run['figure_id']!=f['figure_id'] or sha(safe(root,run['log_path']))!=run['log_sha256']:
        raise ValueError('Real successful execution with current log required')
    if str(safe(root,f['script'])) not in run['command'] or not 0<run['started_at_ns']<=run['finished_at_ns']:
        raise ValueError('Execution command/timestamps invalid')
    if set(run['output_mtime_ns'])!=set(outputs) or any(safe(root,p).stat().st_mtime_ns!=run['output_mtime_ns'][p] or run['output_mtime_ns'][p]<run['started_at_ns'] for p in outputs):
        raise ValueError('Outputs must be written by the recorded run')
    if artifacts(root,f,rec) or qa['technical_failures']: raise ValueError('Technical QA failed')
    if qa['status']!='PASS': raise ValueError('Actual visual QA not passed')
    if f['status']!='qa_pass' or rec['status']!='qa_pass': raise ValueError('Figure and provider QA not passed')
    if set(qa['dimensions'])!={'scientific_validity','reference_fidelity','print_readability'} or any(v['status']!='PASS' or len(v['observation'].strip())<12 for v in qa['dimensions'].values()):
        raise ValueError('Three separate actual review dimensions required')
    expected=expected_views(root,f,rec,runtime)
    if len(qa['views'])!=len(expected) or {v['kind'] for v in qa['views']}!=set(expected): raise ValueError('Missing actual review views')
    for v in qa['views']:
        path=safe(root,v['path'])
        with Image.open(path) as actual:
            im=expected[v['kind']]
            equal=actual.size==im.size and actual.convert('RGB').tobytes()==im.convert('RGB').tobytes()
        if not equal or sha(path)!=v['sha256'] or not review_ok(v): raise ValueError('Actual current image review missing: '+v['kind'])


def execute(root,plan_path,figure_id,runtime,allow_demo=False,timeout=600):
    from candidate_figures import audit_figure
    from workspace_resources import dependencies
    gate=audit_figure(root,plan_path,figure_id,'plan',runtime,allow_demo)
    if gate['status']!='PASS': raise ValueError('Plan gate failed: '+json.dumps(gate['failures'],ensure_ascii=False))
    f=next(f for f in figures(load(plan_path)) if f['figure_id']==figure_id)
    rec=next(r for r in load(sidecar(plan_path))['figures'] if r['figure_id']==figure_id)
    before=input_files(root,f,rec,runtime); job=safe(root,rec['job_dir']); rp=safe(root,rec['run_record_path']); log=rp.with_suffix('.log')
    if rp.exists() or log.exists(): raise ValueError('Preserve runs; choose a fresh run_record_path')
    output_paths=set(f['outputs'].values())|{f['statistics_report']}
    if set(before)&output_paths or any(safe(root,p) in {rp,log} for p in before.keys()|output_paths): raise ValueError('Input/output/log collision')
    from visual_routes import academic_panels,routed_panels,media_sidecar
    mixed=[]
    if academic_panels(f):
        ar=next(r for r in load(Path(plan_path).with_suffix('.assets.json'))['figures'] if r['figure_id']==figure_id)
        mixed.append(safe(root,ar['run_record_path']))
    if routed_panels(f):
        from audit_media_figures import current_files
        mr=next(r for r in load(media_sidecar(plan_path))['figures'] if r['figure_id']==figure_id)
        mixed.append(safe(root,mr['run_record_path']))
        media_before=current_files(root,f,mr,runtime)
        if any(before.get(p)!=h for p,h in media_before.items()):
            raise ValueError('Declare all mixed-media inputs as ModelViz dependencies before execution')
    occupied={safe(root,p) for p in before.keys()|output_paths}|{rp,log}
    if len(set(mixed))!=len(mixed) or any(p.exists() or p in occupied or not p.is_relative_to(job) for p in mixed):
        raise ValueError('Mixed-provider run paths must be fresh, distinct and inside this Figure job')
    skill=discover(template_root(root,runtime),runtime,'modelviz-skill',rec['skill_root'])
    write_json(rp.with_suffix('.dependencies.json'),validate_host(root,f,rec,skill))
    payload=rp.with_suffix('.payload.json'); write_json(payload,{'job_dir':str(job),'script':str(safe(root,f['script'])),
          'data_path':str(safe(root,modelviz_panels(f)[0]['result_file'])),'output_dir':str(safe(root,f['outputs']['preview']).parent),
          'protected_inputs':[str(safe(root,p)) for p in before if not p.startswith(('.agents/','.claude/','华为杯_论文规范模板/'))]})
    command=[sys.executable,'-B',str(Path(__file__).resolve()),'--plot-child',str(payload),str(safe(root,f['script']))]
    env=dict(os.environ,PYTHONUTF8='1',MPLBACKEND='Agg',PYTHONDONTWRITEBYTECODE='1')
    started=time.time_ns(); start_iso=datetime.now(timezone.utc).isoformat()
    try:
        proc=subprocess.run(command,cwd=job,env=env,capture_output=True,text=True,encoding='utf8',errors='replace',timeout=timeout,shell=False)
        code,text=proc.returncode,proc.stdout+'\n'+proc.stderr
    except subprocess.TimeoutExpired as exc: code,text=124,str(exc)
    log.write_text(json.dumps(command,ensure_ascii=False)+'\n'+text,encoding='utf8')
    after=input_files(root,f,rec,runtime); outputs={p:sha(safe(root,p)) for p in output_paths if safe(root,p).is_file()}
    mtimes={p:safe(root,p).stat().st_mtime_ns for p in outputs}; failures=[]
    if code: failures.append('script_failed')
    if before!=after: failures.append('input_changed')
    if set(outputs)!=output_paths or any(v<started for v in mtimes.values()): failures.append('missing_or_old_output')
    if re.search(r'Glyph .* missing|not compatible with tight_layout|Tight layout not applied|No artists with labels',text,re.I): failures.append('font_or_layout_warning')
    value={'schema_version':'1.0','runtime':runtime,'figure_id':figure_id,'resource_dependencies':dependencies(root,runtime,'modelviz'),
        'contract_sha256':contract_digest(f,rec),'command':command,'cwd':str(job),'started_at_ns':started,'finished_at_ns':time.time_ns(),
        'started_at':start_iso,'finished_at':datetime.now(timezone.utc).isoformat(),'returncode':code,'inputs_before':before,'inputs_after':after,
        'outputs':outputs,'output_mtime_ns':mtimes,'log_path':log.relative_to(root).as_posix(),'log_sha256':sha(log),
        'failures':failures,'status':'FAIL' if failures else 'EXECUTED_REVIEW_REQUIRED'}
    write_json(rp,value)
    # One real process supplies whole-Figure evidence for every participating gate.
    from visual_routes import academic_panels,routed_panels,media_sidecar
    if academic_panels(f):
        refs=load(Path(plan_path).with_suffix('.assets.json')); ar=next(r for r in refs['figures'] if r['figure_id']==figure_id)
        dest=safe(root,ar['run_record_path'])
        if dest.exists(): raise ValueError('Preserve academic mixed-run history')
        academic_inputs={f['script']}|{p['result_file'] for p in f['panels']}
        write_json(dest,{**value,'schema_version':'2.0','resource_dependencies':dependencies(root,runtime,'academic'),
            'files':{**{p:after[p] for p in academic_inputs},**outputs},'input_sha256_before':{p:before[p] for p in academic_inputs}})
    if routed_panels(f):
        from audit_media_figures import current_files
        mr=next(r for r in load(media_sidecar(plan_path))['figures'] if r['figure_id']==figure_id)
        dest=safe(root,mr['run_record_path'])
        if dest.exists(): raise ValueError('Preserve media mixed-run history')
        media_inputs=current_files(root,f,mr,runtime)
        if media_inputs!=media_before: raise ValueError('Mixed-media inputs changed during execution')
        write_json(dest,{**value,'resource_dependencies':dependencies(root,runtime,'media'),
            'contract_sha256':contract_digest(f,mr),'inputs_before':media_inputs,'inputs_after':media_inputs})
    return value


def plot_child(payload):
    """Restricted plotting child: common Python writes confined to this job, inputs read-only."""
    import runpy
    data=load(payload); job=Path(data['job_dir']).resolve(); script=safe(job,data['script'])
    def guard(event,args):
        writes=event=='open' and (any(c in (args[1] or '') for c in 'wax+') or args[2] & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
        if writes or event in {'os.remove','os.rmdir','os.mkdir','os.rename','os.chmod','os.utime'}:
            targets=args[:2] if event=='os.rename' else args[:1]
            for raw in targets:
                if isinstance(raw,(str,bytes,Path)):
                    path=safe(job,str(Path.cwd()/os.fsdecode(raw)))
                    if path==script or str(path)==data['data_path'] or str(path) in data.get('protected_inputs',[]): raise ValueError('Plot input is read-only')
        if event in {'os.symlink','os.link'}: raise ValueError('Plotting cannot create links')
    for key in ('MPLCONFIGDIR','TEMP','TMP','XDG_CACHE_HOME'):
        dest=job/'cache'/key; dest.mkdir(parents=True,exist_ok=True); os.environ[key]=str(dest)
    sys.addaudithook(guard); os.chdir(job)
    os.environ.update(DATA_PATH=data['data_path'],OUTPUT_DIR=data['output_dir'])
    sys.argv=[str(script),data['data_path'],data['output_dir']]
    runpy.run_path(str(script),run_name='__main__')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['prepare','run','qa','audit']); p.add_argument('--project-root',type=Path,default=Path('.'))
    p.add_argument('--runtime',choices=['codex','claude'],required=True); p.add_argument('--plan',required=True)
    p.add_argument('--figure-id'); p.add_argument('--purpose',choices=['production','demo'],default='production')
    p.add_argument('--allow-demo',action='store_true'); p.add_argument('--stage',choices=['plan','render','paper'],default='plan')
    p.add_argument('--main-tex'); p.add_argument('--report'); a=p.parse_args(); root=a.project_root.resolve()
    try:
        plan=safe(root,a.plan)
        if a.action=='prepare': result=prepare(root,plan,a.runtime,a.purpose)
        elif a.action=='run': result=execute(root,plan,a.figure_id,a.runtime,a.allow_demo)
        elif a.action=='qa': result=prepare_qa(root,plan,a.figure_id,a.runtime)
        else: result=audit_modelviz(plan,a.stage,root,a.runtime,a.allow_demo,a.main_tex,[a.figure_id] if a.figure_id else None)
        if a.report: write_json(safe(root,a.report),result)
        print(json.dumps(result,ensure_ascii=False)); return bool(result.get('failures'))
    except Exception as exc:
        print(json.dumps({'status':'FAIL','error':str(exc)},ensure_ascii=False)); return 1


if __name__=='__main__':
    if sys.argv[1:2]==['--plot-child']:
        plot_child(sys.argv[2])
    else:
        from workspace_cli import require_cli_mode
        require_cli_mode(__file__)
        raise SystemExit(main())
