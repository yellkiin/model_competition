#!/usr/bin/env python3
"""Figure 1.1 v4: apply the user's 14 marked edits to the reviewed v3 vector.

All artwork is edited locally. Existing SimSun/Times outlines and Computer Modern
formula paths are reused from v3; no font is copied or downloaded. New Chinese
headings reuse characters already present in that drawing. An editable-text SVG
and a portable outlined SVG are written separately. Colors come only from the
existing ink-v2 palette registry. Run at repository root: python <this file> --all.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
import gzip
import json
from pathlib import Path
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SVG = 'http://www.w3.org/2000/svg'
INK = 'http://www.inkscape.org/namespaces/inkscape'
ET.register_namespace('', SVG)
ET.register_namespace('inkscape', INK)
N = {'s': SVG}
TAG = lambda name: '{' + SVG + '}' + name
THEMES = ('qinglu', 'qianjiang', 'yanlan', 'mono')


def find(root, ident):
    e = root.find(".//*[@id='" + ident + "']")
    if e is None:
        raise ValueError('Missing reviewed v3 object: ' + ident)
    return e


def erase(root, node):
    for parent in root.iter():
        if node in list(parent):
            parent.remove(node)
            return
    raise ValueError('Detached node')


def translate(node, x=0, y=0):
    node.set('transform', f'translate({x:g},{y:g}) ' + node.get('transform', ''))


def label(node):
    return node.get('data-label', node.text or '').strip()


def remove_label(root, value):
    for node in list(root.iter()):
        if (node.tag == TAG('text') or node.get('data-fonts')) and label(node) == value:
            erase(root, node)


def rect(parent, ident, x, y, w, h, cls='', **attrs):
    return ET.SubElement(parent, TAG('rect'), {
        'id':ident, 'x':str(x), 'y':str(y), 'width':str(w), 'height':str(h),
        'class':cls, **{k.replace('_','-'):str(v) for k,v in attrs.items()}})


def route(parent, ident, d, role='ink', dash=False, width=2.2):
    return ET.SubElement(parent, TAG('path'), {
        'id':ident, 'd':d, 'fill':'none', 'stroke':'#232323',
        'stroke-width':str(width), 'stroke-linejoin':'round', 'stroke-linecap':'round',
        'marker-end':f'url(#v4-arrow-{role})', 'data-role':role,
        **({'stroke-dasharray':'7 6'} if dash else {})})


class TextPair:
    """Pair native text with its already-authored outline. This is drawing reuse,
    not a generated font: no cmap, font files or embedded font resources exist.
    """
    def __init__(self, editable, outlined):
        self.native = {}
        self.outlines = {}
        self.glyphs = {}
        self._pair(editable, outlined)

    def _pair(self, a, b):
        if a.tag == TAG('text'):
            key = a.get('id') or f'v4-inherited-text-{len(self.native):03d}'
            a.set('id', key); b.set('id', key)
            self.native[key] = deepcopy(a); self.outlines[key] = deepcopy(b)
            value = a.text or ''
            size = float(a.get('font-size', '28'))
            x, y = float(a.get('x','0')), float(a.get('y','0'))
            width = float(b.get('data-width','0'))
            if a.get('text-anchor') == 'middle': x -= width / 2
            if a.get('text-anchor') == 'end': x -= width
            # The all-CJK prefix advances one em; no guessed Latin metrics.
            paths = list(b[-1]) if len(b) else []
            for ch, path in zip(value, paths):
                if ord(ch) < 0x2e80: break
                key_glyph = (ch, 'bold' in a.get('class','').split())
                self.glyphs.setdefault(key_glyph, (deepcopy(path), x, y, size))
                x += size
            return
        if len(a) != len(b):
            raise ValueError('Reviewed editable and outlined trees differ')
        for x,y in zip(a,b): self._pair(x,y)

    def chinese(self, parent, ident, value, x, y, size=34, bold=False, portable=False):
        if not portable:
            t = ET.SubElement(parent, TAG('text'), {
                'id':ident, 'x':str(x), 'y':str(y), 'font-size':str(size),
                'text-anchor':'middle', 'class':'bold' if bold else '',
                'style':"font-family:'SimSun',serif;fill:#232323"})
            t.text = value
            return t
        g = ET.SubElement(parent, TAG('g'), {
            'id':ident, 'data-label':value, 'data-fonts':'SimSun (existing figure outlines)',
            'fill':'#232323', 'stroke':'none'})
        left = x - len(value)*size/2
        for i,ch in enumerate(value):
            src = self.glyphs.get((ch,bold)) or self.glyphs.get((ch,not bold))
            if src is None: raise ValueError('New character not in existing figure: '+ch)
            path, ox, oy, oldsize = src
            item = deepcopy(path)
            item.set('transform',f'translate({left+i*size:g},{y:g}) scale({size/oldsize:.12g}) translate({-ox:.9f},{-oy:.9f})')
            item.attrib.pop('stroke',None);item.attrib.pop('stroke-width',None)
            if bold:
                item.set('stroke','#232323');item.set('stroke-width',str(oldsize*.018))
            g.append(item)
        return g

    def existing(self, parent, source_id, ident, x, y, size, portable):
        a = self.native[source_id]
        b = self.outlines[source_id]
        node = deepcopy(b if portable else a)
        node.set('id',ident)
        oldsize = float(a.get('font-size','28'))
        ox, oy = float(a.get('x','0')), float(a.get('y','0'))
        # All uses of this helper retain the original anchor.
        node.set('transform',f'translate({x:g},{y:g}) scale({size/oldsize:.12g}) translate({-ox:g},{-oy:g})')
        parent.append(node)
        return node

    def shorten(self, root, ident, keep, portable, center=None):
        node = find(root,ident)
        if not portable:
            node.text = (node.text or '')[:keep]
            if center is not None: node.set('x',str(center))
            return
        value = node.get('data-label','')
        kept = value[:keep]
        # Outlines are one path per non-space character, optionally with a halo.
        count = sum(not ch.isspace() for ch in kept)
        for sub in node:
            for child in list(sub)[count:]: sub.remove(child)
        node.set('data-label',kept)
        if center is not None:
            # Left-to-right glyphs are unchanged. Center using the native label's
            # known widths: removed suffix ' · Q3' is Times New Roman, 2.05517578125 em.
            source = self.native[ident]
            suffix = value[keep:]
            if suffix != ' · Q3': raise ValueError('Unexpected suffix')
            # Exact Times New Roman advance units: space512, middle dot682,
            # Q1479, 3=1024; em2048 (native outline font audit).
            removed = (512+682+512+1479+1024)/2048*float(source.get('font-size'))
            oldcenter = float(source.get('x'))
            translate(node,center-oldcenter+removed/2,0)
            node.set('data-width',str(float(node.get('data-width'))-removed))


def apply(root, text, portable):
    # 02 and 09: remove only marked title/output bands, keep feedback iteration.
    page = find(root,'page-v3')
    for child in list(page):
        if child.tag not in (TAG('title'),TAG('rect')) and child.get('class') != 'panel-divider':
            page.remove(child)
    root.set('viewBox','0 235 3000 1430')
    root.set('width','420mm'); root.set('height','200.2mm')
    page.find('s:rect',N).set('height','1665')
    feedback = find(root,'feedback-output-v3')
    erase(root,find(root,'finish-to-output')); erase(root,find(root,'outputs-v3'))
    remove_label(root,'停止时')
    # 05: original-graph title, not the deleted G formula or input list.
    j = find(root,'joint-decision-v3')
    remove_label(root,'输入：计算图、硬件配置与搜索预算')
    erase(root,find(root,'graph-definition'))
    rect(j,'original-graph-card',92,356,822,76,'v4-card',rx=4,fill='white',stroke='#747474',stroke_width=1.8)
    text.chinese(j,'original-graph-title','原始计算图',503,405,34,True,portable)
    graph = find(root,'bipartite-example')
    graph.set('transform','translate(116,458) scale(.85)')
    # 06: identical Computer Modern formula, moved into upper-right graph space.
    formula = find(root,'partition-expression')
    formula.set('transform','translate(640,487)')
    formula.set('data-annotation','06')
    # 07: actual connection graph -> caption box -> mapped cores.
    remove_label(root,'原始算子与依赖保持不变')
    g=ET.SubElement(j,TAG('g'),{'id':'partition-map-explanation'})
    rect(g,'partition-map-card',118,937,796,96,'v4-card',rx=4,fill='white',stroke='#747474',stroke_width=1.8)
    text.chinese(g,'partition-map-title','子图划分与归核',516,975,34,True,portable)
    # Unchanged original subtitle style/size, simply centered in its new frame.
    sub = next(k for k,v in text.native.items() if v.text=='原始算子与依赖保持不变')
    obj=text.existing(g,sub,'partition-map-subtitle',516+11*26/2,1012,26,portable)
    # Source is end-anchored; the original 11-character, 286-unit subtitle is centered.
    cores=find(root,'core-assignment-v3')
    for child in list(cores):
        if child.tag==TAG('path') and child.get('d','').startswith(('M279,987','M457,987','M654,987','M812,987')):
            cores.remove(child)
    cores.set('transform','translate(0,0)')
    route(j,'graph-to-partition','M468,911 V933')
    route(j,'partition-to-cores','M516,1033 V1066')
    # 08: clone existing native/math composite, no substituted subscript glyph.
    for old,src,y in [('text-029','text-104',1119),('text-033','text-113',1238)]:
        e=find(root,old); template=deepcopy(find(root,src));template.set('id',old)
        template.set('transform',f'translate(70,{y})')
        for descendant in template.iter():
            if descendant is not template and descendant.get('id'):
                descendant.set('id',old+'-'+descendant.get('id'))
        erase(root,e);cores.append(template)
    for node in j:
        if node.get('data-label','').startswith('核心映射'):
            translate(node,0,26)
    # 03: one smooth downward transfer with a defined endpoint above B.
    source=find(root,'source-structure')
    for node in list(source):
        if node.tag==TAG('path') and node.get('d','').startswith('M1743,691'):
            source.remove(node)
    route(source,'b-migration-v4','M1744,691 C1744,708 1712,706 1712,727','structure',width=2.4)
    # 12: retain the FIFO mechanism, remove only its local Q3 tag.
    value=text.native['text-084'].text
    text.shorten(root,'text-084',len(value)-len(' · Q3'),portable)
    # 13: boxed overall evaluation heading; no longer a special B caption.
    ex=find(root,'execution-v3')
    remove_label(root,'候选示意：迁移 B')
    rect(ex,'evaluation-title-card',2090,356,824,76,'v4-card',rx=4,fill='white',stroke='#747474',stroke_width=1.8)
    text.chinese(ex,'evaluation-title','总体评价',2502,405,34,True,portable)
    hw=find(root,'hardware-cutaway-v3')
    original=list(hw)
    # Gain space below the new heading without compressing engraved hardware.
    for indexes,dy in [(range(0,9),50),(range(9,28),40),(range(28,38),30),
                       (range(44,53),50),(range(53,72),40),(range(72,82),30)]:
        for i in indexes:translate(original[i],0,dy)
    for i in list(range(38,44))+list(range(82,100)):
        hw.remove(original[i])
    for i,(x,tx) in enumerate([(2213,2190),(2353,2345),(2628,2605),(2768,2760)]):
        route(hw,f'pipe-private-{i}',f'M{x},807 C{x},816 {tx},815 {tx},822',width=1.8)
    # 04: both left labels have explicit direction. All arrow heads finish in
    # clear whitespace, ahead of memory/DDR solids rather than behind a face.
    route(hw,'left-copy-out','M2195,915 C2080,955 2117,1018 2240,1037','memory')
    route(hw,'left-copy-in','M2344,1037 C2405,997 2441,953 2354,916','memory')
    route(hw,'right-copy-out','M2627,915 C2521,958 2545,1009 2648,1037','memory')
    route(hw,'right-copy-in','M2782,1037 C2880,1008 2877,950 2790,916','memory')
    erase(root,find(root,'text-122'));erase(root,find(root,'text-123'))
    text.existing(hw,'text-122','copy-out-label',2198,958,22,portable)
    text.existing(hw,'text-123','copy-in-label',2328,992,22,portable)
    find(root,'copy-out-tensor-v3').set('transform','translate(2213,1003) scale(.72)')
    # No COPY_IN label on the right; retain its data-object pictogram.
    find(root,'copy-in-tensor-v3').set('transform','translate(2775,987) scale(.78)')
    # 10: delete exactly the horizontal dashed line, not the fill relation.
    for node in list(hw):
        if node.tag==TAG('path') and node.get('d')=='M2375,1201H2810':hw.remove(node)
    # 11: a shorter L2 cuboid, with native label recentered and Q3 deleted.
    for node in hw:
        if node.tag==TAG('path') and node.get('d','').startswith('M2363,1252l'):
            node.set('d','M2460,1252l24,-24h330l-24,24Z')
        elif node.tag==TAG('path') and node.get('d','').startswith('M2820,1252l'):
            node.set('d','M2790,1252l24,-24v79l-24,24Z')
        elif node.tag==TAG('rect') and node.get('x')=='2363':
            node.set('x','2460');node.set('width','330')
    text.shorten(root,'text-125',len(text.native['text-125'].text)-len(' · Q3'),portable,center=2625)
    # 14: a broad leftward fill arc close to the unchanged two-line annotation.
    for node in list(hw):
        if node.tag==TAG('path') and node.get('d','').startswith('M2385,1169'):hw.remove(node)
        elif node.tag==TAG('path') and node.get('d','').startswith('M2822,1292'):hw.remove(node)
    route(hw,'ddr-to-l2-fill','M2385,1169 C2225,1182 2310,1278 2448,1284','fifo',True,1.9)
    route(hw,'l2-hit-read','M2815,1292 C2944,1206 2962,862 2882,717','fifo',False,2.2)
    # 01: 22 -> 29 SVG units, moved outside the arc, without a white masking halo.
    for ident,y in [('text-129',1031),('text-130',1067),('text-131',1103)]:
        erase(root,find(root,ident))
        node=text.existing(hw,ident,ident,2970,y,29,portable)
        if portable:
            for subnode in list(node):
                if subnode.get('aria-hidden')=='true':node.remove(subnode)
        else: node.set('class','muted')
    # Everything remains in named editable layers, with v4 identifiers.
    for node in root.iter():
        for key,value in list(node.attrib.items()):
            if key in ('id','data-source','data-target'):
                node.set(key,value.replace('-v3','-v4'))
    root.set('data-version','ink_v4')
    root.set('data-input-version','ink_v3')
    root.set('data-annotations-applied','01 02 03 04 05 06 07 08 09 10 11 12 13 14')
    root.set('data-text-outlined','true' if portable else 'false')
    find(root,'title').text='图1.1 第四版：联合决策、多邻域协同与统一执行评价'
    find(root,'desc').text='按14条原始批注直接编辑第三版矢量。保留反馈迭代，删除图内顶部标题及停止输出块；公式和算法语义沿用原稿。'


def pigments(root,p):
    def wash(c,t=.13):
        return '#'+''.join(f'{round(255+(int(c[i:i+2],16)-255)*t):02X}' for i in (1,3,5))
    mapping={'#232323':p['ink'],'#171717':p['ink'], '#585858':p['muted'],'#505050':p['muted'],
             '#747474':p['hair'],'#BDBDBD':p['faint'],'#B6B6B6':p['faint'],
             '#404040':p['structure'],'#686868':p['memory'],'#858585':p['fifo'],
             '#E6E6E6':wash(p['structure']),'#EBEBEB':wash(p['memory']),'#EFEFEF':wash(p['fifo'])}
    def replace(s):return re.sub(r'#[0-9a-fA-F]{6}',lambda m:mapping.get(m.group().upper(),m.group()),s)
    for node in root.iter():
        for k,v in list(node.attrib.items()):node.set(k,replace(v))
        if node.tag==TAG('style') and node.text:node.text=replace(node.text)
        if node.get('data-role'):node.set('stroke',p[node.get('data-role')])
    defs=root.find('s:defs',N)
    for role in ('ink','structure','memory','fifo'):
        m=ET.SubElement(defs,TAG('marker'),{'id':f'v4-arrow-{role}','viewBox':'0 0 12 12',
           'refX':'11','refY':'6','markerWidth':'12','markerHeight':'12',
           'markerUnits':'userSpaceOnUse','orient':'auto'})
        ET.SubElement(m,TAG('path'),{'d':'M1 1 L11 6 L1 11 L3.5 6 Z','fill':p[role],'stroke':'none'})
    root.set('data-palette',p['key'])


def export(svg: Path, width: int):
    exe=shutil.which('inkscape')
    if not exe:raise RuntimeError('SVGs are ready; Inkscape is required for PDF/PNG exports')
    dest=HERE/'exports';dest.mkdir(exist_ok=True)
    for suffix,opts in [('.pdf',[]),('.png',[f'--export-width={width}']),('_preview.png',['--export-width=1800'])]:
        target=dest/(svg.stem+suffix)
        subprocess.run([exe,str(svg),f'--export-filename={target}','--export-area-page',
                        '--export-background=white','--export-background-opacity=1',*opts],
                       check=True,capture_output=True,text=True,timeout=120)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--all',action='store_true')
    ap.add_argument('--palette',choices=THEMES,default='qinglu')
    ap.add_argument('--svg-only',action='store_true')
    ap.add_argument('--png-width',type=int,default=6000)
    ap.add_argument('--source',type=Path,default=HERE.parent/'ink_v3/assets')
    args=ap.parse_args()
    editable=ET.parse(args.source/'workflow_mono_v3_editable.svg').getroot()
    outlined=ET.parse(args.source/'workflow_mono_v3.svg').getroot()
    text=TextPair(editable,outlined)
    registry=json.loads((ROOT/'paper_a_figures/ink_engraving_agent/palettes.json').read_text(encoding='utf8'))
    apply(editable,text,False);apply(outlined,text,True)
    names=THEMES if args.all else [args.palette]
    for name in names:
        p={**registry['common'],**registry['palettes'][name],'key':name}
        for src,tail in [(editable,'_editable'),(outlined,'')]:
            root=deepcopy(src);pigments(root,p)
            dest=HERE/'assets'/f'workflow_{name}_v4{tail}.svg';dest.parent.mkdir(exist_ok=True)
            ET.ElementTree(root).write(dest,encoding='utf-8',xml_declaration=True)
            if not tail:
                dest.with_suffix('.svgz').write_bytes(gzip.compress(dest.read_bytes(),mtime=0))
                if not args.svg_only:export(dest,args.png_width)
        print(name,flush=True)


if __name__=='__main__':main()
