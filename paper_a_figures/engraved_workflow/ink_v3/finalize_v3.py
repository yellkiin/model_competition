#!/usr/bin/env python3
"""Apply the reviewed font and alignment corrections after ink_v2 geometry.

Native text uses real paper fonts; equations use Computer Modern vector paths.
Missing native fonts cause an error rather than a silent substitution.
"""
from __future__ import annotations
import argparse
import gzip
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
SVG='http://www.w3.org/2000/svg'
XML='http://www.w3.org/XML/1998/namespace'
ET.register_namespace('',SVG)
NS={'s':SVG}
PALETTES=('mono','qinglu','qianjiang','yanlan')


def tag(name):
    return '{'+SVG+'}'+name


def find(root,ident):
    node=root.find('.//*[@id="'+ident+'"]')
    if node is None:
        raise ValueError(f'Missing SVG object: {ident}')
    return node


def set_attrs(node,**attrs):
    for key,value in attrs.items():
        key='class' if key=='class_' else key.replace('_','-')
        node.set(key,str(value))


def set_plain_text(node,value,**attrs):
    for child in list(node):node.remove(child)
    node.text=value
    set_attrs(node,**attrs)


def ensure_font_style(root):
    defs=root.find('s:defs',NS)
    if defs is None:raise ValueError('Missing SVG defs')
    old=defs.find('.//*[@id="paper-font-fix"]')
    if old is not None:defs.remove(old)
    # Removing comments also makes the small outline-color resolver unambiguous.
    for style in defs.findall('s:style',NS):
        style.text=re.sub(r'/\*.*?\*/','',style.text or '',flags=re.S)
    style=ET.SubElement(defs,tag('style'),{'id':'paper-font-fix'})
    style.text="text, .serif, .math {font-family:'Times New Roman','SimSun',serif;}"


def ensure_graph_definition(root):
    node=root.find('.//*[@id="graph-definition"]')
    if node is None:node=ET.SubElement(find(root,'joint-decision-v3'),tag('text'),{'id':'graph-definition'})
    set_plain_text(node,'G = (T ∪ O, E)',x=914,y=380,font_size=32,text_anchor='end',class_='math')


def normalize_b(root):
    for path in find(root,'bipartite-example').iter(tag('path')):
        if 'structure-hatch' in path.get('style',''):
            path.attrib.pop('style',None)
            break
    set_attrs(find(root,'text-024'),class_='serif')
    targets={('430','1084'):'text-031',('1677','741'):'text-063',('2572','453'):'text-114'}
    found=set()
    for rect in root.iter(tag('rect')):
        key=(rect.get('x',''),rect.get('y',''))
        if key in targets:
            rect.set('class','paper')
            rect.attrib.pop('style',None)
            found.add(key)
    if set(targets)-found:raise ValueError(f'Missing B rectangles: {sorted(set(targets)-found)}')
    for label in targets.values():set_attrs(find(root,label),class_='math')
    for node in root.iter(tag('text')):
        if ''.join(node.itertext()).strip() in {'候选示意：B 迁至 k₂','候选示意：B 迁至 k2'}:
            set_plain_text(node,'候选示意：迁移 B',font_size=29,class_='bold')


def set_core_label(node,index,x):
    for child in list(node):node.remove(child)
    set_attrs(node,x=x,y=424,font_size=30,text_anchor='middle',class_='bold')
    node.text='核心 '
    ET.SubElement(node,tag('tspan'),{'class':'math'}).text='k'
    ET.SubElement(node,tag('tspan'),{'baseline-shift':'sub','font-size':'70%','class':'math'}).text=str(index)
    node.set('{'+XML+'}space','preserve')
    node.set('data-tight-text','true')


def align_execution_labels(root):
    set_core_label(find(root,'text-104'),1,2272)
    set_core_label(find(root,'text-113'),2,2687)
    # Keep each label centered on its tensor, but place both inside the blank
    # interior of its transfer arc. Do not merely hide an intersection by halo.
    set_plain_text(find(root,'text-122'),'COPY_OUT',x=2225,y=946,font_size=22,text_anchor='middle',class_='serif halo')
    set_plain_text(find(root,'text-123'),'COPY_IN',x=2788,y=946,font_size=22,text_anchor='middle',class_='serif halo')
    shifts=[('translate(2190,996)','translate(2225,996)','copy-out-tensor-v3'),
            ('translate(2821,1001)','translate(2788,1001)','copy-in-tensor-v3')]
    for node in root.iter(tag('g')):
        transform=node.get('transform','')
        for old,new,ident in shifts:
            if old in transform:
                node.set('transform',transform.replace(old,new))
                node.set('id',ident)


def fix_makespan_formula(root):
    node=find(root,'makespan-v3')
    for child in list(node):node.remove(child)
    set_attrs(node,x=2497,y=1458,font_size=36,text_anchor='middle',class_='math')
    node.text='C'
    node.set('{'+XML+'}space','preserve')
    node.set('data-tight-text','true')
    ET.SubElement(node,tag('tspan'),{'baseline-shift':'sub','font-size':'70%'}).text='q'
    ET.SubElement(node,tag('tspan')).text='(y) = '
    ET.SubElement(node,tag('tspan'),{'font-style':'normal'}).text='max'
    ET.SubElement(node,tag('tspan'),{'baseline-shift':'sub','font-size':'70%'}).text='j'
    ET.SubElement(node,tag('tspan')).text=' f'
    ET.SubElement(node,tag('tspan'),{'baseline-shift':'sub','font-size':'70%'}).text='j'


def remove_bottom_q3_note(root):
    for parent in root.iter():
        for child in list(parent):
            if child.tag==tag('text') and '固定同一方案' in ''.join(child.itertext()):parent.remove(child)
    for node in root.iter(tag('text')):
        if ''.join(node.itertext()).strip().startswith('输出：调度方案'):node.set('y','1771')


def write_svg(root,svg):
    ET.indent(root,space='  ')
    for node in root.findall('.//*[@data-tight-text="true"]'):
        for child in list(node):child.tail=''
    ET.ElementTree(root).write(svg,encoding='utf-8',xml_declaration=True)
    with svg.with_suffix('.svgz').open('wb') as raw:
        with gzip.GzipFile(fileobj=raw,mode='wb',mtime=0) as z:z.write(svg.read_bytes())


def export(svg,out_dir,width):
    inkscape=shutil.which('inkscape')
    if not inkscape:raise RuntimeError('Final SVG is ready; install Inkscape to export PDF and PNG.')
    exports=out_dir/'exports'
    exports.mkdir(parents=True,exist_ok=True)
    jobs=[(exports/f'{svg.stem}.pdf',['--export-text-to-path']),
          (exports/f'{svg.stem}.png',[f'--export-width={width}']),
          (exports/f'{svg.stem}_preview.png',['--export-width=1800'])]
    for target,extra in jobs:
        run=subprocess.run([inkscape,str(svg),f'--export-filename={target}','--export-area-page',
                            '--export-background=white','--export-background-opacity=1',*extra],
                           stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=180)
        if run.returncode:raise RuntimeError(run.stderr)


def update_build_info(out_dir,palettes):
    path=out_dir/'BUILD_INFO.json'
    data=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    data.update({'finalizer':'finalize_v3.py','palettes':palettes,'bottom_q3_note_removed':True,
                 'b_highlight_removed':True,'b_operation_label':'迁移 B',
                 'font_alignment':'Verified paper fonts: SimSun / Times New Roman / Computer Modern',
                 'copy_label_centers':{'COPY_OUT':2225,'COPY_IN':2788},
                 'alignment_fixes':['graph definition','core labels','COPY labels and tensors clear of arcs','makespan formula']})
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def native_outline(svg):
    from outline_native import NativeFonts,outline
    outline(svg,NativeFonts(Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'))


def finalize(svg,out_dir,do_export,width):
    root=ET.parse(svg).getroot()
    if root.get('data-text-outlined')=='true':
        if do_export:export(svg,out_dir,width)
        return
    if root.find('.//*[@data-math-fonts]') is None:
        ensure_font_style(root)
        ensure_graph_definition(root)
        normalize_b(root)
        align_execution_labels(root)
        fix_makespan_formula(root)
        remove_bottom_q3_note(root)
        from math_layout import apply_math
        apply_math(root,out_dir/'assets'/'math_layout.json')
        write_svg(root,svg)
    if do_export:
        native_outline(svg)
        export(svg,out_dir,width)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=HERE)
    parser.add_argument('--palettes',nargs='+',choices=PALETTES,default=['mono','qinglu'])
    parser.add_argument('--png-width',type=int,default=6000)
    parser.add_argument('--no-export',action='store_true')
    args=parser.parse_args()
    if args.png_width<1200:parser.error('png-width must be at least 1200')
    for name in args.palettes:
        svg=args.out/'assets'/f'workflow_{name}_v3.svg'
        if not svg.exists():raise FileNotFoundError(f'Run build.py --svg-only first: {svg}')
        finalize(svg,args.out,not args.no_export,args.png_width)
        print(svg)
    update_build_info(args.out,args.palettes)

if __name__=='__main__':main()
