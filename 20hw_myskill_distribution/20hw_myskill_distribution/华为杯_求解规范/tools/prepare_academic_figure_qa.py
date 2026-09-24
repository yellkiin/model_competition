#!/usr/bin/env python3
"""Prepare current reference/result previews and an UNREVIEWED QA record."""
from __future__ import annotations

# Shared execution is explicit; direct legacy/maintenance CLIs must declare mode.
if __name__ == "__main__":
    import sys as _workflow_sys
    _workflow_sys.dont_write_bytecode = True
    from workspace_cli import require_cli_mode
    require_cli_mode(__file__)

import argparse,json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from build_academic_figure_asset_index import safe,sha,write_json,runtime_skill
from prepare_academic_figure_review import plan_figures,sidecar_path,figure_contract_digest
from workspace_context import resource_path
from filesystem_paths import native_path

def raster(path):
    if path.suffix.lower() in {'.pdf','.svg'}:
        import pymupdf as fitz
        with fitz.open(path) as raw:
            doc=fitz.open('pdf',raw.convert_to_pdf()) if path.suffix.lower()=='.svg' else raw
            pages=[]
            for page in doc:
                factor=min(1800/page.rect.width,1400/page.rect.height)
                pix=page.get_pixmap(matrix=fitz.Matrix(factor,factor),alpha=False)
                pages.append(Image.frombytes('RGB',[pix.width,pix.height],pix.samples))
            if doc is not raw:doc.close()
            return pages
    with Image.open(path) as raw:
        pages=[]
        for n in range(getattr(raw,'n_frames',1)):
            raw.seek(n);pages.append(raw.convert('RGB').copy())
        return pages

def prepare_qa(root,plan_path,figure_id,runtime):
    root=Path(root).resolve();plan_path=safe(root,str(plan_path))
    plan=json.loads(plan_path.read_text(encoding='utf-8-sig'));refs=json.loads(sidecar_path(plan_path).read_text(encoding='utf-8-sig'))
    resolved,_=runtime_skill(runtime,refs['skill_root'])
    if resolved!=refs['runtime']:raise ValueError('Runtime mismatch')
    f=next(x for x in plan_figures(plan) if x['figure_id']==figure_id)
    rec=next(x for x in refs['figures'] if x['figure_id']==figure_id)
    png=safe(root,f['outputs']['preview']);vector=safe(root,f['outputs']['vector']);script=safe(root,f['script'])
    qa_path=safe(root,f['qa_report']);out=qa_path.parent/(figure_id+'_review');out.mkdir(parents=True,exist_ok=True)
    rendered=raster(vector)
    if len(rendered)!=1:raise ValueError('One Figure must have a single vector page; split multipage output into distinct Figure IDs')
    pdf_preview=out/'vector_render.png';rendered[0].save(pdf_preview)
    gray=out/'grayscale.png';raster(png)[0].convert('L').save(gray)
    ref_paths=list(dict.fromkeys(raw for p in rec['panel_plan'] for raw in [p['atlas_reference'],p['source_example_path']]))
    tiles=[]
    for raw in ref_paths:
        for n,im in enumerate(raster(native_path(resource_path(root,raw,runtime))),1):tiles.append((Path(raw).name+f' / p{n}',im))
    tiles.append(('CURRENT / '+figure_id,raster(png)[0]))
    cols=min(3,len(tiles));width,height=900,850
    sheet=Image.new('RGB',(width*cols,height*((len(tiles)+cols-1)//cols)),'#eeeeee');draw=ImageDraw.Draw(sheet)
    font_path=Path('C:/Windows/Fonts/msyh.ttc');font=ImageFont.truetype(str(font_path),22) if font_path.is_file() else ImageFont.load_default()
    for i,(label,im) in enumerate(tiles):
        x=i%cols*width;y=i//cols*height;im.thumbnail((width-32,height-76))
        draw.text((x+16,y+12),label,font=font,fill='#222222');sheet.paste(im,(x+(width-im.width)//2,y+64+(height-76-im.height)//2))
    comparison=out/'reference_vs_current.png';sheet.save(comparison)
    with Image.open(png) as im:dpi=min(im.info.get('dpi',(0,0)))
    checks=[{'name':'PNG >=300 dpi','status':'PASS' if dpi>=299 else 'FAIL','value':dpi}]
    if vector.suffix.lower()=='.pdf':
        import pymupdf as fitz
        with fitz.open(vector) as doc:
            mm=doc[0].rect.width/72*25.4
            checks.extend([{'name':'PDF target width','status':'PASS' if abs(mm-rec['target_width_mm'])<0.5 else 'FAIL','width_mm':mm},
                           {'name':'Vector drawing primitives present','status':'PASS' if doc[0].get_drawings() else 'FAIL'}])
    relative=lambda p:p.relative_to(root).as_posix()
    value={'status':'REVIEW_REQUIRED','automated_checks':checks,
        'contract_sha256':figure_contract_digest(f,rec),
        'artifact_sha256':{'script':sha(script),'png':sha(png),'vector':sha(vector)},
        'visual_review':{'reviewed':False,'tool_ref':'','observation':'','png_sha256':sha(png),
          'pdf_render_path':relative(pdf_preview),'pdf_render_sha256':sha(pdf_preview),'grayscale_path':relative(gray),'grayscale_sha256':sha(gray)},
        'reference_comparison':{'path':relative(comparison),'sha256':sha(comparison),'final_png_sha256':sha(png),
          'reference_hashes':{raw:sha(resource_path(root,raw,runtime)) for raw in ref_paths},'reviewed':False,'tool_ref':'','observation':''},
        'review_dimensions':{k:{'status':'REVIEW_REQUIRED','observation':''} for k in ['scientific_validity','reference_fidelity','print_readability']},
        'assurance':'This tool prepares previews and technical checks only. It never claims actual viewing, aesthetic approval or scientific validity.'}
    from workspace_resources import dependencies
    value['resource_dependencies']=dependencies(root,runtime,'academic')
    write_json(qa_path,value)
    return value

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--project-root',type=Path,default=Path('.'))
    p.add_argument('--plan',type=Path,required=True);p.add_argument('--figure-id',required=True)
    p.add_argument('--runtime',choices=['codex','claude'],required=True);p.add_argument('--replace-review',action='store_true')
    a=p.parse_args();root=a.project_root.resolve()
    try:
        plan=json.loads(safe(root,str(a.plan)).read_text(encoding='utf-8-sig'));f=next(x for x in plan_figures(plan) if x['figure_id']==a.figure_id)
        if safe(root,f['qa_report']).exists() and not a.replace_review:raise ValueError('Existing QA retained; back it up and use --replace-review after rerendering')
        result=prepare_qa(root,a.plan,a.figure_id,a.runtime)
        print(json.dumps({'status':result['status'],'comparison':result['reference_comparison']['path']},ensure_ascii=False));return 0
    except Exception as exc:print(json.dumps({'status':'FAIL','error':str(exc)},ensure_ascii=False));return 1
if __name__=='__main__':raise SystemExit(main())
