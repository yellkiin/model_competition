#!/usr/bin/env python3
"""Fail-closed asset provenance gate, supplementary to audit_visual_plan (no visual judgment automation)."""
from __future__ import annotations

# Shared execution is explicit; direct legacy/maintenance CLIs must declare mode.
if __name__ == "__main__":
    import sys as _workflow_sys
    _workflow_sys.dont_write_bytecode = True
    from workspace_cli import require_cli_mode
    require_cli_mode(__file__)

import argparse
import json
import re
from pathlib import Path
from build_academic_figure_asset_index import build_index, safe, sha, sync_report, write_json, runtime_skill, OUTPUT_EXT
from prepare_academic_figure_review import plan_figures, sidecar_path, search_catalog, STYLE_KEYS, select_figures, figure_contract_digest
from visual_routes import academic_figures, academic_panels, routing_errors
from workspace_context import reference_path, resource_path

ROLES={'mechanism','main_result','validation','error','sensitivity','robustness','scenario'}
MODES={'native_run','visual_adapt','cross_type_inherit'}


def meaningful(value):
    return isinstance(value,str) and bool(value.strip()) and value.strip().lower() not in {'unknown','needs_review','pending','todo','待填写','已参考'}


def schema_errors(value, schema, definitions=None, location='$'):
    """Validate the JSON Schema keywords used by the bundled local schemas, without network/dependencies."""
    definitions = schema if definitions is None else definitions
    if '$ref' in schema:
        target=definitions
        for part in schema['$ref'].removeprefix('#/').split('/'): target=target[part]
        return schema_errors(value,target,definitions,location)
    errors=[]
    for branch in schema.get('allOf', []):
        errors.extend(schema_errors(value, branch, definitions, location))
    if 'anyOf' in schema and not any(not schema_errors(value, branch, definitions, location) for branch in schema['anyOf']):
        errors.append(location+':anyOf')
    if 'if' in schema:
        branch = 'else' if schema_errors(value, schema['if'], definitions, location) else 'then'
        errors.extend(schema_errors(value, schema.get(branch, {}), definitions, location))
    types={'object':dict,'array':list,'string':str,'boolean':bool,'null':type(None),'integer':int,'number':(int,float)}
    expected=schema.get('type'); kinds=expected if isinstance(expected,list) else [expected] if expected else []
    if kinds and not any(isinstance(value,types[k]) and not (k in {'number','integer'} and isinstance(value,bool)) for k in kinds):
        return [location+':type']
    if 'const' in schema and value!=schema['const']:errors.append(location+':const')
    if 'enum' in schema and value not in schema['enum']:errors.append(location+':enum')
    if isinstance(value,str):
        if len(value)<schema.get('minLength',0):errors.append(location+':minLength')
        if 'pattern' in schema and re.search(schema['pattern'],value) is None:errors.append(location+':pattern')
    if isinstance(value,list):
        if len(value)<schema.get('minItems',0) or len(value)>schema.get('maxItems',float('inf')):errors.append(location+':items_count')
        if schema.get('uniqueItems') and len({json.dumps(x,sort_keys=True) for x in value})!=len(value):errors.append(location+':unique')
        if 'items' in schema:
            for i,x in enumerate(value):errors.extend(schema_errors(x,schema['items'],definitions,f'{location}[{i}]'))
    if isinstance(value,dict):
        errors.extend(location+':missing:'+k for k in schema.get('required',[]) if k not in value)
        if len(value)<schema.get('minProperties',0):errors.append(location+':minProperties')
        props=schema.get('properties',{})
        for k,x in value.items():
            if k in props:errors.extend(schema_errors(x,props[k],definitions,location+'.'+k))
            elif schema.get('additionalProperties') is False:errors.append(location+':extra:'+k)
            elif isinstance(schema.get('additionalProperties'),dict):errors.extend(schema_errors(x,schema['additionalProperties'],definitions,location+'.'+k))
    return errors


def audit_gallery(root, index, review_path, add):
    """Check full overview coverage; attestations are not proof of cognition."""
    def load(raw):return json.loads(safe(root,raw).read_text(encoding='utf-8-sig'))
    review=load(review_path);manifest=load(review['contact_manifest'])
    add('gallery_version',review.get('schema_version')=='2.0' and manifest.get('schema_version')=='2.0')
    add('gallery_runtime',review.get('runtime')==index['runtime']==manifest.get('runtime') and manifest.get('skill_root')==index['skill_root'])
    add('gallery_current',review.get('scan_digest')==manifest.get('scan_digest')==index['scan_digest'] and review.get('contact_manifest_sha256')==sha(safe(root,review['contact_manifest'])))
    add('gallery_no_unviewable_assets',not index['inspection_errors'] and not manifest.get('errors'))
    visual={e['path']:e for e in index['inventory'] if Path(e['path']).suffix.lower() in OUTPUT_EXT}
    expected={f'{raw}#page={p+1}' for raw,e in visual.items() for p in range(e.get('pages',0))}
    units=manifest.get('units',[]);unit_ids=[u['unit_id'] for u in units]
    add('gallery_all_pages_frames',len(unit_ids)==len(set(unit_ids)) and set(unit_ids)==expected and manifest.get('expected_units')==len(expected))
    sheets={p['path']:p for p in manifest['pages']};receipts=review.get('pages',[])
    add('gallery_all_sheets_reviewed',len(receipts)==len(sheets) and {x['path'] for x in receipts}==set(sheets))
    mapped=[uid for p in sheets.values() for uid in p['unit_ids']]
    add('gallery_sheet_mapping_exact',len(mapped)==len(set(mapped)) and set(mapped)==expected)
    for row in receipts:
        raw=row['path'];p=sheets[raw]
        add('gallery_view:'+raw,row.get('reviewed') is True and meaningful(row.get('tool_ref')) and meaningful(row.get('observation')) and row.get('sha256')==p['sha256']==sha(safe(root,raw)))
    for u in units:
        sheet=sheets[u['sheet_path']];cell=u.get('sheet_cell',0)
        add('gallery_unit:'+u['unit_id'],u['asset_sha256']==visual[u['asset_path']]['sha256'] and u['preview_sha256']==sha(safe(root,u['preview_path'])) and 1<=cell<=len(sheet['unit_ids']) and sheet['unit_ids'][cell-1]==u['unit_id'] and isinstance(u.get('sheet_bbox'),list) and len(u['sheet_bbox'])==4)
    observations=review.get('asset_observations',[])
    add('gallery_asset_observations_exact',len(observations)==len(visual) and {x['path'] for x in observations}==set(visual))
    for row in observations:
        add('gallery_observation:'+row['path'],row['sha256']==visual[row['path']]['sha256'] and all(meaningful(row.get(k)) for k in ['data_fit','visual_features','limitations']))
    if review.get('detail_review_path'):
        detail_path=safe(root,review['detail_review_path'])
        add('gallery_detail_manifest_hash',review.get('detail_review_sha256')==sha(detail_path))
        for row in load(review['detail_review_path']):
            add('gallery_detail:'+row['preview_path'],row.get('reviewed') is True and meaningful(row.get('tool_ref')) and meaningful(row.get('observation')) and row['source_sha256']==visual[row['asset_path']]['sha256'] and row['preview_sha256']==sha(safe(root,row['preview_path'])))
    return review


def audit_assets(plan_path, stage, root, references=None, allow_demo=False, runtime=None, main_tex=None, figure_ids=None):
    root=Path(root).resolve(); checks=[]; failures=[]
    def add(code,ok,**details):
        row={'code':code,'ok':bool(ok),**details};checks.append(row)
        if not ok: failures.append(row)
    def present(raw):
        path=safe(root,raw)
        if not path.is_file() or not path.stat().st_size: raise ValueError(f'Missing/empty file: {raw}')
        return path
    def reference(raw):
        path = reference_path(root, raw, runtime or refs.get('runtime'))
        from filesystem_paths import native_path
        path = native_path(path)
        if not path.is_file() or not path.stat().st_size:
            raise ValueError('Missing/empty reference file: ' + str(raw))
        return path
    def load(raw):return json.loads(present(raw).read_text(encoding='utf-8-sig'))
    try:
        plan_path=Path(plan_path).resolve(); plan=load(str(plan_path)); figures=academic_figures(plan)
        for f in plan_figures(plan):
            if figure_ids is None or f['figure_id'] in figure_ids:
                add(f['figure_id']+':routing_valid',not routing_errors(f),errors=routing_errors(f))
        if figure_ids:
            available={f['figure_id'] for f in plan_figures(plan)}
            add('selected_ids_exist',set(figure_ids)<=available)
            figures=[f for f in figures if f['figure_id'] in figure_ids]
        if figure_ids and stage == 'paper':
            raise ValueError('Incremental selection cannot grant a paper-stage pass')
        if not figures:
            add('no_ordinary_figures',True)
        else:
            refs=load(str(references or sidecar_path(plan_path)))
            if figure_ids:
                plan, refs = select_figures(plan, refs, figure_ids)
                figures = academic_figures(plan)
            for name,value in [('视觉计划.schema.json',plan),('academic_figure_references.schema.json',refs)]:
                spec=json.loads((Path(__file__).resolve().parent.parent/name).read_text(encoding='utf-8-sig'))
                if figure_ids and name == '视觉计划.schema.json':
                    errors = [error for f in figures for error in schema_errors(f, spec['$defs']['figure'], spec)]
                else:
                    errors=schema_errors(value,spec)
                add('schema:'+name,not errors,errors=errors)
            index=load(refs['index_path']);current=build_index(root,refs['skill_root'])
            resolved,skill=runtime_skill(runtime or refs.get('runtime'),refs['skill_root'])
            add('runtime_matches',resolved==refs.get('runtime')==index.get('runtime') and skill==index['skill_root'])
            add('index_fresh_and_derived',index==current)
            add('scan_fingerprint_current',refs.get('scan_digest')==current['scan_digest'])
            add('schema_supported',refs.get('schema_version')=='2.0')
            add('gallery_review_hash',refs.get('gallery_review_sha256')==sha(present(refs['gallery_review_path'])))
            audit_gallery(root,current,refs['gallery_review_path'],add)
            add('review_session_declared',meaningful(refs.get('review_session_id')))
            add('references_target_plan',safe(root,refs['plan_path'])==plan_path)
            purpose=refs.get('purpose'); add('purpose_valid',purpose in {'demo','production'})
            add('demo_not_in_production',purpose=='production' or (allow_demo and stage!='paper'))
            if purpose=='demo':
                isolated=(root/'求解/验收输出/academic_figure_integration').resolve()
                add('demo_plan_isolated',plan_path.is_relative_to(isolated))
                add('demo_outputs_isolated',all(safe(root,f['script']).is_relative_to(isolated) and all(safe(root,v).is_relative_to(isolated) for v in f['outputs'].values()) for f in figures))
            mirror=sync_report(root);add('skill_mirrors_identical',mirror['status']=='PASS',**{k:v for k,v in mirror.items() if k!='status'})
            inventory={x['path']:x for x in current['inventory']}
            atlas={x['path'] for x in current['atlas']};families={f['figure_type']:f for f in current['families']}
            add('directory_map_covers_production',all(f['keywords'] for f in current['families'] if f['production_scripts']))
            rfigs=refs.get('figures',[]);ids=[f.get('figure_id') for f in rfigs]
            add('reference_figure_ids_exact',len(ids)==len(set(ids)) and set(ids)=={f['figure_id'] for f in figures})
            record_by_id={f.get('figure_id'):f for f in rfigs}
            for f in figures:
                fid=f['figure_id']; rec=record_by_id.get(fid,{})
                try:
                    backend=rec.get('backend');add(fid+':backend',backend=='academic-figure-skill')
                    for key in ['scientific_question','core_claim','backend_reason','intended_layout']:
                        add(fid+':'+key,meaningful(rec.get(key)))
                    add(fid+':question_matches',rec.get('scientific_question')==f.get('scientific_question'))
                    add(fid+':layout_matches',rec.get('intended_layout')==f.get('layout'))
                    add(fid+':evidence_role',rec.get('evidence_role') in ROLES)
                    contract=rec.get('figure_contract',{})
                    add(fid+':contract',all(meaningful(contract.get(k)) for k in ['necessity','evidence_chain','review_risks']))
                    linked={'script':f['script'],'final_png_path':f['outputs']['preview'],
                            'statistics_report_path':f['statistics_report'],'visual_qa_path':f['qa_report']}
                    vector=f['outputs']['vector'];linked['final_pdf_path' if vector.endswith('.pdf') else 'final_svg_path']=vector
                    for key,value in linked.items():
                        add(fid+':path_matches:'+key,rec.get(key)==value)
                        safe(root,value)
                    geometry=rec.get('paper_geometry',{})
                    text_width=geometry.get('text_width_mm',0);fraction=geometry.get('width_fraction',0)
                    add(fid+':paper_geometry',isinstance(text_width,(int,float)) and isinstance(fraction,(int,float)) and text_width>0 and 0<fraction<=1 and abs(rec.get('target_width_mm',0)-text_width*fraction)<0.5 and meaningful(geometry.get('basis')) and geometry.get('source_sha256')==sha(reference(geometry['source_tex'])))
                    panels=rec.get('panel_plan',[]); pids=[p.get('panel_id') for p in panels]
                    add(fid+':panels_exact',len(pids)==len(set(pids)) and set(pids)=={p['panel_id'] for p in academic_panels(f)})
                    rpanels={p.get('panel_id'):p for p in panels}
                    for p in academic_panels(f):
                        tag=fid+':'+p['panel_id'];rp=rpanels.get(p['panel_id'],{})
                        try:
                            family=families[rp['asset_family']]
                            add(tag+':family_has_source',bool(family['production_scripts']))
                            add(tag+':atlas_exists',rp['atlas_reference'] in atlas)
                            add(tag+':source_in_family',rp['production_asset'] in {x['path'] for x in family['production_scripts']})
                            add(tag+':source_example',rp.get('source_example_path') in {x['path'] for x in family['outputs']} and meaningful(rp.get('source_locator')))
                            add(tag+':mode_valid',rp['adaptation_mode'] in MODES and rp['adaptation_mode']==p['asset_mode'])
                            if backend=='academic-figure-skill':
                                add(tag+':directory_matches',resource_path(root,p['asset_directory'],resolved)==resource_path(root,family['directory'],resolved))
                            add(tag+':panel_question',rp.get('scientific_question')==p['question'])
                            ds=rp.get('data_schema',{})
                            add(tag+':data_schema',ds.get('fields')==p['fields'] and ds.get('units')==p['units'] and meaningful(ds.get('shape')) and isinstance(ds.get('groups'),list))
                            add(tag+':inheritance',isinstance(rp.get('style_parameters_inherited'),dict) and bool(rp['style_parameters_inherited']) and all(meaningful(v) for v in rp['style_parameters_inherited'].values()))
                            add(tag+':adaptation_reason',isinstance(rp.get('changed_parameters'),dict) and meaningful(rp.get('reason_for_change')))
                            styles=rp.get('style_contract',{})
                            add(tag+':style_contract_coverage',set(styles)==set(STYLE_KEYS))
                            for key,row in styles.items():
                                add(tag+':style:'+key,all(meaningful(row.get(k)) for k in ['reference_value','final_value','source_path','source_locator','reason']) and row.get('basis') in {'source','image_estimate','not_applicable'} and row.get('source_path') in inventory)
                            add(tag+':selection_reviewed',rp.get('selection_status')=='reviewed')
                            if rp['adaptation_mode']=='native_run': add(tag+':native_semantics_match',rp.get('semantic_match') is True)
                            candidates=rp.get('candidate_families',[]);candidate_atlas=rp.get('candidate_atlas',[])
                            search=rp.get('candidate_search',{})
                            add(tag+':full_catalog_search',meaningful(search.get('query')) and search.get('scan_digest')==current['scan_digest'] and search.get('results')==search_catalog(current,search.get('query','')) and search.get('reviewed') is True and meaningful(search.get('selection_reason')))
                            comparisons=rp.get('candidate_comparison',[])
                            add(tag+':candidate_comparison',len(comparisons)==len(candidates) and {x.get('family') for x in comparisons}==set(candidates) and all(all(meaningful(x.get(k)) for k in ['fit','conflict','decision_reason']) and x.get('decision') in {'selected','rejected'} for x in comparisons) and [x.get('family') for x in comparisons if x.get('decision')=='selected']==[rp['asset_family']] and (len(candidates)>1 or meaningful(search.get('single_candidate_reason'))))
                            add(tag+':candidate_list',bool(candidates) and rp['asset_family'] in candidates and rp['atlas_reference'] in candidate_atlas and set(candidate_atlas)<=atlas)
                            expected=set(candidate_atlas)
                            for fam in candidates:
                                expected.update(x['path'] for x in families[fam]['production_scripts']+families[fam]['outputs'])
                            reviews=rp.get('candidate_review',[]);paths=[x.get('path') for x in reviews]
                            add(tag+':candidate_review_coverage',len(paths)==len(set(paths)) and set(paths)==expected)
                            for view in reviews:
                                raw=view['path']; file=reference(raw)
                                add(tag+':review_hash:'+raw,view.get('sha256')==sha(file) and raw in inventory)
                                ext=file.suffix.lower();allowed={'source_read'} if ext in {'.py','.r'} else {'image_view','contact_sheet_view','pdf_render_view','svg_render_view'}
                                add(tag+':view_attestation:'+raw,view.get('reviewed') is True and view.get('method') in allowed and meaningful(view.get('tool_ref')) and meaningful(view.get('observation')))
                                if inventory[raw].get('pages',1)>1:
                                    add(tag+':candidate_all_pages:'+raw,view.get('pages_reviewed')==list(range(1,inventory[raw]['pages']+1)))
                                if view.get('method') in {'contact_sheet_view','pdf_render_view','svg_render_view'}:
                                    preview=present(view['preview_path'])
                                    add(tag+':review_preview_hash:'+raw,view.get('preview_sha256')==sha(preview))
                            # Final references must be inspected in detail, not only tiny overview cells.
                            detailed={x['path'] for x in reviews if x.get('method') in {'image_view','pdf_render_view','svg_render_view'}}
                            add(tag+':selected_references_detail',rp['atlas_reference'] in detailed and rp['source_example_path'] in detailed)
                            if stage in {'render','paper'}:
                                present(p['result_file'])
                                profile=load(rp['data_profile_path'])
                                add(tag+':real_data_revalidated',rp.get('data_state')=='verified' and profile.get('source_path')==p['result_file'] and profile.get('sha256')==sha(present(p['result_file'])) and set(p['fields'])<=set(profile.get('fields',[])) and profile.get('valid') is True and meaningful(profile.get('validation_method')))
                                if purpose=='production':
                                    add(tag+':result_not_skill_demo', '/assets/' not in p['result_file'] and 'DEMO' not in p['result_file'].upper())
                        except (KeyError,ValueError,TypeError,OSError) as exc: add(tag+':record_invalid',False,error=str(exc))
                    if stage in {'render','paper'}:
                        script=present(f['script']);png=present(f['outputs']['preview']);vp=present(vector)
                        add(fid+':script_is_working_copy','/assets/figures/' not in script.as_posix())
                        add(fid+':not_reference_png',sha(png) not in {x['sha256'] for x in current['inventory'] if x['path'] in atlas or x['path'].endswith('.png')})
                        stats=load(f['statistics_report']);qa=load(f['qa_report']);run=load(rec['run_record_path'])
                        from workspace_resources import evidence_current
                        add(fid+':resource_dependencies_current',evidence_current(root,resolved,'academic',run)
                            and evidence_current(root,resolved,'academic',qa))
                        add(fid+':statistics_nonempty',isinstance(stats,dict) and bool(stats))
                        if purpose=='production':add(fid+':statistics_not_demo','DEMO' not in json.dumps(stats,ensure_ascii=False).upper())
                        if 'contract_sha256' in qa:
                            add(fid+':qa_contract_current',qa['contract_sha256']==figure_contract_digest(f,rec))
                        add(fid+':automated_checks',isinstance(qa.get('automated_checks'),list) and bool(qa['automated_checks']) and all(x.get('status')=='PASS' for x in qa['automated_checks']))
                        add(fid+':qa_status',qa.get('status')=='PASS' and rec.get('status')=='qa_pass' and f.get('status')=='qa_pass')
                        for key,raw in {'script':f['script'],'png':f['outputs']['preview'],'vector':vector}.items():
                            add(fid+':qa_current:'+key,qa.get('artifact_sha256',{}).get(key)==sha(present(raw)))
                        visual=qa.get('visual_review',{})
                        add(fid+':final_visual_review',visual.get('reviewed') is True and meaningful(visual.get('tool_ref')) and meaningful(visual.get('observation')) and visual.get('png_sha256')==sha(png))
                        for key in ['pdf_render','grayscale']:
                            preview=present(visual[key+'_path'])
                            add(fid+':final_view_derivative:'+key,visual.get(key+'_sha256')==sha(preview))
                        comparison=qa.get('reference_comparison',{})
                        add(fid+':comparison_review',comparison.get('reviewed') is True and meaningful(comparison.get('tool_ref')) and meaningful(comparison.get('observation')) and comparison.get('sha256')==sha(present(comparison['path'])) and comparison.get('final_png_sha256')==sha(png))
                        reference_paths={p['atlas_reference'] for p in panels}|{p['source_example_path'] for p in panels}
                        add(fid+':comparison_inputs',set(comparison.get('reference_hashes',{}))==reference_paths and all(comparison['reference_hashes'][raw]==sha(reference(raw)) for raw in reference_paths))
                        dimensions=qa.get('review_dimensions',{})
                        add(fid+':three_review_dimensions',set(dimensions)=={'scientific_validity','reference_fidelity','print_readability'} and all(x.get('status')=='PASS' and meaningful(x.get('observation')) for x in dimensions.values()))
                        command=run.get('command',[])
                        from datetime import datetime
                        time_ok=False
                        try:
                            begin=datetime.fromisoformat(run['started_at']); end=datetime.fromisoformat(run['finished_at'])
                            time_ok=begin.tzinfo is not None and end.tzinfo is not None and end>=begin
                        except (KeyError,ValueError,TypeError): pass
                        command_matches=False
                        if isinstance(command,list) and command and all(isinstance(x,str) for x in command):
                            for token in command:
                                if Path(token).suffix.lower() in {'.py','.r'}:
                                    try: command_matches=command_matches or safe(root,token)==script
                                    except (ValueError,OSError): pass
                        add(fid+':execution_success',run.get('returncode')==0 and time_ok and command_matches)
                        add(fid+':execution_runtime',run.get('runtime')==resolved and run.get('figure_id')==fid)
                        present(run['log_path'])
                        add(fid+':execution_log_hash',run.get('log_sha256')==sha(present(run['log_path'])))
                        required={f['script'],vector,f['outputs']['preview'],f['statistics_report']}|{p['result_file'] for p in f['panels']}
                        add(fid+':run_inputs_outputs_current',all(run.get('files',{}).get(raw)==sha(present(raw)) for raw in required))
                        produced={vector,f['outputs']['preview'],f['statistics_report']}
                        started_ns=run.get('started_at_ns',0)
                        add(fid+':outputs_written_by_run',isinstance(started_ns,int) and started_ns>0 and set(run.get('output_mtime_ns',{}))==produced and all(run['output_mtime_ns'][raw]==present(raw).stat().st_mtime_ns and run['output_mtime_ns'][raw]>=started_ns for raw in produced))
                        input_paths={f['script']}|{p['result_file'] for p in f['panels']}
                        add(fid+':plot_inputs_unchanged',set(run.get('input_sha256_before',{}))==input_paths and all(run['input_sha256_before'][raw]==sha(present(raw)) for raw in input_paths))
                        from PIL import Image
                        with Image.open(png) as im:
                            dpi=im.info.get('dpi',(0,0));add(fid+':png_300dpi',min(dpi)>=299 and im.width>100 and im.height>100);im.verify()
                        if vp.suffix.lower()=='.pdf':
                            try:
                                import pymupdf as fitz
                            except ImportError:
                                import fitz
                            with fitz.open(vp) as doc:
                                target=rec.get('target_width_mm')
                                add(fid+':pdf_target_width',isinstance(target,(int,float)) and not isinstance(target,bool) and target>0 and all(abs(page.rect.width/72*25.4-target)<=3 for page in doc))
                                add(fid+':pdf_readable_vector',len(doc)>0 and any(page.get_drawings() for page in doc), message='Heuristic: vector drawing primitives present; not a full vector purity proof')
                        elif vp.suffix.lower()=='.svg':
                            import xml.etree.ElementTree as ET
                            svg=ET.parse(vp);add(fid+':svg_has_vector',any(e.tag.rsplit('}',1)[-1] in {'path','line','rect','circle','polyline','polygon'} for e in svg.iter()))
                        else:add(fid+':vector_extension',False)
                except (KeyError,ValueError,TypeError,OSError,ImportError) as exc:add(fid+':record_invalid',False,error=f'{type(exc).__name__}: {exc}')
            if stage=='paper':
                from collect_academic_paper_review import verify_evidence
                paper_review=load(refs['paper_review_path'])
                add('paper_main_provided',main_tex is not None)
                if main_tex is not None:
                    from visual_routes import paper_specs
                    specs=paper_specs(plan_path)
                    paper_failures=verify_evidence(root,paper_review,main_tex,resolved,specs)
                    add('paper_compiled_evidence',not paper_failures,failures=paper_failures)
    except Exception as exc:add('asset_gate_input_error',False,error=f'{type(exc).__name__}: {exc}')
    return {'status':'FAIL' if failures else 'PASS','stage':stage,'checks':checks,'failures':failures,
      'assurance':'Hashes validate inventory/provenance and recorded attestations, NOT whether an agent truly saw/understood an image. Manual visual review remains mandatory.'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--project-root',type=Path,default=Path('.'))
    p.add_argument('--plan',type=Path,required=True);p.add_argument('--references',type=Path)
    p.add_argument('--runtime',choices=['codex','claude'],required=True);p.add_argument('--main-tex',type=Path)
    p.add_argument('--stage',choices=['plan','render','paper'],default='plan');p.add_argument('--allow-demo',action='store_true')
    p.add_argument('--report',type=Path,required=True);a=p.parse_args();root=a.project_root.resolve()
    result=audit_assets(safe(root,str(a.plan)),a.stage,root,safe(root,str(a.references)) if a.references else None,a.allow_demo,a.runtime,a.main_tex)
    write_json(safe(root,str(a.report)),result);print(json.dumps({'status':result['status'],'checks':len(result['checks']),'failures':result['failures']},ensure_ascii=False,indent=2));raise SystemExit(0 if result['status']=='PASS' else 1)

if __name__=='__main__':main()
