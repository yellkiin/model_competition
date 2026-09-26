#!/usr/bin/env python3
"""Build the editable SVG and optional vector PDF / high-resolution PNG locally."""
from __future__ import annotations
import argparse, json, shutil, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def command(args: list[str]) -> None:
    subprocess.run(args,check=True,cwd=ROOT,timeout=180)

def main() -> None:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--svg-only',action='store_true',help='Python standard library only')
    ap.add_argument('--png-width',type=int,default=6000)
    args=ap.parse_args()
    if not 1500<=args.png_width<=12000:ap.error('--png-width must be between 1500 and 12000')
    command([sys.executable,'src/draw_workflow.py'])
    command([sys.executable,'src/draw_style_guide.py'])
    command([sys.executable,'tests/test_workflow.py'])
    if args.svg_only:return
    exe=shutil.which('inkscape')
    if not exe:raise SystemExit('Inkscape CLI is required for exports. Install Inkscape and Noto CJK fonts, or use --svg-only.')
    out=ROOT/'exports';out.mkdir(exist_ok=True)
    command([exe,str(ROOT/'assets/workflow.svg'),'--export-type=pdf',f'--export-filename={out / "workflow.pdf"}'])
    command([exe,str(ROOT/'assets/workflow.svg'),'--export-type=png',f'--export-width={args.png_width}',f'--export-filename={out / "workflow.png"}'])
    command([exe,str(ROOT/'assets/workflow.svg'),'--export-type=png','--export-width=1800',f'--export-filename={out / "workflow_preview.png"}'])
    command([exe,str(ROOT/'assets/style_guide.svg'),'--export-type=pdf',f'--export-filename={out / "style_guide.pdf"}'])
    # Query the SVG objects using the same renderer used for production exports.
    r=subprocess.run([exe,str(ROOT/'assets/workflow.svg'),'--query-all'],capture_output=True,text=True,check=True,timeout=60)
    outside=[];count=0
    # Inkscape query coordinates use CSS px (96 dpi), not viewBox units.
    canvas_w,canvas_h=420*96/25.4,296.8*96/25.4
    for line in r.stdout.splitlines():
        cols=line.split(',')
        if len(cols)!=5:continue
        try:x,y,w,h=map(float,cols[1:])
        except ValueError:continue
        count+=1
        if x < -2 or y < -2 or x+w>canvas_w+2 or y+h>canvas_h+2:outside.append(cols)
    report={'renderer':subprocess.check_output([exe,'--version'],text=True).strip(),'canvas_css_px':[canvas_w,canvas_h],'queried_objects':count,'out_of_canvas':outside,'manual_review_required':'Inspect the full PNG and a PDF render at reading size; geometric checks alone do not establish good layout.'}
    (out/'build_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    if outside:raise SystemExit('Some SVG objects exceed the canvas; inspect exports/build_report.json.')
    print('Built assets/workflow.svg and exports/{workflow.pdf,workflow.png,workflow_preview.png}.')

if __name__=='__main__':main()
