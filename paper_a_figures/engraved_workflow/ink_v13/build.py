#!/usr/bin/env python3
"""V13: two columns, three rows; larger native outlined labels in four palettes.

Retains the published V11 artwork and font outlines. Portable assets require no
installed fonts. Editable assets retain the original SimSun / Times New Roman
text and Computer Modern mathematical outlines. Exports use Inkscape.
"""
from __future__ import annotations
import argparse
import copy
import gzip
import os
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET
import pymupdf
from spacing_joint import space_joint
from spacing_hardware import space_hardware
from labels_large import enlarge_pool_labels
from pipeline_labels import replace_pipeline_labels

HERE = Path(__file__).resolve().parent
SVG = 'http://www.w3.org/2000/svg'
NS = {'s': SVG}
ET.register_namespace('', SVG)
ET.register_namespace('inkscape', 'http://www.inkscape.org/namespaces/inkscape')
THEMES = ('qinglu', 'qianjiang', 'yanlan', 'mono')
WIDTH, HEIGHT, TOP = 3150, 2000, 235


def find(root, ident):
    node = root.find(".//*[@id='" + ident + "']")
    if node is None:
        raise ValueError('Missing object: ' + ident)
    return node


def shift(node, dx, dy):
    node.set('transform', f'translate({dx:g},{dy:g}) ' + node.get('transform', ''))


def path(root, ident, d):
    find(root, ident).set('d', d)


def scale_labels(root, reference):
    # Grow whole mixed text/math groups together, preserving their internal
    # spacing. Grow normal labels around their original alignment anchors.
    parents = {c:p for p in reference.iter() for c in p}
    handled = set()
    for label in reference.findall('.//s:text', NS):
        node = label
        p = parents.get(node)
        while p is not None and p.tag.endswith('g') and p.get('data-tex'):
            node = p
            p = parents.get(node)
        ident = node.get('id')
        # Anonymous mixed groups are matched by their unique mathematical text.
        if node is not label:
            key = node.get('data-label')
            matches = [n for n in root.iter() if n.get('data-label') == key]
            if len(matches) != 1 or key in handled:
                continue
            target = matches[0]
            handled.add(key)
            target.set('transform', target.get('transform', '') + ' scale(1.2412)')
            continue
        if not ident:
            continue
        target = find(root, ident)
        size = float(label.get('font-size', 28))
        factor = 1.18 if size >= 40 else (1.27 if size <= 27 else 1.20)
        # Cache vertical cells have a fixed 32-unit pitch.
        if ident.startswith('l2-hit-cell-'):
            factor = 1.16
        if ident in ('copy-out-label','copy-in-label','right-copy-out-label-v8','right-copy-in-label-v8'):
            factor = 1.14  # adjacent COPY labels have deliberately small gutters
        factor *= 1.07
        x, y = float(label.get('x', 0)), float(label.get('y', 0))
        target.set('transform', target.get('transform','') + f' translate({x:g},{y:g}) scale({factor:g}) translate({-x:g},{-y:g})')
        target.set('data-v13-effective-font-size', f'{size * factor:.2f}')
    # Mathematical block labels are outlines in both source variants.
    for n in root.iter():
        if n.get('data-tex') and n.get('id','').startswith(('b-','c-','split-')):
            n.set('transform', n.get('transform','') + ' scale(1.12)')


def card(group, x, y, width, height, ink):
    ET.SubElement(group, '{'+SVG+'}path', {'d':f'M{x},{y}l12,-12h{width}l-12,12Z', 'class':'hatch'})
    ET.SubElement(group, '{'+SVG+'}path', {'d':f'M{x+width},{y}l12,-12v{height}l-12,12Z', 'class':'hatch'})
    ET.SubElement(group, '{'+SVG+'}rect', {'x':str(x),'y':str(y),'width':str(width),'height':str(height),'class':'paper wash-structure'})


def rebuild_result(root, ident, left, width, center_shift, yshift):
    g = find(root, ident)
    # Preserve all original text/formulas, rebuild only the card geometry.
    for n in list(g):
        if n.tag.rsplit('}',1)[-1] in ('path','rect'):
            g.remove(n)
    text_nodes = list(g)
    g.clear(); g.set('id',ident); g.set('transform',f'translate(0,{yshift})')
    card(g,left,1370,width,118,'')
    for n in text_nodes:
        shift(n,center_shift,0)
        g.append(n)


def apply(source, editable_reference):
    root = copy.deepcopy(source)
    editable_reference = copy.deepcopy(editable_reference)
    replace_pipeline_labels(root)
    replace_pipeline_labels(editable_reference)
    root.set('viewBox',f'0 {TOP} {WIDTH} {HEIGHT}')
    root.set('width','472.5mm'); root.set('height','300mm')
    root.set('data-version','ink_v13'); root.set('data-input-version','ink_v11')
    root.set('data-v13-layout','two-columns-three-rows')
    root.set('data-v13-changes','two-columns-three-rows-larger-labels-reconnected-collector')
    root.set('data-v13-alignment','aligned-columns-uniform-side-artwork-larger-labels-compact-gaps')
    find(root,'title').text='图1.1 第十三版：联合决策、候选生成与统一执行评价'
    find(root,'desc').text='02采用两列三排，依次为a/b、c/d、e/f；六项为候选来源而非串行步骤。整图收窄，01和03图形等比放大并收紧连接间隙，02文字增大并拉开文字间距。两核流水线标注为矩阵、向量、读入、写出。四种配色共享几何，保留V11笔触及评价反馈闭环。'
    scale_labels(root, editable_reference)
    enlarge_pool_labels(root, editable_reference, find)

    # Original page rules stop too early after adding a third row.
    page=find(root,'page-v6')
    for n in list(page):
        if n.tag.rsplit('}',1)[-1] != 'title': page.remove(n)
    ET.SubElement(page,'{'+SVG+'}rect',{'x':'0','y':str(TOP),'width':str(WIDTH),'height':str(HEIGHT),'fill':'white'})
    for x in (1050,2130):
        ET.SubElement(page,'{'+SVG+'}path',{'d':f'M{x},346V1880','class':'panel-divider'})

    # Match headers/result rows and spread intact components with translations.
    joint=find(root,'joint-decision-v6')
    keep={'v6-inherited-text-003','v6-inherited-text-004','v6-inherited-text-005','original-graph-card','original-graph-title'}
    body=ET.Element('{'+SVG+'}g',{'id':'joint-body-v13','transform':'translate(-30,-1) scale(1.12)','data-v13-component-spacing':'compact-translations-uniform-scale'})
    for n in list(joint):
        if n.get('id') not in keep and not n.tag.endswith('title'):
            joint.remove(n); body.append(n)
    joint.append(body)
    space_joint(root,find,shift)
    find(root,'original-graph-card').set('height','96')
    find(root,'original-graph-card').set('x','40')
    find(root,'original-graph-card').set('width','990')
    shift(find(root,'original-graph-title'),32,12.2)
    for ident in ('v6-inherited-text-003','v6-inherited-text-004','v6-inherited-text-005'):
        shift(find(root,ident),-48,0)
    shift(find(root,'v6-inherited-text-005'),0,4)

    pool=find(root,'neighborhoods-v6')
    shift(pool,70,0)
    for ident in ('v6-inherited-text-018','v6-inherited-text-020','v6-section-02-title'): shift(find(root,ident),-50,0)
    for n in pool:
        if n.tag.endswith('rect'):
            n.set('x','1000'); n.set('width','1040'); n.set('y','356'); n.set('height','96')
    shift(find(root,'selection-principle'),-235,0)
    pool.remove(find(root,'selection-to-pool'))
    # Equal 520-unit column pitch and compact 500-unit row pitch.
    placements={'a':(-50,-19,1,1),'b':(-5,-19,1,2),
                'c':(-1000,481,2,1),'d':(470,5,2,2),
                'e':(-525,505,3,1),'f':(-480,505,3,2)}
    for key,(dx,dy,row,col) in placements.items():
        g=find(root,'source-'+key); shift(g,dx,dy)
        g.set('data-row',str(row)); g.set('data-column',str(col))
    for ident in ('text-047','subtitle-b','subtitle-c','subtitle-d','text-069','text-085'):
        shift(find(root,ident),0,8)
    for ident in ('text-082','text-091'):
        shift(find(root,ident),0,8)
    fifo=find(root,'source-f')
    for n in list(fifo)[4:19]:
        shift(n,0,16)
    path(root,'pool-row-divider','M1000,950H2040M1000,1450H2040')
    # Extra spacing below subtitles prevents enlarged before-label collisions.
    for key in ('b','c'):
        for suffix in ('before','before-state','transition','action','after','after-state'):
            shift(find(root,f'{key}-{suffix}'),0,22)
    for ident in ('split-before','split-parent-B','split-transition','split-after',
                  'split-child-B1','split-child-B2','split-preserved-dependency'):
        shift(find(root,ident),0,22)
    shift(find(root,'split-before'),0,-11)
    shift(find(root,'split-parent-B'),0,-13)
    shift(find(root,'split-after'),0,31)
    for ident in ('split-child-B1','split-child-B2','split-preserved-dependency'):
        shift(find(root,ident),0,29)
    path(root,'split-transition','M1262,1174V1235')
    # Caption a had its own old translation; center below its actual diagram.
    shift(find(root,'text-054'),0,20)
    # Place the residency transition between the upper and lower block rows.
    for n in find(root,'source-e'):
        if n.tag.endswith('path') and n.get('d')=='M1455,1128V1212':
            n.set('id','residency-transition-v13'); n.set('d','M1455,1188V1230')
    path(root,'pool-collector','M1020,1900V1922H2020V1900')
    path(root,'pool-to-complete-candidate','M1520,1922V1955')

    # Bring 03 left into the space released by switching to two columns.
    execution=find(root,'execution-v6'); execution.set('transform','translate(60,0)')
    hardware=find(root,'hardware-cutaway-v6')
    hardware.set('transform','translate(-240.3,-3) scale(1.12)')
    for ident in ('text-107','text-108','text-109','text-110','text-116','text-117','text-118','text-119'):
        shift(find(root,ident),-6,0)
    find(root,'evaluation-title-card').set('height','96')
    find(root,'evaluation-title-card').set('width','960')
    shift(find(root,'evaluation-title'),68,12.2)
    # Increase the gap between the two enlarged COPY labels on each core.
    for ident in ('copy-out-label','right-copy-out-label-v8'): shift(find(root,ident),-12,0)
    for ident in ('copy-in-label','right-copy-in-label-v8'): shift(find(root,ident),12,0)
    space_hardware(root,find,shift)

    rebuild_result(root,'current-state-v6',40,990,42,600)
    rebuild_result(root,'candidate-v6',1070,1040,-165,600)
    rebuild_result(root,'objective-v6',2150,960,133,600)
    path(root,'current-to-candidate','M1046,2029H1063')
    path(root,'candidate-to-evaluation','M2126,2029H2143')
    feedback=find(root,'feedback-v6'); feedback.set('transform','translate(75,585)')
    shift(find(root,'v6-inherited-text-079'),0,4)
    path(root,'evaluation-to-feedback','M2630,2098V2140Q2630,2171 2600,2171H2050')
    path(root,'feedback-to-current','M1135,2171H565Q535,2171 535,2141V2098')
    shift(find(root,'v6-inherited-text-081'),-48,470)
    return root


def detail(root):
    """Standalone 02 detail, useful when the paper needs a full-width close-up."""
    result=copy.deepcopy(root)
    for n in list(result):
        if n.tag.endswith('g') and n.get('id') not in ('neighborhoods-v6','main-process-v6'):
            result.remove(n)
    main=find(result,'main-process-v6')
    for n in list(main):
        if n.get('id')!='candidate-v6': main.remove(n)
    result.set('viewBox','1050 235 1080 1875')
    result.set('width','150mm'); result.set('height',f'{150*1875/1080:.6f}mm')
    result.set('data-v13-detail','02')
    return result


def inkscape_binary():
    candidates=[os.environ.get('INKSCAPE_BIN'),shutil.which('inkscape'),shutil.which('inkscape.com'),r'C:\Program Files\Inkscape\bin\inkscape.com']
    for c in candidates:
        if c and Path(c).exists(): return c
    raise RuntimeError('Set INKSCAPE_BIN to the Inkscape command-line executable')


def export(svg, dest, width=6000):
    dest.mkdir(exist_ok=True)
    pdf=dest/(svg.stem+'.pdf')
    cmd=[inkscape_binary(),str(svg.resolve()),'--export-area-page','--export-type=pdf','--export-filename='+str(pdf.resolve())]
    result=subprocess.run(cmd,capture_output=True,timeout=120)
    if result.returncode or not pdf.exists(): raise RuntimeError(result.stderr.decode(errors='replace'))
    doc=pymupdf.open(pdf)
    if len(doc)!=1 or doc[0].get_image_info(): raise ValueError('Export must be one vector PDF page')
    for tail,px in [('',width),('_preview',2100)]:
        doc[0].get_pixmap(matrix=pymupdf.Matrix(px/doc[0].rect.width,px/doc[0].rect.width),alpha=False).save(dest/(svg.stem+tail+'.png'))
    doc.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--all',action='store_true'); p.add_argument('--palette',choices=THEMES,default='qinglu')
    p.add_argument('--source',type=Path,default=HERE.parent/'ink_v11')
    p.add_argument('--svg-only',action='store_true'); args=p.parse_args()
    (HERE/'assets').mkdir(exist_ok=True)
    for theme in THEMES if args.all else [args.palette]:
        reference=ET.parse(args.source/'assets'/f'workflow_{theme}_v11_editable.svg').getroot()
        for tail in ('','_editable'):
            source=ET.parse(args.source/'assets'/f'workflow_{theme}_v11{tail}.svg').getroot()
            result=apply(source,reference)
            target=HERE/'assets'/f'workflow_{theme}_v13{tail}.svg'
            ET.ElementTree(result).write(target,encoding='utf-8',xml_declaration=True)
            if not tail:
                target.with_suffix('.svgz').write_bytes(gzip.compress(target.read_bytes(),mtime=0))
                closeup=HERE/'assets'/f'workflow_{theme}_v13_detail.svg'
                ET.ElementTree(detail(result)).write(closeup,encoding='utf-8',xml_declaration=True)
                if not args.svg_only:
                    export(target,HERE/'exports')
                    export(closeup,HERE/'exports',width=3000)
        print(theme+': V13 two columns / three rows built',flush=True)


if __name__=='__main__': main()
