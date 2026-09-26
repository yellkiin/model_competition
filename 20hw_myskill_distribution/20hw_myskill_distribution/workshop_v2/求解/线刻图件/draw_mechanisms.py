"""Editable engraved mechanism diagrams aligned to manuscript definitions.

Only draws schematics. It does not run, replace or modify any scheduling method.
"""
from io import BytesIO
from pathlib import Path
import math,re,subprocess,shutil
import xml.etree.ElementTree as ET
from matplotlib import mathtext, rc_context
from style import WORK,HERE,INK,S,M,F,GRAY,P,THEME,wash

NS='http://www.w3.org/2000/svg';XLINK='http://www.w3.org/1999/xlink'
ET.register_namespace('',NS);ET.register_namespace('xlink',XLINK)
def tag(s):return '{'+NS+'}'+s

class Drawing:
    def __init__(self,name,height):
        self.name=name;self.width=1200;self.height=height;self.counter=0
        self.root=ET.Element(tag('svg'),{'viewBox':f'0 0 1200 {height}','width':'162mm','height':f'{162*height/1200:.4f}mm'})
        self.defs=ET.SubElement(self.root,tag('defs'))
        css=ET.SubElement(self.defs,tag('style'));css.text=f'''text {{font-family:'Times New Roman','SimSun','Noto Serif CJK SC',serif;fill:{INK};}} .label {{font-size:23px;}} path,line,polyline,rect,ellipse {{stroke-linecap:round;stroke-linejoin:round;}}'''
        for role,c in [('ink',INK),('s',S),('m',M),('f',F)]:
            marker=ET.SubElement(self.defs,tag('marker'),{'id':f'arrow-{role}','viewBox':'0 0 10 10','refX':'9','refY':'5','markerWidth':'10','markerHeight':'10','orient':'auto','markerUnits':'userSpaceOnUse'})
            ET.SubElement(marker,tag('path'),{'d':'M1,1 L9,5 L1,9 L3.5,5 Z','fill':c,'stroke':'none'})
            pat=ET.SubElement(self.defs,tag('pattern'),{'id':f'hatch-{role}','patternUnits':'userSpaceOnUse','width':'9','height':'9'})
            ET.SubElement(pat,tag('path'),{'d':'M-1,9 L9,-1 M8,10 L10,8','fill':'none','stroke':c,'stroke-width':'.7','opacity':'.55'})
        ET.SubElement(self.root,tag('rect'),{'x':'0','y':'0','width':'1200','height':str(height),'fill':'white','stroke':'none'})
        self.group=self.root

    def elem(self,name,**a):
        a={k.replace('_','-'):str(v) for k,v in a.items() if v is not None}
        return ET.SubElement(self.group,tag(name),a)
    def text(self,x,y,t,size=23,color=INK,anchor='middle',bold=False):
        self.counter+=1
        e=self.elem('text',x=x,y=y,font_size=size,fill=color,text_anchor=anchor,id=f'{self.name}-label-{self.counter}')
        # Inline style wins over shared text fill.
        e.set('style',f'fill:{color}'+(';font-weight:600' if bold else ''));e.text=t
        return e
    def lines(self,x,y,ls,size=22,dy=32,color=GRAY,anchor='middle'):
        for i,s in enumerate(ls):self.text(x,y+dy*i,s,size,color,anchor)
    def rule(self,x1,y1,x2,y2,c=INK,width=1,dash=None):
        return self.elem('line',x1=x1,y1=y1,x2=x2,y2=y2,stroke=c,stroke_width=width,stroke_dasharray=dash)
    def link(self,points,role='ink',dash=None,width=1.8,arrow=True):
        c={'ink':INK,'s':S,'m':M,'f':F}[role]
        d='M'+' L'.join(f'{x},{y}' for x,y in points)
        return self.elem('path',d=d,fill='none',stroke=c,stroke_width=width,stroke_dasharray=dash,marker_end=f'url(#arrow-{role})' if arrow else None)
    def frame(self,x,y,w,h,c=INK,dash=None,fill='white',rx=0):
        return self.elem('rect',x=x,y=y,width=w,height=h,fill=fill,stroke=c,stroke_width=1.4,stroke_dasharray=dash,rx=rx)
    def box(self,x,y,w,h,label,role='ink',size=23,light=True):
        c={'ink':INK,'s':S,'m':M,'f':F}[role]
        self.frame(x,y,w,h,c=c,fill=wash(c,.055) if light else 'white',rx=3)
        self.text(x+w/2,y+h/2+size*.33,label,size,c)
    def cube(self,x,y,w,h,label='',role='ink',size=24):
        c={'ink':INK,'s':S,'m':M,'f':F}[role];d=11
        for points in [f'{x},{y} {x+d},{y-d} {x+w+d},{y-d} {x+w},{y}',f'{x+w},{y} {x+w+d},{y-d} {x+w+d},{y+h-d} {x+w},{y+h}']:
            self.elem('polygon',points=points,fill='white',stroke=c,stroke_width=1.1)
            self.elem('polygon',points=points,fill=f'url(#hatch-{role})',stroke='none')
        self.frame(x,y,w,h,c=c,fill=wash(c,.06))
        if label:self.text(x+w/2,y+h/2+size*.33,label,size,c)
    def op(self,x,y,label,role='ink',rx=27,ry=20):
        c={'ink':INK,'s':S,'m':M,'f':F}[role]
        self.elem('ellipse',cx=x,cy=y,rx=rx,ry=ry,fill='white',stroke=c,stroke_width=1.5)
        self.elem('ellipse',cx=x,cy=y,rx=rx-4,ry=ry-4,fill='none',stroke=c,stroke_width=.5)
        self.text(x,y+7,label,22,c)
    def math(self,x,y,tex,width=None):
        buf=BytesIO()
        with rc_context({'svg.fonttype':'path'}):
            mathtext.math_to_image('$'+tex+'$',buf,format='svg',dpi=72,color=INK)
        elem=ET.fromstring(buf.getvalue());vb=[float(a) for a in elem.get('viewBox').split()]
        sc=2.4 if width is None else min(2.4,width/vb[2])
        self.counter+=1;prefix=f'm{self.counter}-';idmap={e.get('id'):prefix+e.get('id') for e in elem.iter() if e.get('id')}
        for e in elem.iter():
            if e.get('id'):e.set('id',idmap[e.get('id')])
            for k,v in list(e.attrib.items()):
                if v.startswith('#') and v[1:] in idmap:e.set(k,'#'+idmap[v[1:]])
                for old,new in idmap.items():v=v.replace('url(#'+old+')','url(#'+new+')')
                if 'url(' in v:e.set(k,v)
        g=ET.SubElement(self.root,tag('g'),{'transform':f'translate({x-vb[2]*sc/2:.3f},{y}) scale({sc})','data-tex':tex})
        for e in list(elem):
            if e.tag not in [tag('metadata')]:g.append(e)
    def stage(self,x,n,title,color):
        self.text(x,40,f'{n:02}',22,color,anchor='start');self.text(x+44,40,title,26,INK,anchor='start')
        self.rule(x,57,x+350,57,color,1.25)
    def save(self,q):
        out=WORK/'求解'/('问题'+['','一','二','三'][q])/'图片';out.mkdir(parents=True,exist_ok=True)
        p=out/(self.name+'.svg');ET.ElementTree(self.root).write(p,encoding='utf-8',xml_declaration=True)
        exe=shutil.which('inkscape')
        if not exe:raise RuntimeError('Editable SVG ready; install Inkscape to export PDF/PNG.')
        for ext,opt in [('pdf',[]),('png',['--export-width=2400'])]:
            subprocess.run([exe,str(p),'--export-background=white','--export-background-opacity=1',f'--export-filename={out/(self.name+"."+ext)}',*opt],check=True,capture_output=True)
        print(self.name)

def q1_overview():
    d=Drawing('q1_overview',430)
    for x,n,t,c in [(30,1,'构造完整初值',S),(425,2,'互补邻域改进',M),(820,3,'执行与接受',F)]:d.stage(x,n,t,c)
    # One branch graph; dashed envelopes are actual partition examples.
    for pts in [[(102,190),(188,128)],[(102,190),(188,246)],[(242,128),(318,190)],[(242,246),(318,190)]]:d.link(pts,width=1.2)
    for x,y,s in [(74,190,'a'),(215,128,'b'),(215,246,'c'),(345,190,'d')]:d.op(x,y,s)
    d.frame(162,91,108,83,c=S,dash='6 5',fill='none',rx=20);d.frame(162,209,108,83,c=S,dash='6 5',fill='none',rx=20)
    d.lines(205,343,['拓扑前缀细化','流水线负载与边界字节'],size=22)
    # A large migration, not a distorted curl. Stable core rails and aligned ports.
    d.text(439,138,'k₁',23,anchor='start');d.text(439,264,'k₂',23,anchor='start')
    d.rule(482,153,770,153,GRAY,1.2);d.rule(482,279,770,279,GRAY,1.2)
    d.cube(490,94,74,47,'A','s');d.frame(610,94,74,47,c=M,dash='5 5');d.text(647,126,'B',24,M)
    d.cube(610,220,74,47,'B','m');d.cube(706,220,60,47,'C','ink')
    d.link([(647,154),(647,202)],'m');d.text(710,185,'迁移',21,M)
    d.lines(610,343,['迁移／交换／拆分','边界释放与驻留重组'],size=22)
    # Compact pipe projection ending at the same measured horizon.
    d.frame(885,92,250,203,c=GRAY)
    for i,(lab,a,b) in enumerate([('M',0,125),('V',50,125),('IN',0,65),('OUT',135,188)]):
        y=117+i*43;d.text(875,y+9,lab,19,GRAY,anchor='end');d.rule(900,y+14,1118,y+14,P['faint'],.65)
        d.frame(910+a,y-6,b-a,18,c=INK,fill=wash(INK,.08));d.elem('rect',x=910+a,y=y-6,width=b-a,height=18,fill='url(#hatch-ink)',stroke='none')
    d.lines(996,343,['完成周期优先','同周期再比较额外搬运'],size=22)
    # Common decision variables and two restrained inter-panel links.
    d.link([(377,190),(414,190)],'ink');d.link([(773,190),(811,190)],'ink')
    d.math(600,390,r'x=(\mathcal{P},a,\boldsymbol{\pi})',width=240)
    d.save(1)

def q1_task():
    d=Drawing('q1_task',390)
    d.text(65,43,'同核相邻子图分别形成任务',26,anchor='start')
    d.frame(65,84,345,124,c=S,dash='6 4',fill='none',rx=8);d.frame(784,84,345,124,c=S,dash='6 4',fill='none',rx=8)
    d.text(93,111,'Task i',22,S,anchor='start');d.text(812,111,'Task j',22,S,anchor='start')
    d.cube(122,142,100,42,'生产者','ink',22);d.cube(853,142,140,42,'消费者','ink',22)
    d.link([(410,124),(774,124)],'s');d.text(596,102,'本核任务交接：+100 周期',22,S)
    d.link([(222,162),(303,162)],'m');d.cube(311,150,23,25,'','m')
    d.cube(378,261,435,47,'DDR 共享读写带宽','m',24)
    d.link([(323,189),(323,284),(367,284)],'m');d.text(214,240,'COPY_OUT',22,M)
    d.link([(825,284),(1018,284),(1018,163),(1006,163)],'m');d.text(990,240,'COPY_IN',22,M)
    d.text(70,350,'跨核前驱任务的交接等待为 1000 周期；数据到达与任务顺序共同决定启动。',22,GRAY,anchor='start')
    d.save(1)

def q2_task():
    d=Drawing('q2_task',470)
    for x,w,lab,c in [(50,515,'核心 k₁：一个 Task',S),(675,475,'核心 k₂：一个 Task',S)]:
        d.frame(x,68,w,223,c=c,dash='6 4',fill='none',rx=8);d.text(x+w/2,42,lab,26)
    d.cube(89,127,109,55,'子图 A','ink',22);d.cube(380,127,120,55,'子图 B','ink',22)
    d.cube(836,127,126,55,'子图 C','ink',22)
    d.cube(272,143,26,28,'','m');d.link([(211,155),(259,155)],'m');d.link([(309,155),(369,155)],'m')
    d.text(285,115,'本核张量',21,M)
    d.box(110,229,138,43,'L1','m');d.box(344,229,138,43,'UB','m')
    d.box(716,229,138,43,'L1','m');d.box(942,229,138,43,'UB','m')
    d.link([(285,185),(285,335),(467,335)],'m');d.text(345,313,'COPY_OUT',21,M)
    d.cube(478,317,270,49,'DDR','m',25)
    d.link([(760,342),(1103,342),(1103,155),(975,155)],'m');d.text(1005,320,'COPY_IN',21,M)
    d.text(907,381,'输出完成后 +500 周期释放读入',22,GRAY)
    d.text(307,415,'同核可延续驻留；容量不足时换出、再取回。',22,GRAY)
    d.text(875,430,'输入就绪、Pipe 与缓冲容量仍须同时满足。',21,GRAY)
    d.save(2)

def q2_overview():
    d=Drawing('q2_overview',465)
    for x,n,t,c in [(30,1,'识别交接与活跃集',M),(425,2,'重组完整子图',S),(820,3,'权衡并完整评价',F)]:d.stage(x,n,t,c)
    d.cube(77,118,92,48,'生产','ink',22);d.cube(258,118,92,48,'消费','ink',22)
    d.cube(204,194,25,28,'','m');d.link([(128,180),(128,208),(194,208)],'m');d.link([(240,208),(305,208),(305,180)],'m')
    d.frame(55,94,139,165,c=GRAY,dash='5 5',fill='none',rx=5);d.frame(250,94,118,165,c=GRAY,dash='5 5',fill='none',rx=5)
    d.text(125,285,'核心 k₁',22);d.text(309,285,'核心 k₂',22)
    d.lines(207,353,['关联张量与生产—消费子图','识别跨核流量和驻留区间'],22)
    # Capacity-limited batches drawn as two distinct, orderly waves.
    for row,y in enumerate([123,220]):
        d.frame(446,y-20,315,68,c=S,dash='5 4',fill='none',rx=7)
        for j in range(3):d.cube(465+j*95,y,65,31,chr(65+row*3+j),'s',20)
    d.text(604,94,'分量分批／归属保持重排',21,GRAY)
    d.link([(608,178),(608,195)],'s')
    d.lines(607,353,['控制同时展开的工作集','保留合法依赖与核内次序'],22)
    # Two causal influences converge on actual execution, not a proxy optimum.
    d.box(844,100,137,58,'搬运','m');d.box(1009,100,137,58,'并行','s')
    d.link([(912,159),(912,203),(993,203)],'m',arrow=False);d.link([(1078,159),(1078,203),(993,203)],'s',arrow=False)
    d.link([(993,203),(993,235)],'ink');d.box(878,245,235,58,'完整事件执行','ink')
    d.lines(993,353,['比较总体周期与额外 COPY','更新当前最好可行方案'],22)
    d.link([(377,210),(414,210)]);d.link([(773,210),(811,210)])
    d.math(600,418,r'\min^{\mathrm{lex}}\,(C_2(x),D_2(x))',width=270)
    d.save(2)

def q3_overview():
    d=Drawing('q3_overview',610)
    for x,n,t,c in [(30,1,'多尺度划分与归核',S),(425,2,'归属保持拆分重排',M),(820,3,'FIFO 访问窗口调整',F)]:d.stage(x,n,t,c)
    # Layered graph: edges only descend through depth bands.
    for y in [112,188,264]:
        d.frame(74,y-27,279,52,c=S,dash='5 4',fill='none',rx=4)
    for col,x in enumerate([126,293]):
        for y in [112,188,264]:d.op(x,y,str(1+col+(y-112)//76*2),rx=23,ry=17)
    for x in [126,293]:
        for y in [112,188]:d.link([(x,y+21),(x,y+50)],'s',width=1.3)
    d.lines(210,325,['层带分量按负载与通信归核','同时比较不同划分尺度'],21)
    d.frame(452,87,176,79,c=M,dash='6 4',fill='none',rx=6)
    d.cube(465,106,60,34,'A₁','m',21);d.cube(548,106,60,34,'A₂','m',21)
    d.cube(665,106,65,34,'B','ink',21)
    d.link([(601,170),(601,202)],'m')
    d.cube(471,228,65,34,'A₂','m',21);d.cube(567,228,65,34,'B','ink',21);d.cube(665,228,65,34,'A₁','m',21)
    d.rule(459,281,754,281,GRAY,1.1)
    d.lines(600,325,['算子归核不变，改变分组与顺序','就绪单元按复用与新读入量排序'],21)
    d.frame(870,152,183,60,c=F,fill=wash(F,.13));d.elem('rect',x=870,y=152,width=183,height=60,fill='url(#hatch-f)',stroke='none')
    d.text(961,189,'有效驻留窗口',21,F)
    d.rule(842,235,1158,235,GRAY,1.1)
    for x,s in [(870,'fₜ'),(963,"s′ₜ"),(1053,'eₜ'),(1133,'sₜ')]:
        d.rule(x,226,x,245,GRAY,.9);d.text(x,275,s,23,F if x==963 else INK)
    d.link([(1133,219),(1133,118),(963,118),(963,141)],'f')
    d.lines(993,325,['只移动已有子图的位置','用新执行重算命中、填充与淘汰'],21)
    # Straight, separate downward trunks meet a shared screening strip.
    for x in [210,600,993]:d.rule(x,373,x,390,INK,1.4)
    d.rule(210,390,993,390,INK,1.4)
    d.link([(210,390),(210,405)])
    d.box(79,414,257,54,'覆盖与无环检查','ink',23)
    d.box(469,414,260,54,'完整执行评价','ink',23)
    d.box(862,414,266,54,'按周期与搬运接受','ink',23)
    d.link([(348,441),(455,441)]);d.link([(741,441),(848,441)])
    d.link([(996,470),(996,513),(213,513)],'ink')
    d.text(214,543,'固定同一个完整方案 x',23,INK,anchor='start')
    d.math(773,541,r'R^{\mathrm{L2}}=C_2(x)/C_3(x)',width=340)
    d.text(608,588,'候选重选与缓存开关配对分别表达，不以第二问的独立最优方案替代。',21,GRAY)
    d.save(3)

def q3_fifo():
    d=Drawing('q3_fifo',490)
    d.box(40,128,176,62,'COPY_IN','ink',25)
    d.link([(228,159),(271,159)])
    d.box(284,128,172,62,'按张量查询','ink',23)
    d.link([(456,147),(507,147),(507,73),(572,73)],'f')
    d.link([(456,172),(507,172),(507,241),(572,241)],'m')
    d.text(513,45,'命中',22,F);d.text(513,280,'未命中',22,M)
    d.cube(584,46,253,65,'独立 L2 读带宽池','f',23)
    d.cube(584,213,253,65,'DDR 共享读写池','m',23)
    d.text(710,149,'命中不刷新 FIFO 次序',22,F)
    d.link([(850,77),(902,77),(902,159),(956,159)],'f')
    d.link([(850,246),(902,246),(902,159)],'m',arrow=False)
    d.box(968,128,185,62,'读完成','ink',24)
    d.link([(1061,203),(1061,333),(969,333),(969,376)],'f')
    d.text(953,319,'每次完成均尝试填充',23,F)
    # FIFO queue, oldest at left, newest at right.
    d.text(611,369,'队首',21,GRAY);d.text(1017,369,'队尾',21,GRAY)
    for i,lab in enumerate(['旧','⋯','新']):d.cube(594+151*i,392,122,46,lab,'f',23)
    d.lines(65,350,['已驻留：保持队列位置','未驻留：足量时插入队尾','容量不足：从队首依次淘汰','张量超出总容量：不缓存'],size=22,dy=33,color=GRAY,anchor='start')
    d.link([(583,415),(519,415)],'f');d.text(538,456,'淘汰',21,F)
    d.save(3)

if __name__=='__main__':
    for fun in [q1_overview,q1_task,q2_overview,q2_task,q3_overview,q3_fifo]:fun()
