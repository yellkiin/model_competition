#!/usr/bin/env python3
"""Figure 1.1, v3: conceptual workflow; no experimental data are generated.

Creates an editable SVG, then optionally exports PDF/PNG via Inkscape.
Fonts are resolved locally; font files are not redistributed.
"""
from __future__ import annotations
import argparse
import json
import shutil
import subprocess
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
NS = 'http://www.w3.org/2000/svg'
INK = 'http://www.inkscape.org/namespaces/inkscape'
ET.register_namespace('', NS)
ET.register_namespace('inkscape', INK)
W, H = 1800, 950
C = dict(ink='#202724', muted='#535E59', faint='#CCD5D0', teal='#446E67',
         gold='#94784D', red='#9A655B', blue='#586F86', paper='#FFFFFF',
         tealwash='#EDF4F1', goldwash='#F6F2EA', redwash='#F7EEEB', bluewash='#EEF2F6')


def el(parent, tag, **attrs):
    return ET.SubElement(parent, '{'+NS+'}'+tag,
                         {k.replace('_','-'):str(v) for k,v in attrs.items() if v is not None})

def group(parent, ident):
    return el(parent, 'g', id=ident)

def rect(p,x,y,w,h,fill='white',stroke=None,r=12,sw=1.6,**kw):
    return el(p,'rect',x=x,y=y,width=w,height=h,rx=r,fill=fill,stroke=stroke,stroke_width=sw,**kw)

def line(p,x1,y1,x2,y2,color=None,sw=2,**kw):
    return el(p,'line',x1=x1,y1=y1,x2=x2,y2=y2,stroke=color or C['muted'],stroke_width=sw,**kw)

def path(p,d,color=None,sw=2,arrow=False,fill='none',**kw):
    return el(p,'path',d=d,fill=fill,stroke=color or C['muted'],stroke_width=sw,
              stroke_linecap='round',stroke_linejoin='round',
              marker_end=kw.pop('marker_end', 'url(#arrow)' if arrow else None),**kw)

def text(p,x,y,s,size=30,fill=None,weight=400,anchor='start',**kw):
    t=el(p,'text',x=x,y=y,font_size=size,fill=fill or C['ink'],font_weight=weight,
         text_anchor=anchor,**kw); t.text=s; return t

def circle(p,x,y,r,fill='white',stroke=None,sw=2):
    return el(p,'circle',cx=x,cy=y,r=r,fill=fill,stroke=stroke or C['teal'],stroke_width=sw)

def short_arrow(p,x1,y1,x2,y2,col=None,sw=2.4):
    return path(p,f'M{x1} {y1} L{x2} {y2}',col,sw,True)

def chevron(p,x,y):
    return path(p,f'M{x} {y-16} L{x+13} {y} L{x} {y+16}',C['teal'],4.6)

def header(p,x,w,n,title,wash):
    rect(p,x,24,w,766,wash,C['faint'],18,1.5)
    rect(p,x,24,w,82,'white',None,18)
    rect(p,x,87,w,19,'white',None,0)
    circle(p,x+41,65,23,C['teal'],C['teal'])
    text(p,x+41,75,n,27,'white',600,'middle')
    text(p,x+79,78,title,38,C['ink'],700)
    line(p,x+22,107,x+w-22,107,C['faint'],1.5)

def chip(p,x,y,w,label,fill=None,col=None,size=27):
    rect(p,x,y,w,45,fill or 'white',col or C['faint'],10,1.4)
    text(p,x+w/2,y+32,label,size,col or C['ink'],500,'middle')

def block(p,x,y,w,label,col=None,fill=None,h=39):
    rect(p,x,y,w,h,fill or 'white',col or C['teal'],6,1.8)
    text(p,x+w/2,y+h/2+9,label,25,col or C['teal'],600,'middle')

def node(p,x,y,label):
    circle(p,x,y,19,'white',C['teal'],2)
    text(p,x,y+8,label,23,C['ink'],500,'middle')

def clock(p,x,y,r,col):
    circle(p,x,y,r,'white',col,2.4)
    path(p,f'M{x} {y-r*.60} V{y} L{x+r*.42} {y+r*.26}',col,2.7)


def generate():
    root=ET.Element('{'+NS+'}svg',{'width':'180mm','height':'95mm','viewBox':f'0 0 {W} {H}',
        'version':'1.1','role':'img','aria-labelledby':'figure-title figure-desc',
        'font-family':'Noto Sans CJK SC, Microsoft YaHei, sans-serif'})
    el(root,'title',id='figure-title').text='联合决策与多邻域迭代：总体方法第三版'
    el(root,'desc',id='figure-desc').text=('原始计算图通过子图划分、核心归属和核内顺序形成完整方案。'
        '基础、结构、驻留以及仅第三问开放的缓存时序来源共享当前方案，每轮择一提出候选。'
        '结构与下界筛选后按当前问题的执行规则评价，反馈更新当前方案；搜索结束输出方案与指标。')
    defs=el(root,'defs')
    m=el(defs,'marker',id='arrow',viewBox='0 0 10 10',refX=8.5,refY=5,
         markerWidth=9,markerHeight=9,orient='auto',markerUnits='userSpaceOnUse')
    el(m,'path',d='M0 0 L10 5 L0 10 Z',fill='context-stroke')
    m2=el(defs,'marker',id='flow-arrow',viewBox='0 0 16 16',refX=14,refY=8,
          markerWidth=17,markerHeight=17,orient='auto',markerUnits='userSpaceOnUse')
    el(m2,'path',d='M1 1 L15 8 L1 15 Z',fill=C['teal'])
    el(defs,'style').text='text { font-family: "Noto Sans CJK SC", "Microsoft YaHei", sans-serif; }'
    rect(root,0,0,W,H,'white',None,0)

    # 01 Joint decision: the same six-operator dependency example as v2.
    g=group(root,'joint-model')
    header(g,20,380,'01','联合建模',C['bluewash'])
    text(g,210,151,'计算图 G 与硬件配置',29,C['blue'],600,'middle')
    text(g,210,186,'六算子依赖示意',24,C['muted'],400,'middle')
    # Group envelopes A, B, C, D; arrows retain the two branches.
    for x,y,w,h,s in [(42,260,64,91,'A'),(124,209,166,100,'B'),
                       (124,338,166,100,'C'),(308,260,64,91,'D')]:
        rect(g,x,y,w,h,'#FFFFFF',C['blue'],15,1.6,stroke_dasharray='6 4')
        text(g,x+w/2,y+25,s,23,C['blue'],700,'middle')
    for d in ['M93 313 C113 313 105 266 139 266','M93 313 C113 313 105 395 139 395',
              'M177 266 H235','M177 395 H235',
              'M273 266 C299 266 290 313 322 313','M273 395 C299 395 290 313 322 313']:
        path(g,d,C['blue'],2.2,True)
    for x,y,s in [(74,313,'o₁'),(158,266,'o₂'),(254,266,'o₄'),
                  (158,395,'o₃'),(254,395,'o₅'),(341,313,'o₆')]: node(g,x,y,s)
    short_arrow(g,210,451,210,484,C['blue'],3)
    text(g,210,525,'划分、归核与顺序联合确定',26,C['ink'],600,'middle')
    for y,label in [(559,'k₁'),(626,'k₂')]:
        text(g,59,y+28,label,26,C['blue'],500)
        line(g,96,y+48,360,y+48,C['faint'],2)
    block(g,100,558,72,'A',C['blue'])
    block(g,183,558,72,'B',C['teal'],C['tealwash'])
    block(g,266,558,72,'D',C['blue'])
    block(g,100,625,72,'C',C['blue'])
    text(g,358,677,'核内次序',23,C['muted'],400,'end')
    chip(g,46,702,101,'划分 P',size=25)
    chip(g,159,702,101,'归核 a',size=25)
    chip(g,272,702,101,'顺序 π',size=25)
    text(g,210,779,'初始可行方案  x = (P, a, π)',25,C['blue'],500,'middle')

    # 02 A menu of complementary sources, not four serial/parallel algorithms.
    g=group(root,'multi-neighborhood')
    header(g,440,700,'02','多邻域迭代改进',C['tealwash'])
    rect(g,464,131,652,68,C['teal'],None,12)
    text(g,790,173,'共享当前方案  ·  每轮择一来源',31,'white',600,'middle')
    card_positions=[(464,222),(800,222),(464,466),(800,466)]
    for (x,y),ident,title,col in zip(card_positions,
       ['base-source','structure-source','residency-source','fifo-source'],
       ['基础构造','结构与负载','驻留与通信','缓存时序'],
       [C['blue'],C['teal'],C['gold'],C['red']]):
        q=group(g,ident)
        rect(q,x,y,316,221,'white',C['faint'],13,1.5)
        rect(q,x,y,5,221,col,None,0)
        text(q,x+20,y+40,title,31,col,650)
        if ident=='fifo-source':
            rect(q,x+237,y+15,59,33,C['redwash'],None,8)
            text(q,x+266,y+39,'Q3',23,col,650,'middle')
    # Base source: same operators, two different legal grain groupings.
    q=root.find(".//*[@id='base-source']")
    for yy,grouped in [(283,True),(345,False)]:
        for i in range(6):
            if grouped and i%3==0: rect(q,489+i*41,yy-9,116,47,C['bluewash'],C['blue'],8,1.4)
            if not grouped and i%2==0: rect(q,489+i*41,yy-9,75,47,C['bluewash'],C['blue'],8,1.4)
            circle(q,507+i*41,yy+14,10,'white',C['blue'],1.6)
    text(q,622,419,'探索不同分组粒度',27,C['muted'],500,'middle')
    # Structure source: move a complete subgraph to another core.
    q=root.find(".//*[@id='structure-source']")
    text(q,823,302,'k₁',24,C['teal']); text(q,823,368,'k₂',24,C['teal'])
    line(q,862,316,1091,316,C['faint'],2); line(q,862,382,1091,382,C['faint'],2)
    block(q,865,279,59,'A'); block(q,947,279,59,'B',C['teal'],C['tealwash'])
    block(q,1029,279,59,'D'); block(q,865,345,59,'C')
    rect(q,947,345,59,39,'white',C['teal'],6,1.8,stroke_dasharray='5 4')
    text(q,976,373,'B',25,C['teal'],600,'middle')
    short_arrow(q,976,324,976,341,C['teal'],2.8)
    text(q,958,419,'迁移 · 交换 · 拆分',27,C['muted'],500,'middle')
    # Residency source: a shared tensor, and nearby use in one core.
    q=root.find(".//*[@id='residency-source']")
    rect(q,488,525,268,97,C['goldwash'],None,10)
    circle(q,526,587,17,'white',C['gold'],1.9)
    text(q,526,595,'t',25,C['gold'],600,'middle')
    block(q,578,565,62,'B',C['gold']);block(q,674,565,62,'C',C['gold'])
    path(q,'M544 587 H571',C['gold'],2.2,True)
    path(q,'M542 579 C566 538 688 538 703 558',C['gold'],2.2,True)
    text(q,622,670,'复用机会与容量压力',27,C['muted'],500,'middle')
    # FIFO source: move a request into its observed residency window.
    q=root.find(".//*[@id='fifo-source']")
    rect(q,875,536,151,59,C['redwash'],C['red'],6,1.5)
    text(q,950,574,'驻留窗口',25,C['red'],500,'middle')
    line(q,830,601,1088,601,C['muted'],1.8)
    short_arrow(q,1072,601,1092,601,C['muted'],1.8)
    for x,s in [(875,'填充'),(1026,'淘汰')]:
        line(q,x,534,x,607,C['red'],1.5)
        text(q,x,632,s,22,C['muted'],400,'middle')
    circle(q,1062,601,6,'white',C['red'],2)
    circle(q,948,601,6,C['red'],C['red'],2)
    path(q,'M1062 542 Q1062 511 1018 511 H965 Q948 511 948 530',C['red'],2.8,True)
    text(q,958,670,'固定 P、a，调整 π',25,C['red'],500,'middle')
    # Filters are one subordinate band, not another implementation pipeline.
    rect(g,464,713,652,63,'white',C['faint'],10,1.5)
    path(g,'M491 729 H525 L513 744 V759 H503 V744 Z',C['teal'],2,False,C['tealwash'])
    text(g,540,754,'结构预检与下界筛选',29,C['teal'],550)
    text(g,1091,754,'候选 y',27,C['teal'],600,'end')

    # 03 The chosen scenario, one common event evaluator, physical resources.
    g=group(root,'execution-evaluation')
    header(g,1180,600,'03','统一执行评价',C['goldwash'])
    text(g,1480,151,'按当前问题选择执行规则',28,C['muted'],500,'middle')
    for x,qno,l1,l2,col in [(1204,'Q1','子图 Task','跨子图 DDR',C['blue']),
                           (1390,'Q2','核心 Task','同核可驻留',C['teal']),
                           (1576,'Q3','核心 Task','加入 L2 FIFO',C['red'])]:
        rect(g,x,172,178,108,'white',C['faint'],11,1.5)
        text(g,x+89,202,qno,26,col,650,'middle')
        text(g,x+89,236,l1,24,C['ink'],500,'middle')
        text(g,x+89,267,l2,23,C['muted'],400,'middle')
    for x,n in [(1220,'k₁'),(1520,'k₂')]:
        rect(g,x,307,221,188,'white',C['teal'],12,1.8)
        # Small die pin notches carry the hardware metaphor without noisy hatching.
        for off in [35,77,119,161]:
            line(g,x+off,300,x+off,307,C['teal'],2.2)
        text(g,x+111,342,'核心 '+n,29,C['teal'],600,'middle')
        for yy,starts in [(359,[(26,67),(108,60)]),(386,[(47,85),(157,39)])]:
            line(g,x+20,yy+13,x+200,yy+13,C['faint'],1.3)
            for off,w in starts: rect(g,x+off,yy,w,19,C['tealwash'],C['teal'],3,1)
        block(g,x+20,442,84,'L1',C['gold'],C['goldwash'],35)
        block(g,x+118,442,84,'UB',C['gold'],C['goldwash'],35)
    # One resource bus; it is not a sequential DDR->L2 pipeline.
    line(g,1331,495,1331,518,C['muted'],2)
    line(g,1631,495,1631,518,C['muted'],2)
    line(g,1302,518,1658,518,C['muted'],2)
    line(g,1346,518,1346,539,C['muted'],2)
    line(g,1620,518,1620,539,C['muted'],2)
    rect(g,1204,541,284,61,'white',C['gold'],10,1.8)
    text(g,1346,580,'DDR 共享读写',29,C['gold'],550,'middle')
    rect(g,1508,541,248,61,'white',C['red'],10,1.8,stroke_dasharray='7 4')
    text(g,1632,579,'L2 只读 · Q3',27,C['red'],550,'middle')
    text(g,1480,640,'依赖 · 容量 · 流水线 · 带宽',28,C['muted'],500,'middle')
    rect(g,1204,667,552,109,C['teal'],None,12)
    clock(g,1241,706,16,'white')
    # Use paths on a dark face for the clock hands.
    path(g,'M1241 695 V706 L1250 712',C['teal'],2.4)
    text(g,1273,716,'Makespan 最小',36,'white',650)
    text(g,1480,757,'周期相同，优先减少额外 COPY',26,'white',400,'middle')

    # Four inter-module links only: two forward, one feedback, one output.
    g=group(root,'main-flow')
    for x in [404,1144]:
        path(g,f'M{x} 432 H{x+29}',C['teal'],4.5,False,marker_end='url(#flow-arrow)')
    # Feedback returns to the source module, rather than to the fixed input graph.
    path(g,'M1458 790 V816 Q1458 835 1439 835 H809 Q790 835 790 816 V792',
         C['teal'],3.8,False,marker_end='url(#flow-arrow)')
    rect(g,932,814,372,43,'white',None,9)
    text(g,1118,845,'执行反馈 · 更新当前方案',27,C['teal'],550,'middle')
    path(g,'M1715 790 V874',C['teal'],3.8,False,marker_end='url(#flow-arrow)')
    text(g,1698,841,'搜索结束',23,C['muted'],400,'end')

    g=group(root,'outputs')
    rect(g,20,879,1760,57,C['bluewash'],C['faint'],11,1.5)
    text(g,44,918,'输出',29,C['blue'],700)
    text(g,132,918,'调度方案  +  执行指标与改进记录',29,C['ink'],500)
    line(g,969,892,969,924,C['faint'],1.5)
    text(g,1000,918,'Q3：固定同一方案，对照有 / 无 L2',28,C['red'],500)
    for i,t in enumerate(root.iter('{'+NS+'}text'),1):
        t.set('id', f'label-{i:03d}')
    return ET.ElementTree(root)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--svg-only',action='store_true')
    parser.add_argument('--png-width',type=int,default=4252)
    args=parser.parse_args()
    for d in ['assets','exports','docs']: (HERE/d).mkdir(exist_ok=True)
    source=HERE/'assets/workflow_v3.svg'
    generate().write(source,encoding='utf-8',xml_declaration=True)
    if args.svg_only:
        print(source);return
    ink=shutil.which('inkscape')
    if not ink: raise SystemExit('Inkscape is required for PDF/PNG export; SVG has been saved.')
    jobs=[(source,HERE/'exports/workflow_v3.pdf',['--export-text-to-path']),
          (source,HERE/'exports/workflow_v3.png',[f'--export-width={args.png_width}']),
          (source,HERE/'exports/workflow_v3_preview.png',['--export-width=1800'])]
    for src,out,extra in jobs:
        subprocess.run([ink,str(src),'--export-area-page',f'--export-filename={out}',*extra],check=True)
    # Text-outline SVG for robust viewing, kept separate from editable text source.
    subprocess.run([ink,str(source),'--export-text-to-path','--export-plain-svg',
                    f'--export-filename={HERE/"exports/workflow_v3_outlined.svg"}'],check=True)
    print('Generated editable SVG, outline SVG, vector PDF, high-resolution PNG and preview.')

if __name__=='__main__': main()
