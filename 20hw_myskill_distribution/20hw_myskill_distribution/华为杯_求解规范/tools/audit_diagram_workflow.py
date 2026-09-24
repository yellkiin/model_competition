#!/usr/bin/env python3
"""Fail-closed diagram/overview gate. Records are not proof of visual cognition."""
from __future__ import annotations

# Shared execution is explicit; direct legacy/maintenance CLIs must declare mode.
if __name__ == "__main__":
    import sys as _workflow_sys
    _workflow_sys.dont_write_bytecode = True
    from workspace_cli import require_cli_mode
    require_cli_mode(__file__)

import argparse
import hashlib
import json
import re
from pathlib import Path

KINDS={'algorithm','physics','comprehensive','flowchart'}
GRAPHICAL={'object','geometry','algorithm','result'}
SIDES={'codex':'.agents','claude':'.claude'}
SKILLS={'algorithm':'algorithm-mechanism-diagram','physics':'engineering-physics-mechanism-diagram',
        'comprehensive':'comprehensive-graphic-text-flowchart'}
from overview_content import RELATION_TYPES, audit_content, audit_result_source

def load(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def sidecar(plan): return Path(plan).with_suffix('.diagrams.json')
def native_bitmap_review(root, pdf, item, rect, reviews):
    """Match embedded pixels and physical size to an explicitly reviewed native source."""
    import pymupdf as fitz
    embedded = fitz.Pixmap(pdf, item[0])
    for review in reviews:
        source = path(root, review['path'])
        if not (source.is_file() and sha(source) == review.get('sha256') and
                review.get('reviewed') is True and meaningful(review.get('observation')) and
                bool(review.get('tool_ref')) and review.get('native_pixels') == [item[2], item[3]] and
                abs(review.get('width_mm', 0) - rect.width * 25.4 / 72) < .1 and
                abs(review.get('height_mm', 0) - rect.height * 25.4 / 72) < .1):
            continue
        original = fitz.Pixmap(source)
        if original.n == embedded.n and original.samples == embedded.samples:
            return True
    return False


def path(root,raw):
    if not isinstance(raw,str) or not raw.strip(): raise ValueError('Empty path')
    from workspace_context import bounded
    return bounded(root,raw)
def meaningful(v):
    return isinstance(v,str) and len(v.strip())>=6 and not any(s in v.lower() for s in ('待填写','todo','pending'))

def valid_operation(p):
    op=p.get('operation')
    if op is None:return True
    shapes=p.get('input_shapes',[]);out=p.get('output_shape',[])
    if not shapes or not out or any(not isinstance(n,int) or n<=0 for s in shapes+[out] for n in s):return False
    if op=='add':return all(s==out for s in shapes)
    if op=='concat':
        axis=p.get('axis');rank=len(out)
        if not isinstance(axis,int) or not 0<=axis<rank or any(len(s)!=rank for s in shapes):return False
        return out[axis]==sum(s[axis] for s in shapes) and all(s[j]==out[j] for s in shapes for j in range(rank) if j!=axis)
    return meaningful(p.get('semantic_review'))

def verify_views(root,d,views):
    """Re-render declared PDF and derive detail/grayscale; never infer a human viewed it."""
    import pymupdf as fitz
    from PIL import Image,ImageOps
    by_kind={v['kind']:v for v in views}
    for kind in ('overall','detail','pdf_size','grayscale'):
        if kind not in by_kind:return False
    with Image.open(path(root,d['outputs']['preview'])) as im:
        source=im.convert('RGB')
        for kind in ('overall','detail','grayscale'):
            v=by_kind[kind]
            if kind=='overall':expected=source
            elif kind=='grayscale':expected=ImageOps.grayscale(source).convert('RGB')
            else:
                box=v.get('crop_box',[])
                if len(box)!=4 or not (0<=box[0]<box[2]<=source.width and 0<=box[1]<box[3]<=source.height):return False
                if box==[0,0,source.width,source.height]:return False
                expected=source.crop(box)
            with Image.open(path(root,v['path'])) as actual:
                if actual.size!=expected.size or actual.convert('RGB').tobytes()!=expected.tobytes():return False
    v=by_kind['pdf_size']
    if v.get('pdf_path')!=d['outputs']['vector'] or v.get('pdf_sha256')!=sha(path(root,v['pdf_path'])):return False
    dpi=v.get('dpi',0)
    if not isinstance(dpi,int) or not 72<=dpi<=600:return False
    with fitz.open(path(root,v['pdf_path'])) as doc:
        if v.get('page_number')!=1:return False
        pix=doc[0].get_pixmap(dpi=dpi,alpha=False)
        with Image.open(path(root,v['path'])) as actual:
            return actual.size==(pix.width,pix.height) and actual.convert('RGB').tobytes()==pix.samples

def initialize(plan_path, runtime):
    plan=load(plan_path); out=sidecar(plan_path)
    if out.exists(): raise ValueError('Keep existing diagram history: '+str(out))
    data={'schema_version':'1.0','overview_content_version':'2.0','purpose':'production','runtime':runtime,
          'questions':[{'problem_id':q['problem_id'],'chapter_id':'','supporting_question_id':'',
                        'overview_id':q['problem_id']+'-OVERVIEW'} for q in plan['problems']],
          'diagrams':[], 'figure_accounting':[], 'paper_review_path':''}
    out.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    return out

def diagram_specs(plan_path):
    d=load(sidecar(plan_path))
    return [{'figure_id':x['diagram_id'],'vector_path':x['outputs']['vector'],
             'target_width_mm':x['target_width_mm']} for x in d['diagrams'] if x.get('placement')=='body']

def as_schematic(d):
    """Normalize only for existing Figure counting; no mutation of the v1 plan."""
    return {'schematic_id':d['diagram_id'],'source_refs':[r['path'] for r in d.get('sources',[])],
            'elements':[p['panel_id'] for p in d.get('panels',[])], 'tex_source':d.get('source'),
            'output_pdf':d.get('outputs',{}).get('vector'),'preview_png':d.get('outputs',{}).get('preview'),
            'paper':d.get('paper',{}),'status':d.get('status','planned')}

def audit(plan_path, stage, root, runtime, main_tex=None, question_id=None,
          paper_manifest=None, supporting_manifest=None, allow_demo=False, diagram_ids=None):
    root=Path(root).resolve(); checks=[]; failures=[]; accounting=None
    def add(code,ok,**kw):
        row={'code':code,'ok':bool(ok),**kw}; checks.append(row)
        if not ok: failures.append(row)
    def current(r):
        p=path(root,r['path'])
        return p.is_file() and p.stat().st_size>0 and r.get('sha256')==sha(p)
    def reference_current(r):
        from workspace_context import resource_path
        from filesystem_paths import native_path
        p=native_path(resource_path(root,r['path'],runtime))
        return p.is_file() and p.stat().st_size>0 and r.get('sha256')==sha(p)
    try:
        plan=load(plan_path); data=load(sidecar(plan_path))
        add('diagram_schema',data.get('schema_version')=='1.0')
        add('runtime_explicit',runtime in SIDES and data.get('runtime')==runtime)
        demo=stage=='demo-paper'
        add('demo_isolation',data.get('purpose')=='production' or
            (allow_demo and data.get('purpose')=='demo' and stage!='paper' and
             any('demo' in s.lower() for s in Path(plan_path).resolve().relative_to(root).parts)))
        if demo: add('demo_not_production',data.get('purpose')=='demo' and allow_demo)
        stage='paper' if demo else stage
        qs=data['questions']; ds=data['diagrams']; ids=[d['diagram_id'] for d in ds]
        if diagram_ids is None:
            from figure_accounting import audit_counts
            accounting=audit_counts(plan,data,stage,root,question_id)
            add('figure_accounting_gate',accounting['status']=='PASS',failures=accounting['failures'])
            from build_figure_accounting import audit_publications
            publications=audit_publications(root,plan_path,plan,data,accounting,stage,runtime)
            add('figure_accounting_publications',publications['status']=='PASS',errors=publications['errors'],
                figure_list=publications['figure_list'],result_index=publications['result_index'])
        else:
            add('component_stage_only',stage in ('plan','render'))
            add('components_exist',bool(diagram_ids) and set(diagram_ids)<=set(ids))
        pids=[p['problem_id'] for p in plan['problems']]
        add('question_mapping_exact',[q['problem_id'] for q in qs]==pids and len(set(pids))==len(pids))
        add('diagram_ids_unique',len(ids)==len(set(ids)))
        add('overview_ids_unique',len({q['overview_id'] for q in qs})==len(qs))
        body=[d for d in ds if d.get('placement')=='body']
        labels=[d.get('paper',{}).get('label') for d in body]
        add('diagram_labels_unique',len(labels)==len(set(labels)))
        by_id={d['diagram_id']:d for d in ds}
        components = None
        if diagram_ids is not None:
            components = set(diagram_ids)
            todo = list(components)
            while todo:
                item = by_id.get(todo.pop(), {})
                for panel in item.get('panels', []):
                    child = panel.get('diagram_id')
                    if child and child not in components:
                        components.add(child)
                        todo.append(child)
        def acyclic(node, active, done):
            if node in active:return False
            if node in done:return True
            active.add(node)
            for panel in by_id.get(node,{}).get('panels',[]):
                child=panel.get('diagram_id')
                if child and not acyclic(child,active,done):return False
            active.remove(node);done.add(node);return True
        add('diagram_dependencies_acyclic',all(acyclic(i,set(),set()) for i in ids))
        if question_id:
            selected=[q for q in qs if question_id in (q['problem_id'],q['supporting_question_id'])]
            add('question_selected',len(selected)==1)
        else: selected=qs
        if supporting_manifest:
            sm=load(supporting_manifest)
            add('supporting_question_mapping',[q['supporting_question_id'] for q in qs]==[q['question_id'] for q in sm['questions']])
        pm=paper_manifest or root/'论文/论文输入.json'
        chapters=[]
        if Path(pm).is_file():
            chapters=sorted([c for c in load(pm)['chapters'] if c['role']=='problem'],key=lambda c:c['order'])
            add('paper_problem_mapping',[q['chapter_id'] for q in qs]==[c['chapter_id'] for c in chapters])
        elif stage in ('tex','paper'): add('paper_manifest_exists',False)
        for q in selected if components is None else []:
            d=by_id.get(q['overview_id'],{});tag=q['problem_id']
            add(tag+':overview_exists',d.get('kind')=='comprehensive' and d.get('problem_id')==tag and d.get('placement')=='body')
            add(tag+':chapter_declared',bool(q.get('chapter_id')) and bool(q.get('supporting_question_id')))
        relevant={q['problem_id'] for q in selected}
        for d in ds:
            if components is not None and d['diagram_id'] not in components: continue
            if question_id and d.get('problem_id') not in relevant: continue
            tag=d['diagram_id'];kind=d.get('kind'); panels=d.get('panels',[])
            add(tag+':kind',kind in KINDS)
            add(tag+':owner',d.get('problem_id') in pids or d.get('problem_id') is None)
            add(tag+':backend',d.get('backend') in ('drawio','tikz','plotneuralnet','other_vector') and meaningful(d.get('backend_reason')))
            add(tag+':science',meaningful(d.get('scientific_question')) and bool(d.get('sources')))
            add(tag+':reference_selection',bool(d.get('references')) and all(
                reference_current(r) and r.get('reviewed') is True and meaningful(r.get('observation')) and meaningful(r.get('decision'))
                and SIDES.get(runtime,'INVALID') in Path(r['path']).parts for r in d.get('references',[])))
            from roadmap_templates import audit as audit_roadmap_template, is_roadmap
            if is_roadmap(d):
                roadmap_qa = (load(path(root,d['qa_path'])) if d.get('qa_path') and
                              path(root,d['qa_path']).is_file() else None)
                for row in audit_roadmap_template(root,runtime,d,stage,roadmap_qa):
                    add(tag+':'+row['code'],row['ok'],**{k:v for k,v in row.items() if k not in {'code','ok'}})
            add(tag+':panels_unique',bool(panels) and len({p['panel_id'] for p in panels})==len(panels))
            add(tag+':connections_traceable',bool(d.get('connections')) and all(
                e.get('from') in {p['panel_id'] for p in panels} and e.get('to') in {p['panel_id'] for p in panels}
                and e.get('type') in RELATION_TYPES and e.get('from') != e.get('to')
                and meaningful(e.get('meaning')) and bool(e.get('source_locator')) for e in d.get('connections',[])))
            from figure_accounting import FLOW_EDGES
            add(tag+':flow_semantics_supported',d.get('flow_semantics') is not True or any(
                e.get('type') in FLOW_EDGES and e.get('from') != e.get('to') for e in d.get('connections',[])))
            if kind=='comprehensive':
                from audit_academic_figure_assets import schema_errors
                size_schema=load(Path(__file__).resolve().parent.parent/'综合图尺寸.schema.json')
                size_errors=schema_errors(d.get('physical_size',{}),size_schema)
                add(tag+':physical_size_plan',not size_errors,errors=size_errors)
                design=d.get('overview_design',{})
                analytic_exception=(design.get('mechanism',{}).get('applicable') is False and
                    meaningful(design.get('mechanism',{}).get('reason')) and meaningful(design.get('omission_reason')) and
                    any(p.get('kind')=='analytic_conclusion' and meaningful(p.get('content')) for p in panels))
                add(tag+':substantive_graphic',any(p.get('kind') in GRAPHICAL and meaningful(p.get('content')) for p in panels) or analytic_exception)
                add(tag+':task_method_flow',all(meaningful(d.get('narrative',{}).get(k)) for k in ('task','basis','solve')))
                # Outcomes/validation/formulas are selected by scientific need,
                # not required panel categories for every possible question.
                add(tag+':optional_narrative_substantive',all(meaningful(v) for v in d.get('narrative',{}).values()))
                add(tag+':overview_detail',meaningful(d.get('overview_detail')))
                content_qa = load(path(root,d['qa_path'])) if (stage != 'plan' or d.get('status') == 'qa_pass') and d.get('qa_path') and path(root,d['qa_path']).is_file() else None
                for row in audit_content(root, plan, d, stage, purpose=data.get('purpose'), qa=content_qa):
                    add(tag+':'+row['code'],row['ok'],**{k:v for k,v in row.items() if k not in {'code','ok'}})
            # Result/media panels reference canonical figures; their own panels choose the gates.
            for p in panels:
                add(tag+':'+p['panel_id']+':semantic_source',p.get('source_path') in {s['path'] for s in d.get('sources',[])} and
                    bool(p.get('source_locator')) and meaningful(p.get('semantic_review')))
                add(tag+':'+p['panel_id']+':operation_shapes',valid_operation(p))
                if p.get('kind') in {'object','geometry'} and Path(p.get('source_path','')).suffix.lower() in {
                        '.png','.jpg','.jpeg','.bmp','.gif','.webp','.tif','.tiff'}:
                    add(tag+':'+p['panel_id']+':image_provenance_route',bool(p.get('visual_plan')))
                if p.get('kind')=='result' or p.get('visual_plan'):
                    from visual_routes import audit_routes, figures, primary_output
                    ap=path(root,p.get('visual_plan') or p.get('academic_plan',''))
                    fid=p.get('visual_figure_id') or p.get('academic_figure_id')
                    linked_plan=load(ap)
                    linked=next((f for f in figures(linked_plan) if f['figure_id']==fid),{})
                    if kind=='comprehensive' and p.get('kind')=='result':
                        for row in audit_result_source(root,d,p,linked_plan,linked,stage,data.get('purpose')):
                            add(tag+':'+p['panel_id']+':'+row['code'],row['ok'])
                    else:
                        add(tag+':'+p['panel_id']+':canonical_figure_source',p.get('source_path') in
                            {primary_output(linked),linked.get('outputs',{}).get('preview')})
                    result=audit_routes(ap,'plan' if stage=='plan' else 'render',root,runtime,
                                        allow_demo=allow_demo,figure_ids=[fid])
                    add(tag+':'+p['panel_id']+':visual_gate',result['status']=='PASS',failures=result['failures'])
                if p.get('diagram_id'):
                    child=by_id.get(p['diagram_id'],{})
                    add(tag+':'+p['panel_id']+':child_current',child.get('kind') in ('algorithm','physics') and child.get('problem_id')==d.get('problem_id'))
                    child_files={child.get('source'),*child.get('outputs',{}).values(),*child.get('dependencies',[]),*[s['path'] for s in child.get('sources',[])]}
                    add(tag+':'+p['panel_id']+':child_dependencies',None not in child_files and child_files<=set(d.get('dependencies',[])))
            paper=d.get('paper',{})
            add(tag+':paper_contract',str(paper.get('label','')).startswith('fig:') and bool(str(paper.get('caption','')).strip()) and meaningful(paper.get('reference_context')))
            if stage in ('render','question','tex','paper'):
                add(tag+':sources_current',all(current(r) and bool(r.get('locator')) for r in d.get('sources',[])))
                required=[d['source'],d['outputs']['vector'],d['outputs']['preview'],d['qa_path']]
                add(tag+':artifacts_exist',all(path(root,r).is_file() and path(root,r).stat().st_size for r in required))
                qa=load(path(root,d['qa_path']))
                from workspace_resources import evidence_current
                add(tag+':resource_dependencies_current',evidence_current(root,runtime,'structure',qa))
                expected={d['source'],*d.get('dependencies',[]),*d['outputs'].values(),*[r['path'] for r in d['sources']]}
                if is_roadmap(d) and d.get('template_selection_path'):
                    expected.add(d['template_selection_path'])
                add(tag+':qa_inputs_current',set(qa.get('files',{}))==expected and all(path(root,r).is_file() and sha(path(root,r))==h for r,h in qa.get('files',{}).items()))
                add(tag+':qa_pass',d.get('status')=='qa_pass' and qa.get('status')=='pass' and meaningful(qa.get('scientific_review')))
                views=qa.get('views',[])
                add(tag+':actual_visual_review',{'overall','detail','pdf_size','grayscale'}<={v.get('kind') for v in views} and all(
                    v.get('reviewed') is True and meaningful(v.get('observation')) and bool(v.get('tool_ref')) and current(v) for v in views))
                add(tag+':views_derived_from_current_outputs',verify_views(root,d,views))
                import pymupdf as fitz
                with fitz.open(path(root,d['outputs']['vector'])) as pdf:
                    add(tag+':pdf_vector_content',any(p.get_drawings() for p in pdf),assurance='Vector primitives present; not a proof of full vector purity')
                    add(tag+':pdf_width',len(pdf)==1 and abs(pdf[0].rect.width*25.4/72-d['target_width_mm'])<3)
                    raster_ok=True
                    for page in pdf:
                        for item in page.get_images(full=True):
                            for rect in page.get_image_rects(item[0]):
                                if rect.width>0 and rect.height>0:
                                    raster_ok &= (min(item[2]*72/rect.width,item[3]*72/rect.height)>=299.5 or
                                                  native_bitmap_review(root,pdf,item,rect,qa.get('native_resolution_reviews',[])))
                    add(tag+':embedded_images_at_final_size',raster_ok)
                if d['backend']=='drawio':
                    import subprocess,sys
                    from workspace_context import resource_path
                    checker=resource_path(root, str(Path(SIDES[runtime])/'skills/sci-box-main/sci-box-main/skills/scibox-diagram/scripts/check_layout.py'),runtime)
                    command=[sys.executable,'-X','utf8',str(checker),str(path(root,d['source'])),'--strict']
                    if d.get('layout_exceptions'):command+=['--exceptions',str(path(root,d['layout_exceptions']))]
                    r=subprocess.run(command,capture_output=True,text=True,encoding='utf8',errors='replace')
                    add(tag+':drawio_layout',r.returncode==0,output=r.stdout+r.stderr)
        if not question_id and components is None:
            flows=[d for d in body if d.get('flow_semantics') is True and any(
                e.get('type') in FLOW_EDGES and e.get('from') != e.get('to') for e in d.get('connections',[]))]
            add('global_roadmap_present',any(d.get('problem_id') is None and d.get('kind')=='flowchart' for d in flows))
            add('two_real_flowcharts',len(flows)>=2)
            planned={f['plan_id'] for f in plan.get('flowcharts',[]) if f.get('needed')=='yes'}
            add('flowchart_plan_links',all(d['diagram_id'] in planned for d in flows))
        if stage in ('tex','paper'):
            from audit_diagram_positions import source_positions, physical_positions
            from audit_visual_plan import body_tex
            main=path(root,str(main_tex or '论文/论文.tex'))
            full=body_tex(main)
            positions=source_positions(load(pm),Path(pm).resolve(),main,root,ds,selected)
            for position in positions:
                add(str(position.get('diagram_id','?'))+':source_position',
                    position['status']=='PASS',evidence=position)
            for d in body:
                label=d['paper']['label']
                add(d['diagram_id']+':unique_body_label',
                    len(re.findall(r'\\label\s*\{'+re.escape(label)+r'\}',full))==1)
            if stage=='paper':
                from collect_academic_paper_review import verify_evidence
                review=load(path(root,data['paper_review_path']))
                from visual_routes import paper_specs
                specs=paper_specs(plan_path)
                errs=verify_evidence(root,review,main,runtime,specs)
                add('compiled_paper_and_visual_review',not errs,failures=errs)
                if not errs:
                    from overview_geometry import audit_bodies
                    for measurement in audit_bodies(root, body, review):
                        add(measurement['diagram_id']+':physical_body_size',
                            measurement['status']=='PASS', evidence=measurement)
                    from audit_pdf_layout import audit_layout
                    layout=audit_layout(path(root,review['pdf_path']),main,Path(pm).resolve())
                    add('actual_pdf_layout',layout['status']=='PASS',failures=layout['failures'])
                    for position in physical_positions(positions,review,layout,main,root):
                        add(str(position.get('diagram_id','?'))+':physical_position',
                            position['status']=='PASS',evidence=position)

    except (OSError,ValueError,KeyError,TypeError,StopIteration,ImportError) as e:
        add('diagram_input_valid',False,error=f'{type(e).__name__}: {e}')
    return {'status':'FAIL' if failures else 'PASS','stage':stage,'checks':checks,'failures':failures,'figure_accounting':accounting,
            'assurance':'文件/哈希/引用检查不证明实际看图或科学判断；DEMO不授予正式论文通过状态。'}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan',type=Path,required=True);p.add_argument('--project-root',type=Path,default=Path('.'))
    p.add_argument('--runtime',choices=SIDES,required=True)
    p.add_argument('--stage',choices=('plan','render','question','tex','paper','demo-paper'),default='plan')
    p.add_argument('--main-tex',type=Path);p.add_argument('--paper-manifest',type=Path)
    p.add_argument('--supporting-manifest',type=Path);p.add_argument('--question-id')
    p.add_argument('--allow-demo',action='store_true');p.add_argument('--report',type=Path,required=True)
    p.add_argument('--prepare-overviews',action='store_true',help='Add missing pending v2 designs, preserving a sidecar backup; does not grant QA')
    a=p.parse_args()
    if a.prepare_overviews:
        from overview_content import prepare_overviews
        changed=prepare_overviews(a.plan)
        result={'status':'PENDING','changed':changed,'assurance':'No scientific or visual review performed.'}
    else:
        result=audit(a.plan,a.stage,a.project_root,a.runtime,a.main_tex,a.question_id,a.paper_manifest,a.supporting_manifest,a.allow_demo)
    a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'status':result['status'],'checks':len(result.get('checks',[])),'failures':result.get('failures',[])},ensure_ascii=False))
    raise SystemExit(0 if result['status'] in {'PASS','PENDING'} else 1)
if __name__=='__main__':main()
