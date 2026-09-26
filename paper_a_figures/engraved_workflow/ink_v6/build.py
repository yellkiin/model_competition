#!/usr/bin/env python3
"""Build ink_v6 by editing the published ink_v5 SVG pairs; never write v5.
Chinese and existing Latin outlines are reused, not converted with substitute fonts.
New mathematical labels use Computer Modern, matching the original mathematics.
No font files, raster artwork, solver changes, or synthetic performance data.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
SVG = 'http://www.w3.org/2000/svg'
TAG = lambda n: '{'+SVG+'}'+n
NS = {'s': SVG}
ET.register_namespace('', SVG)
ET.register_namespace('inkscape', 'http://www.inkscape.org/namespaces/inkscape')
THEMES = ('qinglu', 'qianjiang', 'yanlan', 'mono')
SHIFT, RIGHT, WIDTH, HEIGHT = 120, 500, 3500, 1550
SOURCE_HASHES = {
 'yanlan': ('93c5ad9793ac54d5e115660333867c2be709eb12', 'a6cc31e3cc307056ae4202469e7fbb5886b15013'),
 'qinglu': ('432aa3454d4013aca35a48ef386f26b67fa2424e', '08ec0a75d7d2ec24d150cb65b83c80876dd40c9b'),
 'mono': ('94d79351e7960a07f766085d8da3b7562b495693', 'd19394d70b60e5bf1f112d5624ea5e5ee3db21b7'),
 'qianjiang': ('d5db1ed4c16354d31ac96c7f863c4c553e68beb6', 'b23dc828b720937d1cd613563dcb92672e3bc166'),
}

def find(root, ident):
    node = root.find(".//*[@id='"+ident+"']")
    if node is None: raise ValueError('Missing source object: '+ident)
    return node

def erase(root, node):
    for parent in root.iter():
        if node in list(parent): parent.remove(node); return
    raise ValueError('Detached object')

def move(node, x=0, y=0):
    node.set('transform', f'translate({x:g},{y:g}) '+node.get('transform',''))
    return node

def el(parent, tag, **attrs):
    return ET.SubElement(parent, TAG(tag), {k.replace('_','-'):str(v) for k,v in attrs.items()})

def git_hash(path):
    b=path.read_bytes()
    return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()

class Atlas:
    """Reuse already-published paths. No font file is generated or distributed."""
    def __init__(self, editable, outlined):
        self.native={e.get('id'):deepcopy(e) for e in editable.iter() if e.tag==TAG('text') and e.get('id')}
        self.outlines={i:deepcopy(find(outlined,i)) for i in self.native}
        self.glyphs={}
        for i,a in self.native.items():
            b=self.outlines[i]
            if not b.get('data-width'): continue
            paths=list(b[-1]) if len(b) and b[-1].tag==TAG('g') else []
            s=a.text or ''; nonspace=[c for c in s if not c.isspace()]
            if len(paths)!=len(nonspace): continue
            size=float(a.get('font-size','28')); x=float(a.get('x','0')); y=float(a.get('y','0'))
            width=float(b.get('data-width'))
            anchor=a.get('text-anchor','start')
            x-=width/2 if anchor=='middle' else width if anchor=='end' else 0
            bold='bold' in a.get('class','').split()
            prefix=re.match(r'^[\u2e80-\uffff]+',s)
            if prefix:
                for j,ch in enumerate(prefix.group()): self.glyphs.setdefault((ch,bold),(deepcopy(paths[j]),x+j*size,y,size))
            suffix=re.search(r'[\u2e80-\uffff]+$',s)
            if suffix:
                n=len(suffix.group())
                for j,ch in enumerate(suffix.group()):
                    self.glyphs.setdefault((ch,bold),(deepcopy(paths[len(paths)-n+j]),x+width-(n-j)*size,y,size))
            # Exact TNR advances of the two inter-word separators in this label.
            if s=='迁移 · 交换 · 切分':
                for j,ch in enumerate('交换'):
                    self.glyphs.setdefault((ch,bold),(deepcopy(paths[3+j]),x+(2+j)*size+size*(512+682+512)/2048,y,size))
    def text(self,parent,ident,value,x,y,size=28,bold=False,portable=False,ink='#202724',anchor='middle'):
        if not portable:
            n=el(parent,'text',id=ident,x=x,y=y,font_size=size,text_anchor=anchor,
                 style=f"font-family:'SimSun',serif;fill:{ink}",**({'class':'bold'} if bold else {}))
            n.text=value; return n
        g=el(parent,'g',id=ident,data_label=value,data_fonts='SimSun (reused v5 outlines)',fill=ink,stroke='none')
        left=x-(len(value)*size/2 if anchor=='middle' else len(value)*size if anchor=='end' else 0)
        for j,ch in enumerate(value):
            src=self.glyphs.get((ch,bold)) or self.glyphs.get((ch,not bold))
            if src is None: raise ValueError('No published glyph: '+ch+' in '+value)
            path,ox,oy,oldsize=src; p=deepcopy(path)
            p.attrib.pop('id',None)
            p.set('transform',f'translate({left+j*size:g},{y:g}) scale({size/oldsize:.12g}) translate({-ox:.9f},{-oy:.9f})')
            p.set('fill',ink)
            if bold: p.set('stroke',ink); p.set('stroke-width',str(oldsize*.014))
            else: p.set('stroke','none')
            g.append(p)
        return g
    def existing(self,parent,source,ident,x,y,size,portable,ink=None):
        a=self.native[source]; n=deepcopy(self.outlines[source] if portable else a)
        n.set('id',ident)
        n.set('transform',f'translate({x:g},{y:g}) scale({size/float(a.get("font-size","28")):.12g}) translate({-float(a.get("x","0")):g},{-float(a.get("y","0")):g})')
        if ink:
            n.set('fill',ink)
            if not portable: n.set('style',f"font-family:'Times New Roman',serif;fill:{ink}")
            for p in n.iter():
                if p.get('fill') and p.get('fill')!='none': p.set('fill',ink)
        parent.append(n);return n


def math(parent,ident,tex,x,y,size=28,ink='#202724'):
    from matplotlib.textpath import TextPath
    from matplotlib.font_manager import FontProperties
    from matplotlib.path import Path as MPath
    tp=TextPath((0,0),'$'+tex+'$',size=size,prop=FontProperties(math_fontfamily='cm'))
    bb=tp.get_extents(); out=[]
    for a,code in tp.iter_segments(curves=True,simplify=False):
        if code==MPath.MOVETO: out.append('M'+','.join(f'{z:.6g}' for z in a))
        elif code==MPath.LINETO: out.append('L'+','.join(f'{z:.6g}' for z in a))
        elif code==MPath.CURVE3: out.append('Q'+' '.join(f'{z:.6g}' for z in a))
        elif code==MPath.CURVE4: out.append('C'+' '.join(f'{z:.6g}' for z in a))
        elif code==MPath.CLOSEPOLY: out.append('Z')
    g=el(parent,'g',id=ident,data_tex=tex,data_math_fonts='Computer Modern',fill=ink,stroke='none',
         transform=f'translate({x-(bb.x0+bb.x1)/2:g},{y:g}) scale(1,-1)')
    el(g,'path',d=''.join(out));return g


def route(parent,ident,d,ink,arrow=True,width=2.1,dash=None):
    a={'id':ident,'d':d,'fill':'none','stroke':ink,'stroke_width':width,
       'stroke_linecap':'butt','stroke_linejoin':'round'}
    if arrow: a['marker_end']='url(#v6-tip-'+ink.lstrip('#')+')'
    if dash: a['stroke_dasharray']=dash
    return el(parent,'path',**a)


def box(parent,ident,x,y,w,h,ghost=False):
    g=el(parent,'g',id=ident)
    if ghost:
        el(g,'rect',x=x,y=y,width=w,height=h,**{'class':'dashed'})
    else:
        el(g,'path',d=f'M{x},{y}l7,-7h{w}l-7,7Z',**{'class':'hatch'})
        el(g,'path',d=f'M{x+w},{y}l7,-7v{h}l-7,7Z',**{'class':'hatch'})
        el(g,'rect',x=x,y=y,width=w,height=h,**{'class':'paper'})
    return g


def header(parent,atlas,letter,title,subtitle,x,y,portable,ink,role):
    el(parent,'ellipse',cx=x+17,cy=y-10,rx=17,ry=17,fill=role,stroke=role)
    math(parent,'badge-'+letter,letter,x+17,y-3,25,'white')
    atlas.text(parent,'heading-'+letter,title,x+48,y,31,True,portable,ink,'start')
    atlas.text(parent,'subtitle-'+letter,subtitle,x,y+38,26,False,portable,ink,'start')


def state(parent,atlas,ident,x,y,lanes,portable,ink,ghost=False):
    g=el(parent,'g',id=ident,data_k1=''.join(lanes[0]),data_k2=''.join(lanes[1]))
    for row,vals in enumerate(lanes):
        yy=y+row*66
        math(g,ident+f'-k{row+1}',f'k_{row+1}',x+20,yy+28,27,ink)
        route(g,ident+f'-axis{row+1}',f'M{x+48},{yy+46}H{x+390}',ink,False,1.3)
        # A/last-node D remain left/right; the operated B/C use the center slot.
        for v in vals:
            col=0 if v=='A' else 2 if v=='D' else 1 if v=='B' or ('B' not in vals) else 2
            xx=x+65+col*112
            b=box(g,ident+'-'+v,xx,yy,78,38)
            atlas.existing(b,'text-030' if v=='A' else 'text-031' if v=='B' else 'text-034' if v=='C' else 'text-032',ident+'-label-'+v,xx+39,yy+27,28,portable,ink)
    if ghost:
        box(g,ident+'-destination',x+177,y,78,38,True)
        route(g,ident+'-B-k2-to-k1',f'M{x+216},{y+62}V{y+47}',ink)
    return g


def change_cell(parent,atlas,letter,title,x,before,after,portable,ink,role):
    g=el(parent,'g',id='source-'+letter,data_operation='migration' if letter=='b' else 'swap')
    header(g,atlas,letter,title,'调整核心映射',x,519,portable,ink,role)
    atlas.text(g,letter+'-before',title+'前',x+210,583,22,False,portable,ink)
    state(g,atlas,letter+'-before-state',x,601,before,portable,ink,letter=='b')
    route(g,letter+'-transition',f'M{x+213},726V758',role,True,2.3)
    # Explicit mathematical operation labels, not an implied pipeline.
    math(g,letter+'-action',r'k_2\to k_1' if letter=='b' else r'B\leftrightarrow C',x+307,750,24,role)
    atlas.text(g,letter+'-after',title+'后',x+210,794,22,False,portable,ink)
    state(g,atlas,letter+'-after-state',x,813,after,portable,ink)
    return g


def apply(root,atlas,portable):
    ink=find(root,'v5-arrow-ink').find('s:path',NS).get('fill')
    structure=find(root,'v5-arrow-structure').find('s:path',NS).get('fill')
    memory=find(root,'v5-arrow-memory').find('s:path',NS).get('fill')
    fifo=find(root,'v5-arrow-fifo').find('s:path',NS).get('fill')
    defs=root.find('s:defs',NS)
    for color in sorted({ink,structure,memory,fifo}):
        marker=el(defs,'marker',id='v6-tip-'+color.lstrip('#'),viewBox='0 0 10 10',refX=1,refY=5,
                  markerWidth=10,markerHeight=10,markerUnits='userSpaceOnUse',orient='auto')
        el(marker,'path',d='M1,1 L9,5 L1,9Z',fill=color,stroke='none')
    for style in defs.findall('s:style',NS):
        style.text=(style.text or '').replace("'Noto Sans CJK SC','Microsoft YaHei',sans-serif","'SimSun','Times New Roman',serif").replace("'Noto Serif CJK SC','STIX','Noto Serif',serif","'Times New Roman','SimSun',serif")
    root.set('viewBox',f'0 235 {WIDTH} {HEIGHT}');root.set('width','490mm');root.set('height','217mm')
    page=find(root,'page-v5');page.find('s:rect',NS).set('width',str(WIDTH));page.find('s:rect',NS).set('height','1785')
    for p in page.findall('s:path',NS):
        p.set('d','M981,351V1450' if '981' in p.get('d','') else 'M2523,351V1450')
    # Preserve 01 and 03 geometry, fonts and physics; only translate whole groups.
    joint=find(root,'joint-decision-v5')
    old=find(root,'partition-map-title');erase(root,old)
    atlas.text(find(root,'partition-map-explanation'),'partition-map-title','子图切分与归核',516,975,34,True,portable,ink)
    move(find(root,'core-assignment-v5'),0,70)
    for n in joint:
        if n.get('data-label','').startswith('核心映射'): move(n,0,70)
    find(root,'partition-to-cores').set('d','M516,1033V1066')
    atlas.text(joint,'best-layout-title','当前最优方案',516,1120,30,True,portable,ink)
    find(root,'core-assignment-v5').set('data-solution-status','illustrative-current-best-not-certified-global-optimum')
    move(find(root,'execution-v5'),RIGHT,0)
    # Enlarge 02 from 910 to 1410; keep original a/e/f drawings at native size.
    pool=find(root,'neighborhoods-v5')
    old_base=deepcopy(find(root,'source-base'))
    old_e=deepcopy(find(root,'source-residency'))
    old_f=deepcopy(find(root,'source-fifo'))
    keep={'v5-inherited-text-018','v5-inherited-text-020'}
    for n in list(pool):
        if n.get('id') not in keep: pool.remove(n)
    atlas.text(pool,'v6-section-02-title','子图切分与归核',1113,285,43,True,portable,ink,'start')
    el(pool,'rect',x=1050,y=357,width=1410,height=96,rx=5,fill='white',stroke=structure,stroke_width=1.5)
    atlas.text(pool,'selection-principle','依据收益与成本分配搜索机会',1755,396,34,True,portable,ink)
    atlas.text(pool,'selection-subtitle','每轮选择一个来源',1755,435,27,False,portable,ink)
    route(pool,'selection-to-pool','M1755,454V478',ink,True,1.6)
    # Original a header and diagram remain, but all six badges now use CM maths.
    erase(old_base,find(old_base,'text-045'))
    math(old_base,'badge-a','a',1067,552,25,'white')
    old_base.set('id','source-a');old_base.set('data-operation','base-construction');pool.append(old_base)
    change_cell(pool,atlas,'b','迁移',1525,(['A','D'],['B','C']),(['A','B','D'],['C']),portable,ink,structure)
    change_cell(pool,atlas,'c','交换',2000,(['A','C','D'],['B']),(['A','B','D'],['C']),portable,ink,structure)
    route(pool,'pool-row-divider','M1050,941H2460',ink,False,.7)
    # d: partition the two operators, preserving their directed dependency.
    g=el(pool,'g',id='source-d',data_operation='split',data_parent='B',data_children='B1 B2',data_partition='B1={o2};B2={o4};B1->B2')
    header(g,atlas,'d','切分','原始算子与依赖保持不变',1050,995,portable,ink,structure)
    atlas.text(g,'split-before','切分前',1260,1070,22,False,portable,ink)
    b=box(g,'split-parent-B',1130,1090,265,83)
    atlas.existing(b,'text-031','split-parent-label',1262,1119,28,portable,ink)
    math(b,'split-parent-o2','o_2',1200,1151,28,ink)
    math(b,'split-parent-o4','o_4',1325,1151,28,ink)
    route(b,'split-original-dependency','M1227,1144H1290',ink,True,1.6)
    route(g,'split-transition','M1262,1185V1208',structure,True,2.3)
    atlas.text(g,'split-after','切分后',1260,1239,22,False,portable,ink)
    for n,x,op in [('1',1095,'2'),('2',1320,'4')]:
        q=box(g,'split-child-B'+n,x,1260,130,64)
        math(q,'split-child-label-'+n,'B_'+n,x+65,1284,28,ink)
        math(q,'split-child-operator-'+n,'o_'+op,x+65,1311,27,ink)
    route(g,'split-preserved-dependency','M1236,1293H1300',ink,True,1.8)
    # e and f are exactly the former c and d, renumbered and translated only.
    for node,oldid,letter,dx in [(old_e,'text-067','e',475),(old_f,'text-083','f',459)]:
        erase(node,find(node,oldid))
        cx=1067 if letter=='e' else 1558
        math(node,'badge-'+letter,letter,cx,966,25,'white')
        node.set('id','source-'+letter);node.set('transform',f'translate({dx},26)')
        node.set('data-operation','residency' if letter=='e' else 'fifo-order')
        pool.append(node)
    route(pool,'pool-collector','M1070,1385V1410H2440V1385',ink,False,1.1)
    route(pool,'pool-to-complete-candidate','M1755,1410V1471',structure,True,2.3)
    # Prominent but sparse 01 -> 02 -> 03 connections, plus one feedback loop.
    links=el(root,'g',id='section-links-v6')
    route(links,'section-01-to-02','M775,279H1006',structure,True,2.6)
    route(links,'section-02-to-03','M2320,279H2563',structure,True,2.6)
    main=find(root,'main-process-v5')
    move(find(root,'current-state-v5'),0,SHIFT)
    old=find(root,'v5-inherited-text-075');erase(root,old)
    atlas.text(find(root,'current-state-v5'),'best-feasible-label','当前最优可行方案',493,1413,33,False,portable,ink)
    move(find(root,'objective-v5'),RIGHT,SHIFT)
    cand=find(root,'candidate-v5')
    for n in cand:
        if n.tag==TAG('rect'): n.set('width','1410')
        elif n.tag==TAG('path'):
            n.set('d',n.get('d').replace('h910','h1410').replace('M1960','M2460'))
        else: move(n,250,0)
    move(cand,0,SHIFT)
    find(root,'current-to-candidate').set('d',f'M925,{1422+SHIFT}H1036')
    find(root,'candidate-to-evaluation').set('d',f'M2488,{1422+SHIFT}H2575')
    fb=find(root,'feedback-output-v5');move(find(root,'feedback-v5'),250,SHIFT)
    find(root,'evaluation-to-feedback').set('d',f'M2997,{1488+SHIFT}V{1559+SHIFT}Q2997,{1586+SHIFT} 2970,{1586+SHIFT}H2222')
    find(root,'feedback-to-current').set('d',f'M1307,{1586+SHIFT}H520Q493,{1586+SHIFT} 493,{1559+SHIFT}V{1488+SHIFT}')
    move(find(root,'v5-inherited-text-081'),140,SHIFT)
    # Retain exact science/math source objects. IDs must stay globally unique.
    for n in root.iter():
        for k,v in list(n.attrib.items()):
            n.set(k,v.replace('-v5','-v6').replace('v5-','v6-'))
    root.set('data-version','ink_v6');root.set('data-input-version','ink_v5')
    root.set('data-text-outlined','true' if portable else 'false')
    root.set('data-v6-changes','connected-stages expanded-six-operations explicit-before-after partition-not-duplication current-best-layout')
    find(root,'title').text='图1.1 第六版：联合决策、子图切分与归核、统一执行评价'
    find(root,'desc').text='六种候选操作a至f：基础构造、迁移、交换、切分、数据驻留、FIFO复用时序。迁移从k2到k1；交换B与C；B切分为包含原有不同算子的B1和B2，依赖不变。操作示意不是串行步骤，也不表示六个独立的搜索来源；完整评价后更新预算内当前最优可行方案，不声称已证全局最优。问题范围只在配套正文说明。'
    return root


def export(path,width):
    exe=shutil.which('inkscape')
    if not exe: raise RuntimeError('Inkscape is required for PDF/PNG export')
    dest=HERE/'exports';dest.mkdir(exist_ok=True)
    for suffix,args in [('.pdf',[]),('.png',[f'--export-width={width}']),('_preview.png',['--export-width=2100'])]:
        cp=subprocess.run([exe,str(path),f'--export-filename={dest/(path.stem+suffix)}','--export-area-page',
             '--export-background=white','--export-background-opacity=1',*args],capture_output=True,text=True,timeout=180)
        if cp.returncode: raise RuntimeError(cp.stderr)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--all',action='store_true');p.add_argument('--palette',choices=THEMES,default='qinglu')
    p.add_argument('--source',type=Path,default=HERE.parent/'ink_v5');p.add_argument('--svg-only',action='store_true')
    p.add_argument('--png-width',type=int,default=6000);args=p.parse_args()
    if args.png_width<=0:p.error('png width must be positive')
    source=args.source/'assets'
    ed=ET.parse(source/'workflow_mono_v5_editable.svg').getroot()
    portable=ET.parse(source/'workflow_mono_v5.svg').getroot();atlas=Atlas(ed,portable)
    for name in THEMES if args.all else [args.palette]:
        for i,tail in enumerate(('', '_editable')):
            path=source/f'workflow_{name}_v5{tail}.svg'
            if name in SOURCE_HASHES and git_hash(path)!=SOURCE_HASHES[name][i]:raise ValueError('Published v5 source changed: '+path.name)
            root=apply(ET.parse(path).getroot(),atlas,i==0)
            target=HERE/'assets'/f'workflow_{name}_v6{tail}.svg';target.parent.mkdir(exist_ok=True)
            ET.ElementTree(root).write(target,encoding='utf-8',xml_declaration=True)
            if i==0:
                target.with_suffix('.svgz').write_bytes(gzip.compress(target.read_bytes(),mtime=0))
                if not args.svg_only:export(target,args.png_width)
        print(name+': done',flush=True)

if __name__=='__main__':main()
