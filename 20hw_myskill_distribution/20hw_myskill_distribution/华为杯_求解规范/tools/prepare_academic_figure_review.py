#!/usr/bin/env python3
"""Create an UNREVIEWED sidecar from an existing visual plan; never invent viewing observations."""
from __future__ import annotations

# Shared execution is explicit; direct legacy/maintenance CLIs must declare mode.
if __name__ == "__main__":
    import sys as _workflow_sys
    _workflow_sys.dont_write_bytecode = True
    from workspace_cli import require_cli_mode
    require_cli_mode(__file__)

import argparse
import json
import uuid
import re
import copy
import hashlib
from pathlib import Path
from build_academic_figure_asset_index import build_index, safe, sha, write_json, runtime_skill
from visual_routes import academic_figures, academic_panels


def plan_figures(plan):
    return list(plan.get('global_figures', []))+[f for p in plan.get('problems',[]) for f in p.get('figures',[])]


def sidecar_path(plan):
    return Path(plan).with_name(Path(plan).stem+'.assets.json')


def select_figures(plan, refs, figure_ids):
    """Select complete figure records, preserving their original provenance paths."""
    ids = set(figure_ids)
    available = [f['figure_id'] for f in plan_figures(plan)]
    if not ids or not ids <= set(available) or len(available) != len(set(available)):
        raise ValueError('Unknown or duplicate figure IDs')
    selected = copy.deepcopy(plan)
    selected['global_figures'] = [f for f in selected.get('global_figures', []) if f['figure_id'] in ids]
    for problem in selected.get('problems', []):
        problem['figures'] = [f for f in problem.get('figures', []) if f['figure_id'] in ids]
    records = copy.deepcopy(refs)
    records['figures'] = [f for f in records.get('figures', []) if f['figure_id'] in ids]
    return selected, records


def figure_contract_digest(figure, reference):
    contract = [copy.deepcopy(figure), copy.deepcopy(reference)]
    for row in contract:
        row.pop('status', None)
    return hashlib.sha256(json.dumps(contract, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':')).encode('utf-8')).hexdigest()


STYLE_KEYS = ['layout','hierarchy','facets','palette','line_width','marker_size','alpha',
              'axes','ticks','grid','legend','colorbar','annotations','spacing','statistics','typography']


def search_catalog(index, query):
    """Search every family, including zero hits; suggestions never become reviewed selections."""
    terms=set(re.findall(r'[a-zA-Z][a-zA-Z0-9_-]+|[\u3400-\u9fff]{2,}',query.lower()))
    rows=[]
    for family in index['families']:
        text=' '.join([family['figure_type'],family['chinese_name'],family['english_name'],
            family['data_structure_hint'],family['scientific_question_hint'],*family['keywords']]).lower()
        hits=sorted(t for t in terms if t in text)
        keyword_hits=[k for k in family['keywords'] if k.lower() in query.lower()]
        rows.append({'family':family['figure_type'],'score':len(hits)+2*len(keyword_hits),
            'matched_terms':sorted(set(hits+keyword_hits)),'has_source':bool(family['production_scripts']),
            'data_structure_hint':family['data_structure_hint'],'status':'needs_review'})
    return sorted(rows,key=lambda x:(-x['score'],x['family']))


def prepare(root, plan_path, index_path, purpose='production', runtime=None, gallery_review=None):
    root=Path(root).resolve(); plan=json.loads(Path(plan_path).read_text(encoding='utf-8-sig'))
    if not academic_figures(plan):
        raise ValueError('No academic panels: use audit_media_figures --prepare; no atlas indexing is needed')
    index=json.loads(Path(index_path).read_text(encoding='utf-8-sig'))
    runtime,skill=runtime_skill(runtime,index['skill_root'])
    if runtime!=index.get('runtime'):raise ValueError('Runtime/index mismatch')
    current=build_index(root,index['skill_root'])
    if current != index: raise ValueError('Stale index: rebuild before preparing reference records')
    fam={f['figure_type']:f for f in index['families']}; items=[]
    for f in academic_figures(plan):
        panels=[]
        for p in academic_panels(f):
            query=' | '.join([p['question'],f['scientific_question'],*p['fields'],*p['units']])
            search=search_catalog(index,query)
            panels.append({'panel_id':p['panel_id'],'scientific_question':p['question'],
              'atlas_reference':'','production_asset':'','source_example_path':'','source_locator':'',
              'asset_family':'','candidate_families':[], 'candidate_atlas':[],
              'candidate_search':{'query':query,'scan_digest':index['scan_digest'],'results':search,
                                  'reviewed':False,'selection_reason':'','single_candidate_reason':''},
              'candidate_comparison':[],
              'adaptation_mode':p['asset_mode'],
              'data_schema':{'fields':p['fields'],'units':p['units'],'shape':'','groups':[]},
              'data_state':'planned','data_profile_path':'',
              'style_parameters_inherited':{},'changed_parameters':{},'reason_for_change':'',
              'style_contract':{key:{'reference_value':'','final_value':'','basis':'','source_path':'',
                                    'source_locator':'','reason':''} for key in STYLE_KEYS},
              'candidate_review':[],
              'selection_status':'needs_review'})
        items.append({'figure_id':f['figure_id'],'backend':'academic-figure-skill','backend_reason':'',
          'scientific_question':f['scientific_question'],'core_claim':'','evidence_role':'',
          'figure_contract':{'necessity':'','evidence_chain':'','review_risks':''},
          'intended_layout':f['layout'],'target_width_mm':0,
          'paper_geometry':{'source_tex':'','source_sha256':'','text_width_mm':0,'width_fraction':0,'basis':''},
          'panel_plan':panels,'script':f['script'],
          'final_pdf_path':f['outputs']['vector'] if f['outputs']['vector'].endswith('.pdf') else '',
          'final_svg_path':f['outputs']['vector'] if f['outputs']['vector'].endswith('.svg') else '',
          'final_png_path':f['outputs']['preview'],'statistics_report_path':f['statistics_report'],
          'visual_qa_path':f['qa_report'],'status':'incomplete','run_record_path':''})
    gallery=safe(root,str(gallery_review)) if gallery_review else None
    return {'schema_version':'2.0','runtime':runtime,'purpose':purpose,'plan_path':Path(plan_path).resolve().relative_to(root).as_posix(),
      'index_path':Path(index_path).resolve().relative_to(root).as_posix(),'scan_digest':index['scan_digest'],
      'gallery_review_path':gallery.relative_to(root).as_posix() if gallery else '',
      'gallery_review_sha256':sha(gallery) if gallery and gallery.is_file() else '',
      'skill_root':index['skill_root'],'review_session_id':str(uuid.uuid4()),'figures':items,
      'assurance':'Scanned by prepare; candidate observations are deliberately empty. Tool refs are attestations, not cryptographic proof of seeing.'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--project-root',type=Path,default=Path('.'))
    p.add_argument('--plan',type=Path,required=True);p.add_argument('--index',type=Path,default=Path('求解/academic_figure_asset_index.json'))
    p.add_argument('--runtime',choices=['codex','claude'],required=True);p.add_argument('--gallery-review',type=Path,required=True)
    p.add_argument('--output',type=Path);p.add_argument('--purpose',choices=['production','demo'],default='production');p.add_argument('--force',action='store_true')
    a=p.parse_args();root=a.project_root.resolve();plan=safe(root,str(a.plan));output=safe(root,str(a.output or sidecar_path(plan)))
    if output.exists() and not a.force: raise SystemExit('Refusing to overwrite review records; use --force only after backing them up')
    value=prepare(root,plan,safe(root,str(a.index)),a.purpose,a.runtime,a.gallery_review);write_json(output,value)
    print(json.dumps({'status':'DRAFT_REQUIRES_REVIEW','output':str(output),'figures':len(value['figures'])},ensure_ascii=False))

if __name__=='__main__':main()
