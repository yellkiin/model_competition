#!/usr/bin/env python3
"""Figure 1.1, engraved workflow v3. Editable SVG; Inkscape PDF/PNG exports.

The v2 six-operator example and visual vocabulary are retained, but the layout
expresses the method rather than implementation branches. No external assets,
bitmap embedding, font bundling, network calls, or solver changes are required.
"""
from __future__ import annotations
import argparse
import json
import shutil
import subprocess
from pathlib import Path
from xml.etree import ElementTree as E

NS = 'http://www.w3.org/2000/svg'
E.register_namespace('', NS)
HERE = Path(__file__).resolve().parent
SOURCE_COMMIT = '70d4888886cd9f77037f7b010ce0241349ef056d'
PALETTES = {
    'mono': dict(ink='#232323', structure='#404040', memory='#686868', fifo='#858585', wash='#eeeeec'),
    'qinglu': dict(ink='#252724', structure='#42665f', memory='#8b7053', fifo='#657d89', wash='#eef2ef'),
}
SUB = str.maketrans('0123456789', '₀₁₂₃₄₅₆₇₈₉')

def el(parent, name, **a):
    return E.SubElement(parent, '{'+NS+'}'+name, {k.replace('_','-'):str(v) for k,v in a.items() if v is not None})

def group(parent, ident, title=None, transform=None):
    g=el(parent,'g',id=ident,transform=transform)
    if title: el(g,'title').text=title
    return g

def txt(parent,x,y,value,size=26,cls='',anchor='start',**attrs):
    t=el(parent,'text',x=x,y=y,font_size=size,text_anchor=anchor,**{'class':cls},**attrs)
    t.text=value
    return t

def path(parent,d,cls='fine',arrow=False,**attrs):
    return el(parent,'path',d=d,**{'class':cls},marker_end='url(#arrow)' if arrow else None,**attrs)

def box(parent,x,y,w,h,cls='paper',**attrs):
    return el(parent,'rect',x=x,y=y,width=w,height=h,**{'class':cls},**attrs)

def formula(parent,x,y,parts,size=34,anchor='middle'):
    t=txt(parent,x,y,'',size,'math',anchor)
    for text,sub in parts:
        s=el(t,'tspan',baseline_shift='sub' if sub else None,font_size='70%' if sub else None)
        s.text=text
    return t

def block(parent,x,y,w,h,label='',dark=False,depth=12,size=30,ident=None):
    g=group(parent,ident or f'block-{x}-{y}')
    path(g,f'M{x},{y} l{depth},-{depth} h{w} l-{depth},{depth}Z','hatch')
    path(g,f'M{x+w},{y} l{depth},-{depth} v{h} l-{depth},{depth}Z','hatch')
    box(g,x,y,w,h,'dark' if dark else 'paper')
    if label: txt(g,x+w/2,y+h/2+size*.35,label,size,'math white' if dark else 'math','middle')
    return g

def cube(parent,x,y,index=None,scale=1):
    g=el(parent,'g',transform=f'translate({x},{y}) scale({scale})')
    el(g,'use',href='#tensor-cube')
    if index is not None: txt(g,0,44,'t'+str(index).translate(SUB),23,'math','middle')
    return g

def op(parent,x,y,index,r=34,size=27):
    g=group(parent,f'op-{index}-{x}-{y}')
    el(g,'ellipse',cx=x,cy=y,rx=r+7,ry=r*.73+5,**{'class':'hair'})
    el(g,'ellipse',cx=x,cy=y,rx=r,ry=r*.73,**{'class':'paper'})
    txt(g,x,y+size*.34,'o'+str(index).translate(SUB),size,'math','middle')

def boundary(parent,x,y,rx,ry,accent=False,engrave=True):
    el(parent,'ellipse',cx=x,cy=y,rx=rx,ry=ry,**{'class':'boundary accent' if accent else 'boundary'})
    if engrave:
        for i in range(5):
            a=rx-7-i*2.5; b=ry-6-i*2
            path(parent,f'M{x-a},{y} C{x-a},{y-b*1.34} {x+a},{y-b*1.34} {x+a},{y} M{x-a},{y} C{x-a},{y+b*1.34} {x+a},{y+b*1.34} {x+a},{y}','engrave')

def rail(parent,x,y,w):
    path(parent,f'M{x},{y} l18,-13 h{w} l-18,13Z','hatch')
    path(parent,f'M{x-4},{y+13}H{x+w+24}','fine',True)

def head(parent,x,y,number,title,sub):
    txt(parent,x,y,number,43,'math')
    txt(parent,x+82,y,title,40,'bold')
    txt(parent,x+82,y+44,sub,25,'muted')

def source_head(parent,x,y,letter,title,sub,role='structure'):
    el(parent,'circle',cx=x+16,cy=y-10,r=16,**{'class':f'badge {role}'})
    txt(parent,x+16,y-1,letter,23,'white math','middle')
    txt(parent,x+47,y,title,28,'bold')
    txt(parent,x,y+40,sub,22,'muted')

def joint(root):
    g=group(root,'joint-decision','01 联合决策：原图、划分、归核、核内顺序')
    head(g,90,263,'01','联合决策','划分粒度 × 核心归属 × 核内顺序')
    txt(g,105,366,'原始计算图',28,'bold')
    txt(g,885,366,'G = (T ∪ O, E)',32,'math','end')
    h=group(g,'bipartite-example','A={o1}, B={o2,o4}, C={o3,o5}, D={o6}', 'translate(105,394) scale(.96)')
    boundary(h,410,105,158,80,True)
    boundary(h,410,370,158,80)
    boundary(h,94,238,56,78,engrave=False)
    boundary(h,730,238,56,78,engrave=False)
    for d in ['M-8,238H51','M137,238H175','M215,224C249,216 253,137 267,122','M215,253C249,261 253,338 267,353','M352,105H384','M435,105H461','M352,370H384','M435,370H461','M550,105H591','M550,370H591','M640,118C678,138 688,188 705,206','M640,357C678,337 688,287 705,270','M773,238H807']:
        path(h,d,'fine',True)
    for x,y,k in [(-26,238,0),(198,238,1),(409,105,2),(409,370,3),(616,105,4),(616,370,5),(833,238,6)]: cube(h,x,y,k,.88)
    for x,y,k in [(94,238,1),(310,105,2),(505,105,4),(310,370,3),(505,370,5),(730,238,6)]: op(h,x,y,k,37,28)
    for x,y,s in [(94,347,'A'),(410,2,'B'),(410,474,'C'),(730,347,'D')]: txt(h,x,y,s,30,'math','middle')
    txt(g,500,912,'𝒫 = {A, B, C, D}',37,'math','middle')
    path(g,'M500,934V976','local',True)
    for y,label in [(1070,'k₁'),(1185,'k₂')]:
        txt(g,128,y-21,label,34,'math')
        rail(g,203,y,639)
    block(g,245,1002,150,58,'A',depth=13)
    block(g,446,1002,150,58,'B',True,13)
    block(g,646,1002,150,58,'D',depth=13)
    block(g,245,1117,150,58,'C',depth=13)
    txt(g,500,1234,'a：归核    π：核内顺序',27,'math','middle')
    txt(g,500,1281,'初始构造 / 已有方案 · 完整验证',24,'muted','middle')
    s=group(g,'current-state','共同维护的当前最好可行方案及执行记录')
    path(s,'M143,1315H833L850,1332V1424L833,1441H143L126,1424V1332Z','hatch')
    box(s,140,1327,696,102,'state')
    txt(s,488,1363,'当前最好可行方案',30,'bold','middle')
    txt(s,488,1410,'x = (𝒫, a, π)',38,'math','middle')

def neighborhoods(root):
    g=group(root,'neighborhoods','02 多邻域迭代：每轮选择一个来源，四类来源共享当前方案')
    head(g,1070,263,'02','多邻域迭代改进','同一当前方案 · 互补候选来源')
    s=group(g,'source-selection')
    box(s,1075,348,870,99,'panel',rx=7)
    txt(s,1510,387,'每轮选择一个来源',31,'bold','middle')
    txt(s,1510,426,'兼顾改进收益与评估成本',25,'muted','middle')
    path(g,'M1510,453V483','local',True)
    path(g,'M1075,872H1945','faint')
    a=group(g,'source-base','基础构造：同一原图的不同划分粒度')
    source_head(a,1075,523,'a','基础构造','多粒度 · 关键路径 · 负载映射')
    h=group(a,'coarse-fine-example',transform='translate(1088,592)')
    for d in ['M24,100C60,100 57,38 103,38','M24,100C60,100 57,164 103,164','M125,38H261','M125,164H261','M283,38C331,38 322,100 362,100','M283,164C331,164 322,100 362,100']:
        path(h,d,'hair')
    boundary(h,187,38,113,43,True,False);boundary(h,187,164,113,43,False,False)
    for x,y,k in [(22,100,1),(116,38,2),(272,38,4),(116,164,3),(272,164,5),(364,100,6)]:op(h,x,y,k,20,21)
    for x in [77,204]: box(h,x,121,105,83,'dashbox',rx=13)
    txt(a,1277,838,'探索不同分组粒度',23,'muted','middle')
    b=group(g,'source-structure','依赖结构与负载：迁移、交换和拆分')
    source_head(b,1540,523,'b','依赖结构与负载','迁移 · 交换 · 拆分')
    for y,label in [(646,'k₁'),(756,'k₂')]:
        txt(b,1542,y-6,label,25,'math');path(b,f'M1600,{y}H1930','fine',True)
    block(b,1605,591,78,45,'A',depth=8,size=27)
    box(b,1718,591,78,45,'dashbox');txt(b,1757,622,'B',26,'muted math','middle')
    block(b,1830,591,78,45,'D',depth=8,size=27)
    block(b,1718,701,78,45,'B',True,8,27)
    block(b,1830,701,78,45,'C',depth=8,size=27)
    path(b,'M1757,645C1798,668 1792,685 1757,690','local',True)
    txt(b,1740,838,'B = {o₂, o₄}  →  B₁ | B₂',25,'math','middle')
    c=group(g,'source-residency','驻留数据重组：缩短关联张量的活跃跨度')
    source_head(c,1075,923,'c','驻留数据重组','调整分组与顺序，缩短驻留','memory')
    for row,indices in [(1059,[2,3,4,5]),(1190,[2,4,3,5])]:
        for i,k in enumerate(indices):block(c,1099+94*i,row-45,65,42,'o'+str(k).translate(SUB),depth=6,size=24)
    for d in ['M1131,1008C1131,953 1319,953 1319,1008','M1225,1008C1225,976 1413,955 1413,1008','M1131,1140C1131,1082 1225,1082 1225,1140','M1319,1140C1319,1082 1413,1082 1413,1140']:
        path(c,d,'memory-arc')
    txt(c,1220,979,'t₂',21,'math','middle');txt(c,1375,989,'t₃',21,'math','middle')
    txt(c,1178,1103,'t₂',21,'math','middle');txt(c,1366,1103,'t₃',21,'math','middle')
    path(c,'M1466,1070V1148','local',True)
    txt(c,1277,1244,'让相关计算更靠近',23,'muted','middle')
    d=group(g,'source-fifo','FIFO 事件时序：只重排核内子图，执行后重新确认实际命中')
    source_head(d,1540,923,'d','FIFO 事件时序 · Q3','保持划分与归核，仅调整 π','fifo')
    box(d,1624,1018,214,145,'fifo-window')
    txt(d,1731,1081,'驻留窗口',26,'muted','middle')
    path(d,'M1563,1163H1933','fine',True)
    for x in [1624,1731,1838,1908]:path(d,f'M{x},1150V1178','hair')
    path(d,'M1908,1154V1030Q1908,998 1875,998H1763Q1731,998 1731,1030V1137','local',True)
    el(d,'circle',cx=1731,cy=1163,r=7,**{'class':'filled-dot'})
    el(d,'circle',cx=1908,cy=1163,r=7,**{'class':'paper'})
    for x,s in [(1624,'fₜ'),(1731,'s′ₜ'),(1838,'eₜ'),(1908,'sₜ')]:txt(d,x,1205,s,26,'math','middle')
    txt(d,1741,1244,'复用落入有效缓存窗口',23,'muted','middle')
    path(g,'M1510,1270V1304','local',True)
    s=group(g,'candidate','候选完整方案及低成本筛选')
    box(s,1090,1315,830,126,'panel',rx=7)
    txt(s,1505,1366,'完整候选  y = (𝒫′, a′, π′)',34,'math','middle')
    txt(s,1505,1414,'结构预检 · 去重 · 下界筛选',27,'muted','middle')

def core(parent,x,y,name,tasks):
    g=group(parent,'core-'+name)
    txt(g,x+159,y-118,name,31,'bold math','middle')
    for i,label in enumerate(tasks):block(g,x+38+i*140,y-58,108,45,label,label=='B',9,29)
    block(g,x,y+24,312,248,depth=26,ident='processor-'+name)
    for i,(label,offset,length) in enumerate([('M',28,108),('V',52,93),('MTE2',-6,110),('MTE3',75,71)]):
        yy=y+72+i*48
        txt(g,x+17,yy+8,label,21,'math')
        path(g,f'M{x+88},{yy+19}H{x+291}','faint')
        box(g,x+106+offset,yy-9,length,20,'hatch')
    for xx,label in [(x+12,'L1'),(x+168,'UB')]:block(g,xx,y+346,131,67,label,depth=15,size=30)
    path(g,f'M{x+74},{y+333}V{y+289}','local',True)
    path(g,f'M{x+234},{y+289}V{y+333}','local',True)
    return g

def execution(root):
    g=group(root,'execution','03 统一执行评价：三问统一方案空间、不同执行环境')
    head(g,2110,263,'03','统一执行评价','重建执行过程，评价整体效果')
    for x,w,title,sub in [(2110,248,'Q1','子图级任务'),(2393,246,'Q2','核心级任务'),(2665,255,'Q3','核心任务 + L2')]:
        txt(g,x+w/2,368,title,27,'bold math','middle')
        txt(g,x+w/2,407,sub,25,'muted','middle')
        path(g,f'M{x+16},427H{x+w-16}','faint')
    core(g,2120,566,'核心 k₁',['A','D'])
    core(g,2555,566,'核心 k₂',['B','C'])
    # Data paths are local hardware relationships, not search-control connectors.
    path(g,'M2194,988C2146,1024 2140,1060 2212,1095','local',True)
    txt(g,2107,1055,'COPY_OUT',21,'math')
    path(g,'M2698,1095C2575,1069 2563,1036 2630,990','local',True)
    txt(g,2745,1055,'COPY_IN',21,'math','middle')
    cube(g,2159,1078,None,.72)
    cube(g,2855,1078,None,.72)
    b=block(g,2196,1110,650,74,depth=20,ident='shared-ddr')
    txt(b,2521,1142,'DDR 共享带宽池',29,'math','middle')
    txt(b,2521,1173,'60 B/周期',23,'math muted','middle')
    b=block(g,2360,1220,486,67,depth=17,ident='readonly-l2-q3')
    txt(b,2603,1261,'只读 L2 · FIFO · Q3',28,'math','middle')
    path(g,'M2378,1185H2328Q2308,1185 2308,1206V1249H2348','dashed',True)
    path(g,'M2867,1248C2956,1193 2953,1021 2802,991','local',True)
    txt(g,2963,1150,'命中读',21,'muted','middle',transform='rotate(-90,2963,1150)')
    txt(g,2167,1238,'读完成尝试填充',20,'muted')
    txt(g,2167,1268,'命中不刷新',20,'muted')
    txt(g,2510,1308,'任务 · 存储 · 流水线 · 共享带宽',23,'muted','middle')
    s=group(g,'execution-result','完整执行产生总体完成时间；可行性和额外COPY见独立说明')
    box(s,2100,1328,820,126,'panel',rx=7)
    txt(s,2510,1365,'总体任务执行时间（Makespan）',29,'bold','middle')
    formula(s,2510,1421,[('C',False),('q',True),('(y) = max',False),('j',True),('\u2002f',False),('j',True)],42)

def links(root):
    g=group(root,'method-flow','仅四条跨模块连接：当前方案、候选、执行反馈与结束输出')
    for ident,d,source,target in [
      ('state-to-candidate','M863,1378H1072','current-state','candidate'),
      ('candidate-to-execution','M1932,1378H2082','candidate','execution-result'),
      ('evaluation-feedback','M2510,1463V1529Q2510,1560 2478,1560H524Q488,1560 488,1524V1454','execution-result','current-state'),
      ('stop-to-output','M1500,1560V1682','evaluation-feedback','final-output')]:
        p=path(g,d,'feedback' if ident=='evaluation-feedback' else 'main',False,id=ident,data_source=source,data_target=target,data_main='true')
        p.set('marker-end','url(#main-arrow)')
    txt(g,1500,1534,'执行反馈：保留更优可行方案，更新方案与执行轨迹',29,'bold','middle')
    txt(g,540,1610,'预算内持续迭代',25,'muted')
    txt(g,1537,1644,'搜索结束',26,'muted')
    s=group(root,'final-output','搜索结束后输出已验证方案；Q3同方案有无L2配对仅为结果分析')
    box(s,488,1695,2022,118,'output',rx=7)
    txt(s,1500,1744,'输出已验证的最好方案  +  执行记录与指标',34,'bold','middle')
    txt(s,1500,1787,'Q3：固定同一方案，对照有 / 无 L2',26,'muted','middle')

def create_svg(palette='mono'):
    p=PALETTES[palette]
    root=E.Element('{'+NS+'}svg',dict(width='420mm',height='262.5mm',viewBox='0 0 3000 1875',role='img',**{'aria-labelledby':'title description'}))
    el(root,'title',id='title').text='计算图调度的联合优化：联合决策—多邻域迭代—统一执行（第三版）'
    el(root,'desc',id='description').text='六算子划分及归核、四类互补候选、统一执行模型，以四条跨模块箭头组成反馈优化。无图例，无代码级判断菱形。内部例子为机制示意，非实测轨迹。'
    el(root,'metadata').text=json.dumps(dict(version=3,source_commit=SOURCE_COMMIT,source='ink_v2 + workshop_v2 manuscript',palette=palette,main_connectors=4),ensure_ascii=False)
    defs=el(root,'defs')
    el(defs,'style').text=f'''
text{{font-family:'Noto Sans CJK SC','Microsoft YaHei',sans-serif;fill:{p['ink']};stroke:none}}
.math,.serif{{font-family:'Noto Serif CJK SC','Noto Serif','FreeSerif',serif}}
.bold{{font-weight:700}} .muted{{fill:#606060}} .white{{fill:white}}
path,rect,ellipse{{stroke-linecap:round;stroke-linejoin:round}}
.fine,.local{{fill:none;stroke:{p['ink']};stroke-width:1.9}}
.hair,.engrave{{fill:none;stroke:#747474;stroke-width:1.0}}
.engrave{{opacity:.66}} .faint{{fill:none;stroke:#cececa;stroke-width:1.5}}
.paper{{fill:white;stroke:{p['ink']};stroke-width:1.9}}
.hatch{{fill:url(#hatch);stroke:{p['ink']};stroke-width:1.5}}
.dark{{fill:{p['structure']};stroke:{p['structure']};stroke-width:1.7}}
.boundary{{fill:url(#sparse);stroke:#515151;stroke-width:2.1;stroke-dasharray:9 7}}
.accent{{fill:url(#accent-hatch);stroke:{p['structure']}}}
.dashbox{{fill:none;stroke:#777;stroke-width:1.6;stroke-dasharray:6 5}}
.badge{{stroke:none;fill:{p['structure']}}} .badge.memory{{fill:{p['memory']}}} .badge.fifo{{fill:{p['fifo']}}}
.panel{{fill:white;stroke:#93938d;stroke-width:1.65}}
.state,.output{{fill:{p['wash']};stroke:#6c6c66;stroke-width:1.7}}
.memory-arc{{fill:none;stroke:{p['memory']};stroke-width:3.4}}
.fifo-window{{fill:url(#sparse);stroke:{p['fifo']};stroke-width:1.6}}
.filled-dot{{fill:{p['fifo']};stroke:none}}
.dashed{{fill:none;stroke:#777;stroke-width:1.6;stroke-dasharray:6 5}}
.main{{fill:none;stroke:{p['ink']};stroke-width:3.8}}
.feedback{{fill:none;stroke:{p['structure']};stroke-width:3.1}}
'''
    for name,step,color,back in [('hatch',6,'#62625e','white'),('sparse',13,'#bbbcb5','white'),('accent-hatch',10,p['structure'],p['wash'])]:
        pa=el(defs,'pattern',id=name,width=step,height=step,patternUnits='userSpaceOnUse')
        el(pa,'rect',width=step,height=step,fill=back)
        el(pa,'path',d=f'M-1,1L1,-1M0,{step}L{step},0M{step-1},{step+1}L{step+1},{step-1}',stroke=color,stroke_width='.65',fill='none')
    for name,size in [('arrow',10),('main-arrow',23)]:
        m=el(defs,'marker',id=name,viewBox='0 0 12 12',markerWidth=size,markerHeight=size,refX='11',refY='6',orient='auto',markerUnits='userSpaceOnUse')
        el(m,'path',d='M0,0L12,6L0,12L3,6Z',fill=p['ink'],stroke='none')
    cube_g=group(defs,'tensor-cube')
    path(cube_g,'M-17,-14H10L22,-25H-5Z','paper')
    path(cube_g,'M10,-14L22,-25V6L10,18Z','hatch')
    box(cube_g,-17,-14,27,32,'hatch')
    page=group(root,'page','版面与标题')
    el(page,'rect',width=3000,height=1875,fill='white')
    path(page,'M88,60H2915','main')
    txt(page,90,134,'计算图调度的联合优化',55,'serif bold')
    txt(page,93,186,'联合决策 — 多邻域迭代 — 统一执行',29)
    txt(page,2910,124,'问题 A · 总体求解流程',28,'serif','end')
    txt(page,2910,178,'划分、计算并行与数据复用的协同优化',24,'muted','end')
    path(page,'M90,219H2915','fine')
    path(page,'M995,336V1266M2046,336V1266','faint')
    joint(root);neighborhoods(root);execution(root);links(root)
    path(page,'M90,1847H2915','fine')
    for i, t in enumerate(root.iter('{'+NS+'}text')):
        t.set('id', f'label-{i:03d}')
    return root

def inspect(root):
    ids=[e.attrib['id'] for e in root.iter() if 'id' in e.attrib]
    if len(ids)!=len(set(ids)): raise ValueError('Duplicate SVG object IDs')
    text=''.join(root.itertext())
    for removed in ['可行且字典序严格改善','Step1','Step2','Step3','停止？','图例']:
        if any(removed in (e.text or '') for e in root.iter('{'+NS+'}text')):raise ValueError('Removed annotation found: '+removed)
    connectors=[e for e in root.iter() if e.get('data-main')=='true']
    assert len(connectors)==4
    assert not list(root.iter('{'+NS+'}image'))
    assert len(list(root.iter('{'+NS+'}text')))>90
    return {'main_connectors':len(connectors),'embedded_images':0,'text_objects':len(list(root.iter('{'+NS+'}text'))),'unique_ids':True,'source_commit':SOURCE_COMMIT}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--palette',choices=PALETTES,default='mono')
    ap.add_argument('--all-palettes',action='store_true')
    ap.add_argument('--svg-only',action='store_true')
    ap.add_argument('--width',type=int,default=6000,help='High resolution PNG width')
    args=ap.parse_args()
    for name in PALETTES if args.all_palettes else [args.palette]:
        root=create_svg(name);report=inspect(root)
        assets=HERE/'assets';exports=HERE/'exports';assets.mkdir(exist_ok=True);exports.mkdir(exist_ok=True)
        svg=assets/f'workflow_v3_{name}.svg'
        E.indent(root,space='  ');E.ElementTree(root).write(svg,encoding='utf-8',xml_declaration=True)
        if not args.svg_only:
            ink=shutil.which('inkscape')
            if not ink:raise SystemExit('SVG created. Install Inkscape and add it to PATH for PDF/PNG export.')
            outputs=[('pdf',None),( 'png',args.width),('preview.png',1800)]
            for suffix,width in outputs:
                out=exports/f'workflow_v3_{name}.{suffix}'
                cmd=[ink,str(svg),f'--export-filename={out}','--export-area-page']
                if width:cmd += [f'--export-width={width}','--export-background=white','--export-background-opacity=1']
                subprocess.run(cmd,check=True,timeout=120,capture_output=True)
        (exports/f'inspection_{name}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(svg)
if __name__=='__main__':main()
