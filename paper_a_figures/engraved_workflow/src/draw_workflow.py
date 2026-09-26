#!/usr/bin/env python3
"""Editable, deterministic scientific engraving. Python stdlib only for SVG.
Run from any directory: python src/draw_workflow.py [--out DIR].
No raster artwork, generative models, network calls, or converted-to-path text.
"""
from __future__ import annotations
import argparse
import math
import re
from contextlib import contextmanager
from html import escape
from pathlib import Path

W, H = 3000, 2120
INK, GRAY, LIGHT = '#171717', '#505050', '#b6b6b6'
SUB = str.maketrans('0123456789','₀₁₂₃₄₅₆₇₈₉')

class Drawing:
    def __init__(self):
        self.parts: list[str] = []
    def add(self, s: str): self.parts.append(s)
    @contextmanager
    def group(self, name: str, label: str, transform: str = '', layer: bool = False):
        attrs = f' id="{name}"'
        if layer: attrs += f' inkscape:groupmode="layer" inkscape:label="{escape(label)}"'
        if transform: attrs += f' transform="{transform}"'
        self.add(f'<g{attrs}><title>{escape(label)}</title>')
        yield
        self.add('</g>')
    def path(self, d: str, cls='fine', **attrs):
        a=' '.join(f'{k.replace("_","-")}="{v}"' for k,v in attrs.items())
        self.add(f'<path class="{cls}" d="{d}" {a}/>')
    def line(self,x1,y1,x2,y2,cls='fine',**attrs):
        self.path(f'M{x1:g},{y1:g}H{x2:g}' if y1==y2 else f'M{x1:g},{y1:g}L{x2:g},{y2:g}',cls,**attrs)
    def rect(self,x,y,w,h,cls='outline',**attrs):
        a=' '.join(f'{k.replace("_","-")}="{v}"' for k,v in attrs.items())
        self.add(f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" class="{cls}" {a}/>')
    def ellipse(self,x,y,rx,ry,cls='outline',**attrs):
        a=' '.join(f'{k.replace("_","-")}="{v}"' for k,v in attrs.items())
        self.add(f'<ellipse cx="{x:g}" cy="{y:g}" rx="{rx:g}" ry="{ry:g}" class="{cls}" {a}/>')
    def text(self,x,y,s,size=28,cls='',anchor='start'):
        body = escape(s)
        if 'math' in cls:
            body = re.sub(r'([_^])(?:\{([^}]+)\}|([A-Za-z]))',
                lambda m: '<tspan baseline-shift="'+('sub' if m[1]=='_' else 'super')+'" font-size="70%">'+(m[2] or m[3])+'</tspan>', body)
        self.add(f'<text x="{x:g}" y="{y:g}" font-size="{size:g}" text-anchor="{anchor}" class="{cls}">{body}</text>')
    def arrow(self,d,cls='route'):
        self.path(d,cls,marker_end='url(#arrow)')
    def fibre(self,x1,y1,x2,y2,c1x,c1y,c2x,c2y,n=7):
        """Contour engraved around one main directional route, not extra graph edges."""
        distance=math.hypot(x2-x1,y2-y1)
        count=n+6 if distance>220 else n
        t1=math.hypot(c1x-x1,c1y-y1) or 1
        t2=math.hypot(x2-c2x,y2-c2y) or 1
        for i in range(count):
            q=(i-(count-1)/2)*4.2
            a,b=c1x-q*(c1y-y1)/t1,c1y+q*(c1x-x1)/t1
            c,e=c2x-q*(y2-c2y)/t2,c2y+q*(x2-c2x)/t2
            self.path(f'M{x1:g},{y1:g}C{a:.1f},{b:.1f} {c:.1f},{e:.1f} {x2:g},{y2:g}', 'hair')
        self.arrow(f'M{x1:g},{y1:g}C{c1x:g},{c1y:g} {c2x:g},{c2y:g} {x2:g},{y2:g}')
    def tensor(self,x,y,name='',scale=1):
        self.add(f'<g transform="translate({x:g},{y:g}) scale({scale:g})">')
        self.path('M-22,-15L11,-15L24,-27L-9,-27Z','paper')
        self.path('M11,-15L24,-27V7L11,20Z','hatch')
        self.rect(-22,-15,33,35,'grid')
        if name:self.text(-3,48,name,25,'math','middle')
        self.add('</g>')
    def op(self,x,y,name,small=False):
        rx,ry=(24,18) if small else (43,30)
        self.ellipse(x,y,rx+9,ry+8,'paper')
        for i in range(30 if not small else 18):
            a = math.tau*i/(30 if not small else 18)
            self.line(round(x+(rx+1)*math.cos(a),1),round(y+(ry+1)*math.sin(a),1),round(x+(rx+8)*math.cos(a),1),round(y+(ry+7)*math.sin(a),1),'hair')
        self.ellipse(x,y,rx,ry,'paper')
        self.text(x,y+9,name,23 if small else 30,'math','middle')
    def slab(self,x,y,w,h,label='',dark=False,depth=13):
        self.path(f'M{x:g},{y:g}l{depth:g},-{depth:g}h{w:g}l-{depth:g},{depth:g}Z','hatch')
        self.path(f'M{x+w:g},{y:g}l{depth:g},-{depth:g}v{h:g}l-{depth:g},{depth:g}Z','hatch')
        self.rect(x,y,w,h,'black' if dark else 'paper')
        if label:self.text(x+w/2,y+h/2+10,label,29,'white math' if dark else 'math','middle')
    def header(self,x,y,n,title,subtitle=''):
        self.text(x,y,n,42,'serif')
        self.text(x+82,y-1,title,39,'bold')
        if subtitle:self.text(x+82,y+41,subtitle,24,'muted')
    def label(self,x,y,n,title):
        self.ellipse(x+17,y-10,17,17,'black')
        self.text(x+17,y-3,n,19,'white','middle')
        self.text(x+48,y,title,31,'bold')

D=Drawing()

def definitions():
    D.add(f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" width="420mm" height="296.8mm" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title desc">
<title id="title">计算图调度的联合优化：联合决策—统一执行—多邻域迭代改进</title>
<desc id="desc">可编辑黑白线刻流程图。以六算子分叉汇合案例表达划分、归核、顺序、候选生成、预检、完整执行、字典序接受与反馈；第三问固定同一方案作无L2对照。案例为机制示意，不是实测计划。</desc>
<defs>
<style>
text{{font-family:'Noto Sans CJK SC','Microsoft YaHei',sans-serif;fill:{INK};stroke:none}}
.serif,.math{{font-family:'Noto Serif CJK SC','STIX','Noto Serif',serif}}
.halo{{paint-order:stroke;stroke:white;stroke-width:7;stroke-linejoin:round}}
.bold{{font-weight:700}}.muted{{fill:{GRAY}}}.white{{fill:white}}
path,rect,ellipse{{stroke-linecap:round;stroke-linejoin:round}}
.fine{{fill:none;stroke:{INK};stroke-width:1.6}}
.hair{{fill:none;stroke:{GRAY};stroke-width:.85}}
.faint{{fill:none;stroke:{LIGHT};stroke-width:1.1}}
.route{{fill:none;stroke:{INK};stroke-width:3}}
.outline{{fill:none;stroke:{INK};stroke-width:2}}
.paper{{fill:white;stroke:{INK};stroke-width:2}}
.black{{fill:{INK};stroke:{INK};stroke-width:1.5}}
.hatch{{fill:url(#hatch);stroke:{INK};stroke-width:1.3}}
.grid{{fill:url(#grid);stroke:{INK};stroke-width:1.8}}
.dashed{{fill:none;stroke:{GRAY};stroke-width:1.6;stroke-dasharray:7 6}}
.boundary{{fill:url(#sparse);stroke:{INK};stroke-width:2.3;stroke-dasharray:10 5}}
</style>
<pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse"><rect width="6" height="6" fill="white"/><path d="M-1,1L1,-1M0,6L6,0M5,7L7,5" stroke="{INK}" stroke-width=".6"/></pattern>
<pattern id="sparse" width="12" height="12" patternUnits="userSpaceOnUse"><rect width="12" height="12" fill="white"/><path d="M0,12L12,0" stroke="{LIGHT}" stroke-width=".5"/></pattern>
<pattern id="grid" width="7" height="7" patternUnits="userSpaceOnUse"><rect width="7" height="7" fill="white"/><path d="M7,0H0V7" fill="none" stroke="{INK}" stroke-width=".55"/></pattern>
<marker id="arrow" viewBox="0 0 10 10" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto-start-reverse" markerUnits="userSpaceOnUse"><path d="M0,0L10,5L0,10L2.6,5Z" fill="{INK}"/></marker>
</defs>''')

def input_plate():
    with D.group('joint-decision','01 联合决策：同一个计算图、划分、核心归属与核内顺序',layer=True):
        D.header(88,277,'01','联合决策','只改变划分、核心归属与核内顺序')
        D.text(92,348,'输入：G、问题 q、核数 n、配置 θ 与预算',24,'muted')
        D.text(92,381,'G = (T ∪ O, E)',34,'math')
        D.text(914,381,'原始算子与依赖保持不变',25,'muted','end')
        # The six-operator diamond is a designed mechanism example.
        with D.group('bipartite-example','贯穿案例：A={o1}, B={o2,o4}, C={o3,o5}, D={o6}','translate(116,421) scale(.91)'):
            D.path('M254,38C294,2 500,4 567,40C603,65 603,153 565,176C505,210 296,208 254,175C222,148 220,71 254,38Z','boundary')
            D.path('M254,303C294,267 500,269 567,305C603,330 603,418 565,441C505,475 296,473 254,440C222,413 220,336 254,303Z','boundary')
            D.ellipse(94,240,60,82,'boundary');D.ellipse(741,240,60,82,'boundary')
            # Curved engraving stays inside the single dashed group envelope.
            for cy in (107,372):
                for i in range(15):
                    z=i*1.8
                    D.path(f'M{244+z*.3:g},{cy-38-z*.45:g}C285,{cy-103+z:g} 535,{cy-103+z:g} {581-z*.3:g},{cy-38-z*.45:g}','hair')
                    D.path(f'M{244+z*.3:g},{cy+38+z*.45:g}C285,{cy+103-z:g} 535,{cy+103-z:g} {581-z*.3:g},{cy+38+z*.45:g}','hair')
            # Actual bipartite edges. Every visible dependency meets a tensor port.
            edges=['M-33,240H43','M145,240H174',
                   'M215,224C253,219 252,150 263,128',
                   'M215,257C253,262 252,329 263,350',
                   'M352,107H383','M429,107H468',
                   'M352,372H383','M429,372H468',
                   'M572,107H612','M572,372H612',
                   'M654,117C685,124 700,180 717,205',
                   'M654,362C685,355 700,300 717,275',
                   'M792,240H843']
            for d in edges:D.arrow(d,'fine')
            D.tensor(198,240,'t₁',1.02)
            for xx,yy,t in [(-58,240,'t₀'),(410,107,'t₂'),(410,372,'t₃'),(636,107,'t₄'),(636,372,'t₅'),(870,240,'t₆')]:D.tensor(xx,yy,t,.94)
            for xx,yy,s in [(94,240,'o₁'),(300,107,'o₂'),(300,372,'o₃'),(520,107,'o₄'),(520,372,'o₅'),(741,240,'o₆')]:D.op(xx,yy,s)
            for xx,yy,s in [(94,351,'A'),(414,14,'B'),(414,511,'C'),(741,351,'D')]:D.text(xx,yy,s,33,'serif','middle')
        D.text(92,951,'𝒫 = {A, B, C, D}',32,'math')
        D.text(914,951,'非边界算子完整覆盖、互不相交',25,'muted','end')
        # Fan from membership labels into the ordered core rails.
        D.fibre(279,987,303,1058,281,1005,303,1021,5)
        D.fibre(457,987,487,1058,457,1010,487,1036,5)
        D.fibre(654,987,319,1177,663,1084,324,1083,5)
        D.fibre(812,987,679,1058,809,1028,736,1035,5)
        for y,k,blocks in [(1084,'k₁',[(245,'A'),(430,'B'),(625,'D')]),(1203,'k₂',[(245,'C')])]:
            D.text(115,y+35,k,35,'math')
            D.path(f'M185,{y+66}H864l18,-18H204Z','hatch')
            D.arrow(f'M180,{y+80}H884','fine')
            for xx,ss in blocks:D.slab(xx,y,138,57,ss,ss=='B')
        D.text(841,1320,'a：归属核心   π：每核排列',27,'math','end')
        D.arrow('M865,1274C904,1323 903,1338 854,1370','fine')
        D.text(92,1395,'基础构造 / 历史方案',28,'bold')
        D.arrow('M382,1384H468')
        D.text(490,1395,'目标配置下先完整验证',27)
        D.arrow('M806,1409C853,1444 782,1481 728,1481')
        D.path('M189,1455H721L748,1482L721,1515H189L165,1482Z','hatch')
        D.rect(197,1462,514,45,'paper')
        D.text(453,1494,'当前最好可行方案 x  +  执行记录',27,'bold','middle')
        D.fibre(752,1482,1056,430,1007,1482,981,430,7)

def neighborhoods():
    with D.group('neighborhoods','02 多邻域候选与来源选择',layer=True):
        D.header(1030,277,'02','多邻域迭代改进','所有来源共享同一个当前最好方案')
        D.text(1503,388,'每轮只选择一个来源',32,'bold','middle')
        D.text(1503,432,'初次覆盖 · 近期收益 / 成本 · 失败比例',25,'','middle')
        D.text(1503,468,'访问间隔 · 剩余预算准入',25,'muted','middle')
        D.line(1070,492,1928,492,'fine')
        # Each source is an attached study, not an independently optimized branch.
        with D.group('source-base','基础构造：粒度、关键性排序与负载映射'):
            D.label(1050,555,'a','基础构造')
            D.text(1050,594,'粒度 · 关键性排序 · 负载映射',24,'muted')
            # One legible projection of the SAME six-operator graph.
            pts=[(1084,715),(1186,650),(1186,780),(1320,650),(1320,780),(1432,715)]
            for cy in (650,780):
                D.path(f'M1143,{cy-30}Q1250,{cy-68} 1362,{cy-30}V{cy+30}Q1250,{cy+68} 1143,{cy+30}Z','boundary')
            for a,b in [(0,1),(0,2),(1,3),(2,4),(3,5),(4,5)]:
                ax,ay=pts[a];bx,by=pts[b]
                D.arrow(f'M{ax+28},{ay}C{ax+52},{ay} {bx-45},{by} {bx-30},{by}','fine')
            for j,(xx,yy) in enumerate(pts):D.op(xx,yy,'o'+str(j+1).translate(SUB),True)
            D.text(1245,881,'同一图的算子投影 / 分组粒度可变',23,'muted','middle')
        with D.group('source-structure','结构与负载：迁移、交换、拆分、联合迁移'):
            D.label(1541,555,'b','依赖结构与负载')
            D.text(1541,594,'迁移 · 交换 · 拆分 · 联合迁移',24,'muted')
            for y,k in [(641,'k₁'),(741,'k₂')]:
                D.text(1545,y+33,k,27,'math');D.arrow(f'M1593,{y+58}H1940','fine')
            D.slab(1607,641,69,46,'A',depth=8)
            D.rect(1710,641,69,46,'dashed');D.text(1744,674,'B',28,'muted math','middle')
            D.slab(1836,641,69,46,'D',depth=8)
            D.slab(1677,741,69,46,'B',True,depth=8);D.slab(1836,741,69,46,'C',depth=8)
            D.fibre(1743,691,1711,728,1780,727,1775,730,5)
            D.text(1541,854,'B = {o₂, o₄}',27,'math')
            D.arrow('M1719,844H1760','fine')
            D.text(1791,854,'B₁ | B₂',27,'math')
        D.line(1050,922,1940,922,'faint')
        with D.group('source-residency','驻留重组：生产消费次序与张量存活区间'):
            D.label(1050,969,'c','驻留数据重组')
            D.text(1050,1008,'改变分组 / 顺序，缩短驻留区间',24,'muted')
            for row,y in enumerate((1140,1246)):
                labels=('o₂','o₃','o₄','o₅') if row==0 else ('o₂','o₄','o₃','o₅')
                for xx,lab in zip((1075,1171,1267,1363),labels):D.slab(xx,y,58,38,lab,depth=6)
                pairs=((1104,1296),(1200,1392)) if row==0 else ((1104,1200),(1296,1392))
                for j,(a,b) in enumerate(pairs):
                    height=62+18*j if row==0 else 41
                    for h in range(7):
                        D.path(f'M{a},{y-8}C{a},{y-height-h*2} {b},{y-height-h*2} {b},{y-8}','hair')
                    D.text((a+b)/2,y-height-7,'t₂' if j==0 else 't₃',24,'math','middle')
            D.arrow('M1455,1128V1212','fine')
            D.text(1050,1318,'由驻留分析提出候选，Spill 由执行器决定',22,'muted')
        with D.group('source-fifo','FIFO事件时序：仅第三问、只修改合法核内顺序'):
            D.label(1541,969,'d','FIFO 事件时序 · Q3')
            D.text(1541,1008,'𝒫、a 保持不变，仅重排 π',25,'math')
            D.rect(1612,1086,209,77,'hatch')
            D.text(1716,1136,'驻留窗口',28,'bold','middle')
            D.arrow('M1544,1188H1950','fine')
            for x,s in [(1612,'fₜ'),(1821,'eₜ'),(1904,'sₜ')]:
                D.line(x,1080,x,1204,'fine');D.text(x,1240,s,29,'math','middle')
            D.ellipse(1904,1188,7,7,'paper');D.ellipse(1713,1188,7,7,'black')
            D.fibre(1904,1080,1713,1080,1880,1021,1750,1021,5)
            D.text(1712,1240,'s′ₜ',29,'math','middle')
            D.text(1541,1289,'填充后、淘汰前：fₜ ≤ s′ₜ < eₜ',25,'math')
            D.text(1541,1325,'同刻按事件顺序；新时序须完整重演',22,'muted')
        D.text(1503,1397,'完整候选  y = (𝒫′, a′, π′)',34,'math','middle')
        D.path('M1255,1348C1255,1363 1430,1346 1503,1346','fine')
        D.path('M1750,1348C1750,1363 1575,1346 1503,1346','fine')
        D.arrow('M1503,1346V1359','fine')
        D.line(1070,1427,1938,1427,'route')
        D.text(1090,1475,'结构预检 / 去重',30,'bold')
        D.text(1090,1516,'覆盖 · 唯一归核 · 合图无环',24)
        D.line(1480,1452,1480,1530,'fine')
        D.text(1513,1475,'有效下界筛选',30,'bold')
        D.text(1513,1516,'L(y) > U 筛去；等号保留',25,'math')
        D.text(1513,1554,'U = C_q(x)',22,'math muted')
        D.fibre(1933,1479,2118,1455,1993,1479,2066,1455,7)
        D.text(2008,1415,'通过',24,'muted','middle')
        # A rejected candidate returns to source selection, not to result acceptance.
        D.arrow('M1938,1528C1982,1528 1980,500 1960,470C1951,453 1941,437 1931,435','dashed')
        D.text(1999,1173,'筛',22,'muted','middle');D.text(1999,1205,'去',22,'muted','middle');D.text(1999,1237,'重',22,'muted','middle');D.text(1999,1269,'选',22,'muted','middle')

def core(x,y,name,groups):
    # Open, engraved axonometric cutaway. Top tiles are the candidate's core order.
    D.text(x+142,y-44,name,31,'bold','middle')
    for i,s in enumerate(groups):D.slab(x+27+i*127,y-13,102,42,s,s=='B',depth=8)
    D.path(f'M{x},{y+72}l32,-28h294l-32,28Z','grid')
    D.path(f'M{x+294},{y+72}l32,-28v225l-32,28Z','hatch')
    D.rect(x,y+72,294,225,'paper')
    for i,(lab,pos,length) in enumerate([('M',55,125),('V',96,105),('MTE2',8,118),('MTE3',150,80)]):
        yy=y+99+47*i
        D.text(x+7,yy+15,lab,22,'math')
        D.line(x+77,yy+15,x+277,yy+15,'faint')
        D.rect(x+77+pos*.6,yy, length*.72,22,'hatch')
        D.line(x+77,yy+28,x+275,yy+28,'hair')
    for xx,label in [(x+8,'L1'),(x+155,'UB')]:
        D.slab(xx,y+342,123,68,label,depth=13)
        for j in range(7):D.line(xx+7,y+392+j*2,xx+115,y+392+j*2,'hair')
    for sx,ex in [(x+83,x+60),(x+223,x+215)]:D.fibre(sx,y+300,ex,y+326,sx,y+312,ex,y+312,5)

def execution_plate():
    with D.group('execution','03 固定执行器：重建任务与COPY、自动Spill、Pipe、DDR和FIFO',layer=True):
        D.header(2090,277,'03','统一执行','以 y 重建执行，不沿用旧方案的周期')
        D.text(2090,378,'示例候选：B 迁至 k₂',29,'bold')
        D.text(2898,378,'ℰ_q(G, y; θ)',33,'math','end')
        core(2130,466,'核心 k₁',('A','D'))
        core(2545,466,'核心 k₂',('B','C'))
        # Boundary data traffic, shared resource surfaces and distinct paths.
        D.fibre(2195,885,2265,1060,2080,950,2110,1070,9)
        D.fibre(2314,1060,2354,885,2352,1000,2375,945,7)
        D.fibre(2642,885,2680,1060,2556,970,2541,1020,9)
        D.fibre(2778,1060,2790,885,2912,999,2890,949,7)
        D.text(2100,949,'COPY_OUT',23,'halo')
        D.text(2790,949,'COPY_IN',23,'halo','end')
        # Tensor packets are objects, not decorative logos.
        D.tensor(2190,996,'',.78);D.tensor(2821,1001,'',.78)
        D.slab(2180,1080,637,82,'DDR  共享带宽池 · 60 B/周期',False,depth=31)
        for i in range(10):D.line(2190,1147+i*2,2808,1147+i*2,'hair')
        # L2 is a separate read pool, not an inline cache on all DDR traffic.
        D.slab(2363,1252,457,79,'只读 L2 · FIFO · Q3',False,depth=24)
        D.text(2590,1368,'1 MiB · 250 B/周期',25,'math','middle')
        D.path('M2375,1201H2810','dashed')
        D.arrow('M2385,1169C2338,1204 2337,1241 2363,1277','dashed')
        D.text(2090,1253,'未命中读 DDR',23)
        D.text(2090,1289,'完成后尝试填充',23)
        D.fibre(2822,1292,2879,677,2956,1223,2967,850,7)
        D.text(2916,1071,'命',22,'muted halo','middle');D.text(2916,1103,'中',22,'muted halo','middle');D.text(2916,1135,'读',22,'muted halo','middle')
        D.text(2500,1404,'COPY_IN 发射时查询；命中不刷新 FIFO',21,'muted','middle')
        D.text(2500,1438,'Step1 核内顺序 → Step2 驻留 / Spill',25,'','middle')
        D.text(2500,1476,'→ Step3 Pipe 排布 → 全局离散事件模拟',25,'','middle')
        # The candidate enters the whole fixed executor, not only its last step.
        D.arrow('M2118,1455C2070,1455 2064,608 2104,562','fine')
        D.arrow('M2866,1492C2960,1540 2960,1657 2828,1732')
        # Differences between question semantics, kept at point of use.
        D.text(2092,1533,'Q1 子图级 Task；跨子图经 DDR，同核亦如此',22,'muted')
        D.text(2092,1567,'同核前序完成 +100；跨核前驱完成 +1000（周期）',21,'muted')
        D.text(2092,1601,'Q2/3 核心级 Task；跨核 COPY_OUT 完成 +500（周期）',21,'muted')

def control_and_outputs():
    with D.group('accept-feedback','04 完整评价、严格接受、状态刷新与预算控制',layer=True):
        D.line(90,1625,2920,1625,'fine')
        # Main lower spine travels right to left: score -> accept -> feedback.
        D.text(2900,1687,'总体任务执行时间（Makespan）',30,'bold','end')
        D.text(2526,1750,'C_q(y) = max_j f_j',43,'math','middle')
        D.text(2900,1803,'周期持平，再比较额外 COPY 字节 D_q(y)',25,'math','end')
        D.fibre(2180,1748,1889,1748,2119,1748,1950,1748,5)
        D.text(1505,1687,'04  可行且字典序严格改善？',31,'bold','middle')
        D.path('M1127,1745L1163,1708H1842L1880,1745L1842,1787H1163Z','paper')
        D.text(1505,1760,'y ∈ ℱ_q  且  (C_q(y), D_q(y)) <_{lex} (C_q(x), D_q(x))',28,'math','middle')
        D.text(2045,1710,'实际评价',24,'muted','middle')
        D.fibre(1122,1748,883,1748,1040,1748,982,1748,7)
        D.text(1000,1708,'是',27,'bold','middle')
        D.text(105,1687,'同步更新共同状态',31,'bold')
        D.text(105,1753,'x ← y',48,'math')
        D.text(341,1749,'方案 + 完整执行记录',29)
        D.text(105,1810,'刷新依赖父状态的局部流；保留全局构造进度',25)
        D.fibre(116,1734,208,1526,20,1696,32,1526,7)
        D.arrow('M1511,1789V1854','dashed')
        D.text(1550,1835,'否：保留 x',25,'muted')
        D.arrow('M793,1790C844,1869 1300,1880 1400,1880','fine')
        D.text(1046,1831,'接受 / 未接受后均检查',23,'muted','middle')
        D.path('M1400,1880L1510,1845L1620,1880L1510,1915Z','paper')
        D.text(1510,1889,'停止？',26,'bold','middle')
        D.path('M1400,1880C1352,1930 1013,2000 1013,1790V495Q1013,392 1060,392','',fill='none',stroke='white',stroke_width=9)
        D.arrow('M1400,1880C1352,1930 1013,2000 1013,1790V495Q1013,392 1060,392','dashed')
        D.text(1285,1970,'否：下一轮',24,'muted','middle')
    with D.group('outputs','05 停止与输出；第三问同方案配对不参与接受',layer=True):
        D.text(94,1926,'05  停止与保存',30,'bold')
        D.text(94,1973,'时间 / 次数预算 · 质量界 · 来源耗尽 · 经验停滞',24)
        D.text(94,2016,'只保存截止前已验证、已可用的最好方案',24,'muted')
        D.arrow('M1620,1880H1780','fine')
        D.text(1690,1851,'是',25,'bold','middle')
        D.text(1806,1918,'方案 x + 实际指标 + 时间—质量记录',28,'bold')
        D.text(1806,1968,'Q3：固定同一个 (𝒫, a, π)，再执行无 L2 对照',26)
        D.text(1806,2014,'R^{L2} = C₂(x₃) / C₃(x₃)；配对不参与搜索接受',27,'math')
    with D.group('legend','线型、对象与示意说明',layer=True):
        D.line(90,2055,2920,2055,'fine')
        D.tensor(110,2090,'',.47);D.text(140,2093,'张量',21)
        D.ellipse(260,2086,23,13,'paper');D.text(294,2093,'算子',21)
        D.rect(412,2074,44,22,'boundary',rx=8);D.text(470,2093,'子图边界',21)
        D.rect(637,2074,31,22,'black');D.text(684,2093,'操作对象',21)
        D.arrow('M850,2087H903','dashed');D.text(917,2093,'反馈 / 条件路径',21)
        D.text(2913,2093,'机制案例为示意，非实测计划；执行时间线不按比例。',21,'muted','end')

def render(out: Path):
    global D
    D=Drawing();definitions()
    with D.group('page','版面与标题',layer=True):
        D.rect(0,0,W,H,'',fill='white',stroke='none')
        D.line(87,61,2917,61,'route')
        D.text(90,145,'计算图调度的联合优化',59,'serif bold')
        D.text(92,199,'联合决策—统一执行—多邻域迭代改进',31)
        D.text(2915,125,'G  →  (𝒫, a, π)  →  ℰ_q  →  (C_q, D_q)',37,'math','end')
        D.text(2915,181,'方法总览 / 黑白线刻',25,'muted','end')
        D.line(90,228,2916,228,'fine')
    input_plate();neighborhoods();execution_plate();control_and_outputs()
    D.add('</svg>')
    out.mkdir(parents=True,exist_ok=True)
    p=out/'workflow.svg';p.write_text('\n'.join(D.parts)+'\n',encoding='utf-8')
    print(p)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=Path(__file__).resolve().parents[1]/'assets')
    render(parser.parse_args().out)
