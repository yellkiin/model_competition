#!/usr/bin/env python3
"""Local editable-SVG revision of the engraved master. Geometry is inherited.

No image-generation service. Existing original remains untouched. Text stays text.
python paper_a_figures/engraved_workflow/ink_v2/build.py --all-palettes
"""
from __future__ import annotations
import argparse
from copy import deepcopy
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))
from paper_a_figures.ink_engraving_agent.style import palette, wash, svg_css

SVG = 'http://www.w3.org/2000/svg'
INKSCAPE = 'http://www.inkscape.org/namespaces/inkscape'
ET.register_namespace('', SVG)
ET.register_namespace('inkscape', INKSCAPE)
NS = {'s': SVG}


def tag(x): return '{' + SVG + '}' + x

def text_value(e): return ''.join(e.itertext())

def by_id(root, ident):
    result = root.find(f".//*[@id='{ident}']")
    if result is None: raise ValueError(f'Master missing named object: {ident}')
    return result


def add_class(e, cls):
    e.set('class', (e.get('class', '') + ' ' + cls).strip())


def new_text(parent, x, y, value, size=24, cls='', anchor='start', ident=None):
    a = {'x':str(x),'y':str(y),'font-size':str(size),'class':cls,'text-anchor':anchor}
    if ident: a['id'] = ident
    e = ET.SubElement(parent, tag('text'), a); e.text = value
    return e


def path(parent, d, cls='main-link', ident=None, marker=True, **attrs):
    a={'d':d,'class':cls, **{k.replace('_','-'):str(v) for k,v in attrs.items()}}
    if ident:a['id']=ident
    if marker:a['marker-end']='url(#ink-feedback-arrow)' if cls=='feedback-link' else 'url(#ink-main-arrow)'
    return ET.SubElement(parent,tag('path'),a)


def layer(root, ident, title):
    g=ET.SubElement(root,tag('g'),{'id':ident, '{'+INKSCAPE+'}groupmode':'layer','{'+INKSCAPE+'}label':title})
    ET.SubElement(g,tag('title')).text=title
    return g


def remove(parent, predicate):
    for e in list(parent):
        if predicate(e):parent.remove(e)


def thin_fibres(root):
    """Keep material engraving; simplify ONLY fibre bundles ending in an arrow."""
    for g in root.iter(tag('g')):
        pending=[]
        for e in list(g):
            if e.tag == tag('path') and e.get('class') == 'hair' and 'C' in e.get('d',''):
                pending.append(e);continue
            if e.tag == tag('path') and e.get('class') == 'route' and e.get('marker-end') and pending:
                # Actual fibre strokes have the same start AND end as this route.
                d=e.get('d',''); start=d.split('C')[0]; tail=d.rsplit(' ',1)[-1]
                bundle=[x for x in pending if x.get('d','').split('C')[0]==start and x.get('d','').rsplit(' ',1)[-1]==tail]
                keep={0,len(bundle)-1} if len(bundle)<8 else {len(bundle)//2-2,len(bundle)//2+2}
                for i,x in enumerate(bundle):
                    if i not in keep:g.remove(x)
                    else:x.set('opacity','.55')
                add_class(e,'local-link')
            pending=[]


def markers(defs, p):
    for ident,color in [('ink-main-arrow',p['ink']),('ink-feedback-arrow',p['structure'])]:
        m=ET.SubElement(defs,tag('marker'),{'id':ident,'viewBox':'0 0 12 12','markerWidth':'12','markerHeight':'12','refX':'11','refY':'6','orient':'auto','markerUnits':'userSpaceOnUse'})
        ET.SubElement(m,tag('path'),{'d':'M1 1 L11 6 L1 11 L3.6 6 Z','fill':color,'stroke':'none'})
    for role in ['structure','memory','fifo']:
        pat=ET.SubElement(defs,tag('pattern'),{'id':f'ink-{role}-hatch','width':'12','height':'12','patternUnits':'userSpaceOnUse'})
        ET.SubElement(pat,tag('rect'),{'width':'12','height':'12','fill':wash(p[role],.13)})
        ET.SubElement(pat,tag('path'),{'d':'M0 12L12 0','stroke':p[role],'stroke-width':'.55','opacity':'.48'})


def style_modules(root,p):
    # Original module geometry is not re-laid out. Color is tied to objects/roles.
    graph=by_id(root,'bipartite-example')
    boundaries=[x for x in graph if x.get('class')=='boundary']
    boundaries[0].set('style',f"fill:url(#ink-structure-hatch);stroke:{p['structure']}")
    for t in graph.iter(tag('text')):
        if text_value(t)=='B':add_class(t,'text-structure')
    for ident,role in [('source-structure','structure'),('source-residency','memory'),('source-fifo','fifo')]:
        g=by_id(root,ident)
        for e in g.iter():
            cls=e.get('class','')
            if cls=='black':add_class(e,'role-'+role)
            if e.tag==tag('path') and ('route' in cls or ('hair' in cls and 'C' in e.get('d',''))):
                e.set('style',f"stroke:{p[role]}")
        if role=='fifo':
            for e in g.iter(tag('rect')):
                if e.get('class')=='hatch':e.set('style','fill:url(#ink-fifo-hatch)')
            for e in g.iter(tag('text')):
                if text_value(e) in ['驻留窗口','s′ₜ']:add_class(e,'text-fifo')
    for ident in ['joint-decision','execution']:
        g=by_id(root,ident)
        for e in g:
            if e.tag==tag('rect') and e.get('class')=='black':add_class(e,'role-structure')
    # Current state is a slight tint, not a colored module panel.
    g=by_id(root,'joint-decision')
    for e in g:
        if e.tag==tag('rect') and e.get('x')=='197':add_class(e,'wash-structure')
    g=by_id(root,'execution')
    for e in g:
        if e.tag==tag('rect'):
            if e.get('y')=='808':add_class(e,'wash-memory')
            if e.get('y')=='1080':add_class(e,'wash-memory')
            if e.get('y')=='1252':add_class(e,'wash-fifo')
        if e.tag==tag('text') and 'L2 · FIFO' in text_value(e):add_class(e,'text-fifo')
        if e.tag==tag('path') and e.get('d','').startswith('M2822,1292'):
            e.set('style',f"stroke:{p['fifo']}")
    for t in by_id(root,'page').iter(tag('text')):
        if text_value(t)=='方法总览 / 黑白线刻':t.text='方法总览 / 线刻 · '+p['name']


def replace_connectors(root,p):
    j,n,e,a,o=[by_id(root,k) for k in ['joint-decision','neighborhoods','execution','accept-feedback','outputs']]
    # The long fibre route, the floating rail loop, and pseudo-double arrows go.
    remove(j,lambda x: x.tag==tag('path') and (x.get('d','').startswith('M752,1482') or x.get('d','').startswith('M865,1274') or x.get('d','').startswith('M806,1409')))
    remove(n,lambda x:x.tag==tag('path') and (x.get('d','').startswith('M1933,1479') or x.get('d','').startswith('M1938,1528')))
    remove(n,lambda x:x.tag==tag('text') and text_value(x) in ['通过','筛','去','重','选'])
    remove(e,lambda x:x.tag==tag('path') and (x.get('d','').startswith('M2118,1455') or x.get('d','').startswith('M2866,1492')))
    remove(a,lambda x:x.tag==tag('path') and any(x.get('d','').startswith(s) for s in ['M2180,1748','M1122,1748','M116,1734','M1511,1789','M793,1790','M1400,1880C']))
    remove(a,lambda x:x.tag==tag('text') and text_value(x) in ['否：下一轮','接受 / 未接受后均检查','实际评价'])
    # Small, symmetrical headers and the objective are no longer displaced by a curl.
    for t in a.iter(tag('text')):
        s=text_value(t)
        if s=='总体任务执行时间（Makespan）':
            t.set('x','2510');t.set('text-anchor','middle');t.set('id','makespan-title')
        elif s.startswith('Cq(y) ='):
            t.set('x','2510');t.set('text-anchor','middle');t.set('id','makespan-formula')
        elif s.startswith('周期持平'):
            t.set('x','2510');t.set('text-anchor','middle');t.set('font-size','24');t.set('id','copy-tiebreak')
    # Update fill wording using workshop_v2: EVERY COPY_IN completion tries fill.
    for t in e.iter(tag('text')):
        s=text_value(t)
        if s=='完成后尝试填充':t.text='每次读完成尝试填充';t.set('font-size','21')
    # Explicit selector/execution ports replace formerly floating arrow ends.
    remove(n,lambda x:x.tag==tag('path') and x.get('d')=='M1070,492H1928')
    ET.SubElement(n,tag('rect'),{'id':'source-selection-frame','x':'1070','y':'352','width':'860','height':'140','rx':'9','fill':'none','stroke':p['hair'],'stroke-width':'1.3'})
    ET.SubElement(e,tag('rect'),{'id':'execution-pipeline-frame','x':'2090','y':'1418','width':'830','height':'84','rx':'7','fill':'none','stroke':p['hair'],'stroke-width':'1.3'})
    # Only the bottom feedback lane gains space; all three top module positions stay.
    root.set('viewBox','0 0 3000 2220');root.set('height','310.8mm')
    page=by_id(root,'page')
    page.find('s:rect',NS).set('height','2220')
    legend=by_id(root,'legend');legend.set('transform','translate(0,100)')
    # Original rule beneath outputs belongs to legend or another layer; align it.
    for x in root.iter(tag('path')):
        if x.get('d','').startswith('M90,2055') or x.get('d','').startswith('M94,2055'):
            x.set('d',x.get('d').replace('2055','2155'))
    connectors=layer(root,'ink-process-links','流程连接：主流程／分支／外侧反馈')
    def link(ident,source,target,d,kind='main-link',**kw):
        x=path(connectors,d,kind,ident=ident,**kw);x.set('data-source',source);x.set('data-target',target);return x
    # Initial validated state -> source selection: one narrow left-side corridor.
    link('verify-to-state','initial-verification','current-state','M805,1408 V1428 Q805,1482 744,1482')
    link('state-to-source','current-state','source-selection','M749,1482 H920 Q955,1482 955,1447 V469 Q955,432 992,432 H1060')
    # Both paths start at different filter ports, so reject cannot cross pass.
    link('source-to-pool','source-selection','candidate-sources','M1500,492 V524')
    link('filter-pass','screening','execution','M1938,1455 H2080')
    new_text(connectors,2007,1430,'通过',22,'muted','middle')
    link('filter-reject','screening','source-selection','M1938,1427 H1954 Q1980,1427 1980,1401 V461 Q1980,432 1951,432 H1932','feedback-link')
    new_text(connectors,2008,1110,'筛去',21,'text-structure','middle')
    new_text(connectors,2008,1142,'重选',21,'text-structure','middle')
    # Exit the execution node through its outside gutter; enter the objective at right, never through its formula.
    link('execution-to-objective','execution','objective','M2920,1455 H2928 Q2950,1455 2950,1477 V1726 Q2950,1748 2928,1748 H2825')
    link('objective-to-accept','objective','accept','M2180,1748 H1891')
    new_text(connectors,2035,1719,'实际评价',22,'muted','middle')
    link('accept-yes','accept','state-update','M1122,1748 H881')
    link('accept-no','accept','stop','M1511,1789 V1844','branch-link')
    # Accepted update and rejected branch both meet stop before another iteration.
    link('update-to-stop','state-update','stop','M865,1818 V1857 Q865,1880 888,1880 H1396','branch-link')
    new_text(connectors,1032,1918,'更新后检查停止条件',22,'muted','middle')
    # Feedback stays outside every module; no centre-line crossing or masked formula.
    link('stop-no-next','stop','current-state','M1510,1915 V2060 Q1510,2088 1482,2088 H72 Q40,2088 40,2056 V1514 Q40,1482 72,1482 H163','feedback-link')
    new_text(connectors,840,2067,'否：使用当前最好方案进入下一轮',23,'text-structure','middle')
    # Leave the original stop-yes output route intact and label its semantics.
    for x in o:
        if x.tag==tag('path') and x.get('d')=='M1620,1880H1780':
            x.set('class','main-link');x.set('marker-end','url(#ink-main-arrow)');x.set('id','stop-yes-output')
            x.set('data-source','stop');x.set('data-target','outputs')
    return connectors


def finish_legend(root,p):
    legend=by_id(root,'legend')
    for r in legend.iter(tag('rect')):
        if r.get('class')=='black':add_class(r,'role-structure')
    for i,(role,label) in enumerate([('structure','结构／状态'),('memory','驻留／搬运'),('fifo','FIFO窗口')]):
        x=1260+i*232
        ET.SubElement(legend,tag('path'),{'d':f'M{x},2083h28','stroke':p[role],'stroke-width':'6','stroke-linecap':'round'})
        new_text(legend,x+38,2093,label,20,'muted')
    for t in legend.iter(tag('text')):
        if text_value(t).startswith('机制案例为示意'):
            t.set('font-size','19')
    desc=by_id(root,'desc')
    desc.text='可编辑线刻设色流程图。模块沿用原原创矢量；主流程单线，反馈在外侧独立通道；当前主题：'+p['name']+'，三种设色分别对应结构状态、驻留搬运和FIFO。符号与workshop_v2对齐，案例不是实验结果。'


def render(name='qinglu', source=None):
    source=Path(source) if source else HERE.parent/'assets/workflow.svg'
    root=ET.parse(source).getroot()
    p=palette(name);defs=root.find('s:defs',NS)
    markers(defs,p)
    ET.SubElement(defs,tag('style')).text=svg_css(name)
    thin_fibres(root);style_modules(root,p);replace_connectors(root,p);finish_legend(root,p)
    # Compound adjacent fine striae; keep text, named modules and routed links
    # editable. This changes storage, not coordinates, and avoids 1000 anonymous IDs.
    for g in root.iter(tag('g')):
        prev=None
        for x in list(g):
            attrs={k:v for k,v in x.attrib.items() if k not in ('d','id')}
            mergeable=x.tag==tag('path') and x.get('class')=='hair' and not x.get('opacity') and not x.get('marker-end')
            if mergeable and prev is not None and attrs=={k:v for k,v in prev.attrib.items() if k not in ('d','id')}:
                prev.set('d',prev.get('d')+' '+x.get('d'));g.remove(x)
            else:prev=x if mergeable else None
    for i,x in enumerate(root.iter(tag('text'))):
        if not x.get('id'):x.set('id',f'text-{i:03d}')
    target=HERE/'assets'/f'workflow_{name}.svg';target.parent.mkdir(parents=True,exist_ok=True)
    ET.ElementTree(root).write(target,encoding='utf-8',xml_declaration=True)
    return target


def export(svg, width=6000):
    exe=shutil.which('inkscape')
    if not exe: raise RuntimeError('SVG generated. PDF/PNG export requires Inkscape on PATH.')
    dest=HERE/'exports';dest.mkdir(exist_ok=True)
    for suffix,extra in [('.pdf',[]),('.png',[f'--export-width={width}']),('_preview.png',['--export-width=1800'])]:
        out=dest/(svg.stem+suffix)
        subprocess.run([exe,str(svg),f'--export-filename={out}','--export-background=white','--export-background-opacity=1',*extra],check=True,capture_output=True,text=True)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--palette',choices=['qinglu','qianjiang','yanlan','mono'],default='qinglu')
    ap.add_argument('--all-palettes',action='store_true');ap.add_argument('--svg-only',action='store_true')
    ap.add_argument('--png-width',type=int,default=6000);ap.add_argument('--source')
    a=ap.parse_args()
    names=['qinglu','qianjiang','yanlan','mono'] if a.all_palettes else [a.palette]
    for name in names:
        svg=render(name,a.source)
        if not a.svg_only:export(svg,a.png_width)
        print(svg)

if __name__=='__main__':main()
