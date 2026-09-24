#!/usr/bin/env python3
"""Deterministic academic asset inventory + labelled contact sheets; never certifies human viewing."""
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
from filesystem_paths import native_path

DEFAULT_SKILL = '.agents/skills/academic-figure-skill'
RUNTIME_SKILLS = {'codex': DEFAULT_SKILL, 'claude': '.claude/skills/academic-figure-skill'}
IMAGE_EXT = {'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.webp', '.bmp', '.gif'}
OUTPUT_EXT = IMAGE_EXT | {'.pdf', '.svg'}
SCRIPT_EXT = {'.py', '.r'}
# Search hints, NOT claims about a future contest dataset. Every selection needs visual review.
ATLAS_HINTS = {
 '3DHeatmap': ['3Dheatmap.png'], 'AUROC': ['auroc.png'],
 'BarAblation': ['bar.png'], 'BarCategorical': ['bar.png'], 'BarComparison': ['bar.png','GroupedBarChart.png'],
 'BarComposition': ['StackedBarScatter.png'], 'BarDistribution': ['bar.png'],
 'GroupedBarChart': ['GroupedBarChart.png'], 'StackedBarScatter': ['StackedBarScatter.png'],
 'CorrelationMatrix': ['Correlationmatrix.png'], 'GroupedCorrelationMatrix': ['GroupCorrelationmatrix.png'],
 'DensityHeatmap': ['density_heatmap.png'], 'Frequency_3DHeatmap': ['Frequency_3DHeatmap.png'],
 'GroupedViolin': ['violin_chart.png'], 'Violin': ['violin_chart.png'],
 'KernelDensity': ['CorrelationDensity.png'], 'MarginalDensity': ['CorrelationDensity.png'],
 'LineTrend': ['trend.png'], 'Manifold': ['PCA.png'], 'PCA': ['PCA.png'],
 'MantelCorrelation': ['MantelCorrelation.png'], 'PairedBoxScatter': ['violin_chart.png'],
 'Radar': ['radar.png'], 'RidgePlot': ['RidgePlot.png'], 'SankeyDiagram': ['sankey.png'],
 'ParameterSweep': ['3Dheatmap.png','density_heatmap.png'], 'ScenarioHeatmap': ['density_heatmap.png'],
 'ResidualDiagnostics': ['trend.png','RidgePlot.png'], 'ConvergenceBand': ['trend.png'],
 'ResourceDesign': ['trend.png'], 'SensitivityTornado': ['bar.png'],
 'ContributionWaterfall': ['bar.png'], 'MonteCarloRecovery': ['CorrelationDensity.png'],
 'PhaseProfile': ['density_heatmap.png','trend.png'], 'TrajectoryProjection': ['PCA.png'],
 'heatmap': ['density_heatmap.png'], 'ConfusionMatrix': ['Correlationmatrix.png'],
 'MarkerGeneDotPlot': ['data-figure.png'], 'volcano': ['data-figure.png'],
}
SHAPES = [
 (['Bar','Tornado','Waterfall'], 'category/group × quantitative value (optional genuine replicate/interval)', ['main_result','sensitivity']),
 (['Residual','Convergence','Recovery'], 'ordered/repeated observations + error/uncertainty', ['validation','error','robustness']),
 (['Heatmap','heatmap','Sweep','CorrelationMatrix'], 'matrix/grid + numeric value + optional annotations', ['main_result','scenario']),
 (['Violin','Density','Ridge','Box'], 'numeric observations + optional grouping/pair identifiers', ['main_result','error']),
 (['Trajectory','Manifold','PCA'], 'samples × coordinates/features', ['main_result','mechanism']),
 (['Line','Resource','Phase'], 'ordered coordinate × numeric response', ['main_result','sensitivity']),
 (['AUROC','Confusion'], 'true class + predicted score/class (or verified aggregate)', ['validation']),
 (['Sankey'], 'source/target/flow with meaningful conservation', ['main_result']),
]


def sha(path):
    return hashlib.sha256(native_path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',',':')).encode()).hexdigest()


def write_json(path, value):
    path = native_path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)+'\n', encoding='utf-8')


def safe(root, raw):
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError('Empty/non-string path')
    from workspace_context import bounded
    return bounded(root, raw)


def files(root):
    root=Path(root); extended=native_path(root)
    return sorted((root/p.relative_to(extended) for p in extended.rglob('*')
                   if p.is_file() and '__pycache__' not in p.parts and p.suffix.lower() != '.pyc'),key=lambda p:p.as_posix())


def parse_map(path):
    result={}
    for line in native_path(path).read_text(encoding='utf-8-sig').splitlines():
        parts=[x.strip() for x in line.strip().split('|')]
        if len(parts)<5 or 'via cross-type' in parts[1]: continue
        name=re.match(r'\*\*([\w-]+)\*\*', parts[1])
        if name: result[name[1]]={'keywords':[s.strip() for s in parts[2].split(',')], 'description':parts[3]}
    return result


def file_entry(path, root):
    entry={'path':path.relative_to(root).as_posix(),'size_bytes':native_path(path).stat().st_size,'sha256':sha(path)}
    try:
        if path.suffix.lower() in IMAGE_EXT:
            from PIL import Image
            Image.MAX_IMAGE_PIXELS = 230_000_000
            with Image.open(native_path(path)) as im:
                entry.update(width=im.width,height=im.height,pages=getattr(im,'n_frames',1)); im.verify()
        elif path.suffix.lower()=='.pdf':
            import fitz
            with fitz.open(native_path(path)) as doc:
                if not len(doc): raise ValueError('Empty PDF')
                entry.update(pages=len(doc), page_sizes_pt=[[p.rect.width,p.rect.height] for p in doc])
        elif path.suffix.lower()=='.svg':
            import xml.etree.ElementTree as ET
            svg=ET.parse(native_path(path)).getroot()
            entry.update(pages=1,svg_geometry={k:svg.attrib.get(k) for k in ['width','height','viewBox']})
    except Exception as exc:
        entry['inspection_error']=f'{type(exc).__name__}: {exc}'
    return entry


def runtime_skill(runtime=None, skill=None):
    """No silent .agents fallback: a caller must name the runtime or its exact local root."""
    if skill is not None:
        skill=Path(skill).as_posix().rstrip('/')
        matches=[key for key,value in RUNTIME_SKILLS.items() if value==skill]
        if len(matches)!=1: raise ValueError('skill-root must be a project Codex/Claude academic root')
        if runtime is not None and runtime!=matches[0]: raise ValueError('runtime / skill-root mismatch')
        runtime=matches[0]
    if runtime not in RUNTIME_SKILLS: raise ValueError('Explicit --runtime codex|claude required')
    return runtime,RUNTIME_SKILLS[runtime]


def build_index(root, skill=None, runtime=None):
    runtime,skill=runtime_skill(runtime,skill)
    from workspace_context import shared_context
    context = shared_context(root, runtime)
    if context:
        drift = context.check_shared()
        if drift['status'] != 'PASS':
            raise ValueError('共享资源已变化，须先核验依赖: ' + json.dumps(drift['changed_resources'], ensure_ascii=False))
        root = context.template_root
    root=Path(root).resolve(); skill_dir=safe(root,skill)
    catalog=parse_map(skill_dir/'references/directory-map.md')
    atlas_dir=skill_dir/'assets/figure-atlas'; figure_dir=skill_dir/'assets/figures'
    if not atlas_dir.is_dir() or not figure_dir.is_dir(): raise ValueError('Missing atlas/figures directory')
    inventory=[file_entry(p,root) for base in [atlas_dir,figure_dir] for p in files(base)]
    by_path={x['path']:x for x in inventory}
    families=[]
    for directory in sorted(p for p in figure_dir.iterdir() if p.is_dir() and p.name!='__pycache__'):
        members=files(directory); info=catalog.get(directory.name,{})
        scripts=[by_path[p.relative_to(root).as_posix()] for p in members if p.suffix.lower() in SCRIPT_EXT]
        outputs=[by_path[p.relative_to(root).as_posix()] for p in members if p.suffix.lower() in OUTPUT_EXT]
        shape, roles='unknown',[]
        for matches,s,r in SHAPES:
            if any(m in directory.name for m in matches): shape,roles=s,r;break
        keywords=info.get('keywords',[])
        chinese=next((x for x in keywords if re.search('[\u3400-\u9fff]',x)), 'unknown')
        families.append({'figure_type':directory.name,'directory':directory.relative_to(root).as_posix(),
          'chinese_name':chinese,'english_name':re.sub(r'(?<=[a-z])(?=[A-Z])',' ',directory.name),
          'keywords':keywords, 'scientific_question_hint':info.get('description','unknown'),
          'data_structure_hint':shape,'evidence_roles':roles,'production_scripts':scripts,'outputs':outputs,
          'statistics_reports':[by_path[p.relative_to(root).as_posix()] for p in members if p.name.endswith('.stats.json')],
          'readmes':[p.relative_to(root).as_posix() for p in members if 'readme' in p.name.lower()],
          'has_statistics_report':any(p.name.endswith('.stats.json') for p in members),
          'has_readme':any('readme' in p.name.lower() for p in members),
          'empty_directory':not bool(members),
          'missing_output':bool(scripts) and not bool(outputs),
          'source_output_links':[{'source':s['path'],'outputs':[o['path'] for o in outputs if Path(o['path']).stem==Path(s['path']).stem], 'basis':'same stem; requires source inspection'} for s in scripts],
          'atlas_references':[(atlas_dir/n).relative_to(root).as_posix() for n in ATLAS_HINTS.get(directory.name,[]) if (atlas_dir/n).is_file()],
          'recommended_adaptation':'visual_adapt' if scripts else 'needs_review',
          'cross_type_inherit_candidates':[], 'review_status':'needs_review',
          'mapping_basis':'directory-map + filename search hints; not a visual similarity classifier',
          'runnable_status':'not_executed', 'placeholder_directory':not bool(scripts)})
    for f in families:
        f['cross_type_inherit_candidates']=[g['figure_type'] for g in families if g['figure_type']!=f['figure_type'] and g['production_scripts'] and g['data_structure_hint']==f['data_structure_hint'] and g['data_structure_hint']!='unknown']
    atlas=[]
    for p in files(atlas_dir):
        if p.suffix.lower() not in OUTPUT_EXT: continue
        entry=dict(by_path[p.relative_to(root).as_posix()]); linked=[f for f in families if entry['path'] in f['atlas_references']]
        entry.update(filename=p.name,figure_types=[f['figure_type'] for f in linked],
          visual_keywords=sorted(set(k for f in linked for k in f['keywords'])),
          data_structures=sorted(set(f['data_structure_hint'] for f in linked)) or ['unknown'],
          scientific_questions=[f['scientific_question_hint'] for f in linked] or ['overview / needs_review'],
          review_status='needs_review')
        atlas.append(entry)
    map_record=file_entry(skill_dir/'references/directory-map.md',root)
    return {'schema_version':'2.0','runtime':runtime,'skill_root':skill,'inventory':inventory,'directory_map':map_record,
      'scan_digest':digest({'inventory':inventory,'directory_map':map_record}),
      'counts':{'atlas_images':len(atlas),'directories':len(families),'production_families':sum(bool(x['production_scripts']) for x in families),
                'scripts':sum(len(x['production_scripts']) for x in families),'inventory_files':len(inventory)},
      'atlas':atlas,'families':families,'ignored':['__pycache__','*.pyc'],
      'inspection_errors':[{'path':e['path'],'error':e['inspection_error']} for e in inventory if 'inspection_error' in e],
      'visual_units':sum(e.get('pages',0) for e in inventory if Path(e['path']).suffix.lower() in OUTPUT_EXT),
      'assurance':'Inventory hashes and image decode only. A human/agent must actually open candidate images and read source.'}


def sync_report(root):
    from workspace_context import shared_context
    context = shared_context(root)
    if context:
        root = context.template_root
    root=Path(root).resolve(); maps=[]
    for side in ['.agents','.claude']:
        base=root/side/'skills/academic-figure-skill'
        if not base.is_dir(): raise ValueError(f'Missing mirror: {base}')
        maps.append({p.relative_to(base).as_posix():sha(p) for p in files(base)})
    differences=[k for k in sorted(maps[0].keys()|maps[1].keys()) if maps[0].get(k)!=maps[1].get(k)]
    return {'status':'PASS' if not differences else 'FAIL','counts':[len(m) for m in maps],'differences':differences,'ignored':['__pycache__','*.pyc']}


def contact_sheets(root, index, output):
    """Render ALL visual pages/frames, map every sheet cell, leave review fields blank."""
    from PIL import Image, ImageDraw, ImageFont, ImageOps
    Image.MAX_IMAGE_PIXELS = 230_000_000
    root=Path(root).resolve(); output=Path(output);output.mkdir(parents=True,exist_ok=True)
    entries=[x for x in index['inventory'] if Path(x['path']).suffix.lower() in OUTPUT_EXT]
    units=[];errors=[]
    preview_dir=output/'previews';preview_dir.mkdir(exist_ok=True)
    for asset_no,item in enumerate(entries,1):
        from workspace_context import resource_path
        raw=resource_path(root,item['path'],index['runtime']);ext=raw.suffix.lower()
        try:
            if item.get('inspection_error'):raise ValueError(item['inspection_error'])
            for page in range(item['pages']):
                if ext in IMAGE_EXT:
                    with Image.open(native_path(raw)) as im:
                        im.seek(page);im.thumbnail((1800,1400),reducing_gap=3.0);preview=im.convert('RGB')
                elif ext=='.pdf':
                    import fitz
                    with fitz.open(native_path(raw)) as doc:
                        p=doc[page];scale=min(1800/p.rect.width,1400/p.rect.height)
                        pix=p.get_pixmap(matrix=fitz.Matrix(scale,scale),alpha=False)
                        preview=Image.frombytes('RGB',[pix.width,pix.height],pix.samples)
                else:
                    import fitz
                    # MuPDF handles SVG without requiring a second rendering dependency.
                    with fitz.open(native_path(raw)) as svg:
                        with fitz.open('pdf',svg.convert_to_pdf()) as doc:
                            p=doc[0];scale=min(1800/p.rect.width,1400/p.rect.height)
                            pix=p.get_pixmap(matrix=fitz.Matrix(scale,scale),alpha=False)
                            preview=Image.frombytes('RGB',[pix.width,pix.height],pix.samples)
                dst=preview_dir/f'asset_{asset_no:03d}_page_{page+1:03d}.png';preview.save(dst)
                units.append({'unit_id':f'{item["path"]}#page={page+1}','asset_path':item['path'],'asset_sha256':item['sha256'],'page':page+1,
                    'preview_path':dst.relative_to(root).as_posix(),'preview_sha256':sha(dst)})
        except Exception as exc:errors.append({'path':item['path'],'error':f'{type(exc).__name__}: {exc}'})
    pages=[];font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',18) if Path('C:/Windows/Fonts/arial.ttf').exists() else ImageFont.load_default()
    for i in range(0,len(units),6):
        chunk=units[i:i+6]; sheet=Image.new('RGB',(1800,1560),'#eeeeee');draw=ImageDraw.Draw(sheet)
        for j,item in enumerate(chunk):
            x=(j%2)*900;y=(j//2)*520
            with Image.open(safe(root,item['preview_path'])) as im:
                im.thumbnail((880,465), reducing_gap=3.0)
                thumb=im.convert('RGB')
                sheet.paste(thumb,(x+(900-thumb.width)//2,y+48+(465-thumb.height)//2))
            label=item['asset_path'].split('/assets/',1)[-1]
            draw.text((x+8,y+5),f'{i+j+1}: {label[:88]}',font=font,fill='black')
            draw.text((x+8,y+26),f'page {item["page"]} | full path and source hash in manifest',font=font,fill='#555555')
            item.update(sheet_cell=j+1,sheet_bbox=[x,y,x+900,y+520])
        path=output/f'assets_{i//6+1:02d}.png';sheet.save(path)
        for item in chunk:item['sheet_path']=path.relative_to(root).as_posix()
        pages.append({'path':path.relative_to(root).as_posix(),'sha256':sha(path),'assets':[x['asset_path'] for x in chunk],'unit_ids':[x['unit_id'] for x in chunk]})
    manifest={'schema_version':'2.0','runtime':index['runtime'],'skill_root':index['skill_root'],'scan_digest':index['scan_digest'],
        'pages':pages,'units':units,'errors':errors,'expected_units':index['visual_units'],
        'assurance':'Generated overview covers every page/frame; NOT a viewing receipt. Zoom originals/crops for details.'}
    write_json(output/'contact_manifest.json',manifest)
    review_path=output/'gallery_review.json'
    if not review_path.exists():
        write_json(review_path,{'schema_version':'2.0','runtime':index['runtime'],'scan_digest':index['scan_digest'],
            'contact_manifest':(output/'contact_manifest.json').relative_to(root).as_posix(),
            'contact_manifest_sha256':sha(output/'contact_manifest.json'),
            'pages':[{'path':p['path'],'sha256':p['sha256'],'reviewed':False,'tool_ref':'','observation':''} for p in pages],
            'asset_observations':[{'path':e['path'],'sha256':e['sha256'],'data_fit':'','visual_features':'','limitations':''} for e in entries],
            'assurance':'Blank scaffold. Agent fills observations only AFTER actual image viewing; reuse only for matching asset version.'})
    return pages


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--project-root',type=Path,default=Path('.'))
    p.add_argument('--runtime',choices=RUNTIME_SKILLS,required=True);p.add_argument('--skill-root');p.add_argument('--output',type=Path,default=Path('求解/academic_figure_asset_index.json'))
    p.add_argument('--contact-dir',type=Path);p.add_argument('--check-sync',action='store_true');p.add_argument('--report',type=Path)
    a=p.parse_args();root=a.project_root.resolve()
    try:
        index=build_index(root,a.skill_root,a.runtime);write_json(safe(root,str(a.output)),index)
        report={'status':'FAIL' if index['inspection_errors'] else 'PASS','counts':index['counts'],'scan_digest':index['scan_digest'],'inspection_errors':index['inspection_errors']}
        if a.contact_dir: report['contact_pages']=len(contact_sheets(root,index,safe(root,str(a.contact_dir))))
        if a.contact_dir:
            contacts=json.loads((safe(root,str(a.contact_dir))/'contact_manifest.json').read_text(encoding='utf-8'))
            report['render_errors']=contacts['errors']
            if contacts['errors'] or len(contacts['units'])!=index['visual_units']:report['status']='FAIL'
        if a.check_sync:
            report['sync']=sync_report(root)
            if report['sync']['status']!='PASS':report['status']='FAIL'
    except Exception as e: report={'status':'FAIL','error':f'{type(e).__name__}: {e}'}
    if a.report: write_json(safe(root,str(a.report)),report)
    print(json.dumps(report,ensure_ascii=False,indent=2));raise SystemExit(0 if report['status']=='PASS' else 1)

if __name__=='__main__': main()
