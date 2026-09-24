"""Focused, registered DEMO audit; never grants full paper acceptance.

Reuses unchanged academic/diagram render gates and actual compilation evidence.
"""
from pathlib import Path
import argparse
import json


def focused_layout(root, main, review, sources):
    import pymupdf as fitz
    from audit_pdf_layout import glyphs, find_glyph_text, rectangle, destination
    headings=[];captions=[];failures=[]
    with fitz.open(root/review['pdf_path']) as pdf:
        names=pdf.resolve_names()
        chars=[glyphs(p) for p in pdf]
        for anchor in sorted({s[k] for s in sources if s['status']=='PASS' for k in ('lower_anchor','upper_anchor')}):
            dest=destination(pdf,names,anchor)
            if not dest:
                failures.append('missing_heading:'+anchor);continue
            p,x,y=dest
            # Bind to actual numbered heading text and destination, not source order.
            number=anchor.split('.',1)[1]
            matches=find_glyph_text(chars[p],number)
            matches=[c for c in matches if abs(c[0]['bbox'][1]-y)<35 and abs(c[0]['bbox'][0]-x)<20]
            if len(matches)!=1:
                failures.append('ambiguous_heading:'+anchor);continue
            baseline=matches[0][0]['origin'][1]
            cs=[c for c in chars[p] if abs(c['origin'][1]-baseline)<.5]
            title=''.join(c['c'] for c in cs)
            if anchor.endswith('.1') and '问题的描述与分析' not in title:
                failures.append('first_heading_title:'+anchor)
            headings.append({'anchor':anchor,'physical_page':p+1,'bbox':rectangle(cs),'text':title})
        for s in sources:
            if s['status']!='PASS':continue
            candidates=[]
            for p,cs in enumerate(chars):
                for found in find_glyph_text(cs,s['source_caption']):
                    candidates.append((p,found))
            if len(candidates)!=1:
                failures.append('unique_actual_caption:'+s['diagram_id']);continue
            p,cs=candidates[0];baseline=cs[0]['origin'][1]
            line=[c for c in chars[p] if abs(c['origin'][1]-baseline)<.5]
            if len({round(c['origin'][1],1) for c in cs})!=1:
                failures.append('caption_not_one_line:'+s['diagram_id'])
            captions.append({'label':s['label'],'physical_page':p+1,'bbox':rectangle(line),'text':''.join(c['c'] for c in line)})
    return {'scope':'overview_only','headings':headings,'captions':captions,'failures':failures}


def audit(root, plan_path, main, manifest_path, review_path, require_visual=True):
    from workspace_context import shared_context, bounded
    from audit_diagram_workflow import load, sidecar, audit as diagram_audit
    from audit_diagram_positions import source_position, physical_positions
    from paper_contract import expand_fragment
    from collect_academic_paper_review import verify_evidence
    from overview_geometry import audit_bodies
    root=Path(root).resolve();ctx=shared_context(root,'codex')
    if not ctx or ctx.manifest['purpose']!='demo':raise ValueError('Registered DEMO workspace required')
    plan_path=bounded(root,str(plan_path));main=bounded(root,str(main));manifest_path=bounded(root,str(manifest_path))
    data=load(sidecar(plan_path));plan=load(plan_path);review=load(bounded(root,str(review_path)));manifest=load(manifest_path)
    failures=[];pids=[p['problem_id'] for p in plan['problems']]
    if data.get('purpose')!='demo':failures.append('demo_purpose_required')
    if [q['problem_id'] for q in data['questions']]!=pids or len(pids)!=len(set(pids)):failures.append('question_mapping_exact')
    ds=data['diagrams'];overview=[]
    for q in data['questions']:
        found=[d for d in ds if d.get('problem_id')==q['problem_id'] and d.get('kind')=='comprehensive' and d.get('placement')=='body']
        if len(found)!=1 or found[0]['diagram_id']!=q['overview_id']:failures.append('primary_overview_coverage:'+q['problem_id'])
        else:overview+=found
    if len({q['overview_id'] for q in data['questions']})!=len(pids):failures.append('overview_ids_unique')
    if not any(d.get('kind')=='flowchart' and d.get('problem_id') is None for d in ds):failures.append('global_roadmap_required')
    render=diagram_audit(plan_path,'render',root,'codex',allow_demo=True,diagram_ids=[d['diagram_id'] for d in ds])
    if render['status']!='PASS':failures.append('component_render_gate')
    specs=[{'figure_id':d['diagram_id'],'vector_path':d['outputs']['vector'],'target_width_mm':d['target_width_mm']} for d in ds if d.get('placement')=='body']
    compile_errors=verify_evidence(root,review,main,'codex',specs,require_visual=require_visual)
    failures+=compile_errors
    sources=[]
    for q in data['questions']:
        d=next((d for d in overview if d['diagram_id']==q['overview_id']),None)
        chapter=next((c for c in manifest['chapters'] if c['chapter_id']==q['chapter_id']),None)
        if not d or not chapter:failures.append('missing_chapter_or_overview');continue
        text=expand_fragment(main.parent,manifest_path.parent/chapter['tex_path'])
        sources.append(source_position(text,chapter,d,main,root,main.read_text(encoding='utf8')))
    if any(s['status']!='PASS' for s in sources):failures.append('source_position')
    layout={};positions=[];sizes=[]
    if not compile_errors:
        layout=focused_layout(root,main,review,sources);failures+=layout['failures']
        positions=physical_positions(sources,review,layout,main,root)
        sizes=audit_bodies(root,overview,review)
        if any(p['status']!='PASS' for p in positions):failures.append('actual_pdf_position')
        if any(p['status']!='PASS' for p in sizes):failures.append('actual_pdf_body_size')
    return {'status':'FAIL' if failures else 'PASS','scope':'registered_overview_DEMO_only','formal_paper_acceptance':False,
            'failures':failures,'component_render':render,'source_positions':sources,'physical_positions':positions,
            'body_measurements':sizes,'focused_layout':layout,
            'limitations':['No full-paper, 35-page, independent-figure-count, model-contest or formal support-material acceptance.',
                            'Machine geometry does not certify visual density, readable meaning or scientific correctness.']}


if __name__=='__main__':
    from workspace_cli import require_cli_mode
    require_cli_mode(__file__)
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('plan','main-tex','manifest','review','report'):p.add_argument('--'+name,required=True)
    a=p.parse_args()
    result=audit(Path.cwd(),a.plan,a.main_tex,a.manifest,a.review)
    from workspace_context import bounded
    bounded(Path.cwd(),a.report).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'status':result['status'],'failures':result['failures']},ensure_ascii=False))
    raise SystemExit(result['status']!='PASS')
