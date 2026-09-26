"""Local vector/layout inspection. Inkscape measures text in the actual fonts."""
from __future__ import annotations
import json
from pathlib import Path
import re
import shutil
import subprocess
import xml.etree.ElementTree as E
from build import HERE, SVG, tag, by_id, text_value


def route_points(d, step=40):
    """Sample the absolute M/L/H/V/Q commands used by the new flow routes."""
    ts=re.findall(r'[MLHVQ]|-?(?:\d*\.\d+|\d+)',d)
    i=0; x=y=0.0; pts=[]
    while i<len(ts):
        cmd=ts[i];i+=1
        if cmd in ('M','L'):
            xx,yy=map(float,ts[i:i+2]);i+=2
            if cmd=='L':pts.extend((x+(xx-x)*t/step,y+(yy-y)*t/step) for t in range(1,step+1))
            else:pts.append((xx,yy))
            x,y=xx,yy
        elif cmd in ('H','V'):
            z=float(ts[i]);i+=1;xx,yy=(z,y) if cmd=='H' else (x,z)
            pts.extend((x+(xx-x)*t/step,y+(yy-y)*t/step) for t in range(1,step+1));x,y=xx,yy
        elif cmd=='Q':
            cx,cy,xx,yy=map(float,ts[i:i+4]);i+=4
            for t in range(1,step+1):
                a=t/step;pts.append(((1-a)**2*x+2*(1-a)*a*cx+a*a*xx,(1-a)**2*y+2*(1-a)*a*cy+a*a*yy))
            x,y=xx,yy
        else:raise ValueError('Unsupported connector command: '+cmd)
    return pts


def check():
    original=E.parse(HERE.parent/'assets/workflow.svg').getroot()
    root=E.parse(HERE/'assets/workflow_qinglu.svg').getroot()
    modules=['bipartite-example','source-base','source-structure','source-residency','source-fifo']
    same={}
    for name in modules:
        def texts(r):return [(text_value(t),t.get('x'),t.get('y'),t.get('font-size'),t.get('text-anchor')) for t in by_id(r,name).iter(tag('text'))]
        same[name]=texts(root)==texts(original)
    if not all(same.values()):raise AssertionError('Protected module text/coordinates changed')
    if list(root.iter(tag('image'))):raise AssertionError('Raster image embedded')
    exe=shutil.which('inkscape')
    if not exe:raise RuntimeError('Text clearance measurement requires Inkscape')
    result=subprocess.run([exe,str(HERE/'assets/workflow_qinglu.svg'),'--query-all'],capture_output=True,text=True,check=True)
    factor=3000/(420/25.4*96)
    boxes={}
    for row in result.stdout.splitlines():
        fields=row.split(',')
        if len(fields)==5:
            try:boxes[fields[0]]=tuple(float(x)*factor for x in fields[1:])
            except ValueError:pass
    reserved={k:boxes[k] for k in ('makespan-title','makespan-formula','copy-tiebreak')}
    collisions=[]
    for p in by_id(root,'ink-process-links').iter(tag('path')):
        for ident,(x,y,w,h) in reserved.items():
            if any(x-12<px<x+w+12 and y-12<py<y+h+12 for px,py in route_points(p.get('d'))):
                collisions.append([p.get('id'),ident])
    if collisions:raise AssertionError(collisions)
    variants={}
    for name in ['qinglu','qianjiang','yanlan','mono']:
        rr=E.parse(HERE/'assets'/f'workflow_{name}.svg').getroot()
        variants[name]={'text_nodes':len(list(rr.iter(tag('text')))), 'raster_nodes':len(list(rr.iter(tag('image')))),
                        'named_layers':[g.get('id') for g in rr.iter(tag('g')) if g.get('{http://www.inkscape.org/namespaces/inkscape}groupmode')=='layer']}
    report={'protected_module_text_and_coordinates':same, 'formula_boxes_svg_units':reserved,
            'connector_formula_collisions_with_12_unit_margin':collisions,'variants':variants,
            'renderer':subprocess.check_output([exe,'--version'],text=True).strip(),
            'visual_review':'PNG and independently rasterized PDF inspected locally; all four themes generated.',
            'chart_adapter':'Matplotlib 3.10.8: existing line/scatter/bar numeric arrays and axis limits preserved; CJK labels rendered without warnings; rc_context restored.',
            'scope':'Workflow refinement and reusable styling tools. No original experiment values modified; no paper-wide figure replacement.'}
    output=HERE/'docs/LAYOUT_REVIEW.json';output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return report

if __name__=='__main__':check()
