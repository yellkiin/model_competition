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
        if not exe:
            node=shutil.which('node')
            if not node:raise RuntimeError('Set PATH to an installed Node.js or Inkscape runtime.')
            subprocess.run([node,str(HERE/'render_svg.mjs'),str(p)],check=True)
            print(self.name)
            return
        for ext,opt in [('pdf',[]),('png',['--export-width=2400'])]:
            subprocess.run([exe,str(p),'--export-background=white','--export-background-opacity=1',f'--export-filename={out/(self.name+"."+ext)}',*opt],check=True,capture_output=True)
        print(self.name)


def miniature_change(d,x,y,kind):
    # Same double outlines, cuboids and thin rails as the PR71 master drawing.
    d.text(x,y,kind,23,S,anchor='start')
    if kind=='a  基础构造':
        for xx,yy,t in [(x+25,y+61,'o₁'),(x+125,y+35,'o₂'),(x+125,y+92,'o₃')]:d.op(xx,yy,t,rx=22,ry=17)
        d.link([(x+50,y+55),(x+99,y+39)],'s',width=1.2);d.link([(x+50,y+70),(x+99,y+88)],'s',width=1.2)
        d.frame(x+91,y+8,69,108,c=S,dash='5 4',fill='none',rx=9)
        d.text(x+85,y+145,'拓扑序与划分粒度',19,GRAY)
    elif kind=='b  迁移':
        d.rule(x+9,y+54,x+170,y+54,GRAY);d.rule(x+9,y+118,x+170,y+118,GRAY)
        d.cube(x+15,y+21,49,27,'A','s',18);d.frame(x+103,y+21,49,27,c=M,dash='4 3');d.text(x+127,y+41,'B',18,M)
        d.cube(x+103,y+85,49,27,'B','m',18);d.link([(x+127,y+78),(x+127,y+56)],'m')
        d.text(x+85,y+145,'改变所属核心',19,GRAY)
    elif kind=='c  交换':
        d.cube(x+9,y+22,49,29,'B','s',18);d.cube(x+115,y+22,49,29,'C','m',18)
        d.link([(x+34,y+67),(x+34,y+89),(x+126,y+89)],'s');d.link([(x+140,y+59),(x+140,y+73),(x+50,y+73)],'m')
        d.text(x+85,y+132,'对调两核子图',19,GRAY)
    elif kind=='d  切分':
        d.cube(x+56,y+18,75,31,'B','s',20)
        d.link([(x+94,y+62),(x+94,y+81)],'s')
        d.cube(x+10,y+97,61,30,'B₁','s',20);d.cube(x+119,y+97,61,30,'B₂','s',20)
        d.link([(x+83,y+111),(x+108,y+111)],'s',width=1.2)
        d.text(x+94,y+158,'保留原算子与依赖',19,GRAY)

def q1_overview():
    d=Drawing('q1_overview',650)
    for x,n,t,c in [(25,1,'联合决策与初值',S),(409,2,'互补候选操作',M),(836,3,'统一执行评价',F)]:d.stage(x,n,t,c)
    d.cube(74,129,241,53,'原始计算图','ink',25)
    d.link([(195,196),(195,228)],'s')
    d.lines(195,261,['子图划分','核心映射','核内顺序'],size=25,dy=43,color=INK)
    d.link([(195,365),(195,399)],'s')
    d.cube(68,418,250,58,'当前完整方案','s',25)
    d.math(195,500,r'x=(\mathcal{P},a,\boldsymbol{\pi})',width=255)
    miniature_change(d,410,105,'a  基础构造');miniature_change(d,627,105,'b  迁移')
    miniature_change(d,410,320,'c  交换');miniature_change(d,627,320,'d  切分')
    d.rule(401,278,809,278,P['faint'],.7)
    d.cube(879,114,245,58,'子图级任务','ink',25)
    for i,(label,start,width) in enumerate([('M',0,92),('V',33,127),('读入',0,53),('写出',122,50)]):
        y=220+i*48;d.text(896,y+14,label,20,GRAY,anchor='end');d.rule(917,y+18,1145,y+18,P['faint'],.6)
        d.frame(925+start,y,width,19,fill=wash(INK,.08));d.elem('rect',x=925+start,y=y,width=width,height=19,fill='url(#hatch-ink)',stroke='none')
    d.lines(1010,441,['任务交接 · 片上容量','流水线 · DDR共享带宽'],size=22,dy=36)
    # A single feedback loop, with labels above and routes below the nodes.
    d.box(79,565,236,51,'当前方案','s',23)
    d.box(477,565,236,51,'构造完整候选','m',23)
    d.box(875,565,275,51,'评价并保留改善','f',23)
    d.link([(327,591),(463,591)]);d.link([(725,591),(860,591)])
    d.link([(1011,620),(1011,637),(197,637),(197,620)],'s',width=1.5)
    d.save(1)

def q1_task():
    d=Drawing('q1_task',430)
    d.text(45,39,'同核相邻子图分别形成任务',27,anchor='start')
    d.frame(46,100,405,139,c=S,dash='6 4',fill='none',rx=7);d.frame(755,100,405,139,c=S,dash='6 4',fill='none',rx=7)
    d.text(70,130,'Task i',23,S,anchor='start');d.text(779,130,'Task j',23,S,anchor='start')
    d.cube(92,164,148,46,'生成算子','ink',23);d.cube(881,164,148,46,'使用算子','ink',23)
    d.cube(324,174,28,31,'','m');d.text(382,202,'t',20,M)
    d.link([(253,187),(309,187)],'m')
    d.link([(467,130),(738,130)],'s');d.text(603,101,'同核交接 +100 周期',23,S)
    d.cube(429,306,318,55,'DDR 共享读写带宽','m',24)
    d.link([(338,220),(338,333),(417,333)],'m');d.text(315,285,'COPY_OUT',22,M,anchor='end')
    d.link([(760,333),(1073,333),(1073,187),(1045,187)],'m');d.text(1044,285,'COPY_IN',22,M,anchor='end')
    d.text(44,407,'跨核前驱任务完成后等待1000周期；任务顺序与输入数据就绪共同决定启动。',22,GRAY,anchor='start')
    d.save(1)

def q2_task():
    d=Drawing('q2_task',610)
    for x,w,lab in [(37,686,'核心 k₁：一个 Task'),(809,355,'核心 k₂：一个 Task')]:
        d.text(x+w/2,42,lab,27);d.frame(x,76,w,290,c=S,dash='6 4',fill='none',rx=7)
    d.cube(83,135,150,52,'子图 A','ink',24);d.cube(501,135,150,52,'子图 B','ink',24)
    d.text(158,218,'生成张量 t',22,M);d.text(576,218,'再次读取 t',22,M)
    d.cube(290,276,165,51,'L1 / UB','m',25)
    d.link([(158,229),(158,301),(276,301)],'m');d.link([(470,301),(576,301),(576,231)],'m')
    d.text(374,257,'本核驻留',23,M)
    d.cube(899,135,164,52,'子图 C','ink',24);d.text(981,220,'跨核读取 t',22,M)
    d.cube(912,276,140,51,'L1 / UB','m',24);d.link([(982,259),(982,234)],'m')
    d.cube(460,445,290,54,'DDR','m',26)
    d.link([(374,341),(374,472),(447,472)],'m');d.text(350,415,'COPY_OUT',22,M,anchor='end')
    d.link([(764,472),(1093,472),(1093,302),(1067,302)],'m');d.text(1064,415,'COPY_IN',22,M,anchor='end')
    d.text(608,534,'跨核读入：对应写出完成后等待500周期',23,GRAY)
    d.text(37,580,'同核复用：后续子图读取仍驻留的数据。',22,GRAY,anchor='start')
    d.text(1164,580,'容量不足：换出到DDR，后续再取回。',22,GRAY,anchor='end')
    d.save(2)

def q2_overview():
    d=Drawing('q2_overview',525)
    for x,n,t,c in [(25,1,'核心级任务与复用',M),(421,2,'驻留候选改进',S),(824,3,'按执行结果选优',F)]:d.stage(x,n,t,c)
    d.frame(43,100,331,239,c=S,dash='6 4',fill='none',rx=6)
    d.cube(74,132,117,48,'生成算子','ink',21);d.cube(235,132,117,48,'使用算子','ink',21)
    d.cube(131,257,154,47,'L1 / UB','m',23)
    d.link([(133,192),(133,218),(180,218),(180,243)],'m');d.link([(297,245),(321,245),(321,197)],'m')
    d.text(211,375,'同核数据延续驻留',23,M)
    d.box(444,107,321,58,'关联子图迁移','s',24)
    d.box(444,208,321,58,'保持核心映射的重组','s',24)
    d.box(444,309,321,58,'分量分批与阶段划分','s',24)
    d.lines(1000,127,['跨核交接 +500 周期','L1 / UB 容量限制','流水线与共享带宽'],23,43,GRAY)
    d.cube(863,282,275,61,'完整执行评价','ink',25)
    d.lines(1000,385,['优先缩短总体周期','同周期减少额外搬运'],22,33,INK)
    d.link([(384,230),(424,230)]);d.link([(779,230),(817,230)])
    d.box(54,461,314,44,'当前完整方案','s',22);d.box(447,461,314,44,'联合生成候选','m',22);d.box(842,461,314,44,'保留更优方案','f',22)
    d.link([(380,483),(433,483)]);d.link([(773,483),(829,483)])
    d.save(2)

def q3_overview():
    d=Drawing('q3_overview',600)
    for x,n,t,c in [(25,1,'继承共同候选',S),(421,2,'增加FIFO时序调整',F),(824,3,'统一执行与反馈',M)]:d.stage(x,n,t,c)
    d.box(48,109,318,60,'基础构造与结构变换','s',23)
    d.box(48,212,318,60,'驻留重组与通信映射','m',23)
    d.lines(207,318,['对应总图操作 a—e','共享当前完整方案'],22,34)
    d.frame(462,147,200,65,c=F,fill=wash(F,.1));d.elem('rect',x=462,y=147,width=200,height=65,fill='url(#hatch-f)',stroke='none')
    d.text(562,187,'有效驻留窗口',23,F)
    d.rule(437,243,780,243,GRAY,1)
    for x,label in [(462,'填充'),(562,'调整后'),(662,'淘汰'),(750,'原读入')]:
        d.rule(x,231,x,252,GRAY);d.text(x,279,label,20,F if x==562 else GRAY)
    d.link([(750,222),(750,118),(562,118),(562,136)],'f')
    d.lines(604,323,['对应总图操作 f','保持划分与映射，调整核内顺序'],20,34)
    d.cube(862,113,273,61,'任务与缓存事件','ink',24)
    d.lines(998,230,['读请求发射时查询','读完成后尝试填充','FIFO队首依次淘汰'],22,37)
    d.text(998,356,'先比较周期，再比较搬运',21,GRAY)
    d.link([(207,373),(207,430)],'s')
    d.link([(604,376),(604,404),(207,404)],'f',arrow=False)
    d.box(80,445,260,50,'构造完整候选','s',23)
    d.box(460,445,270,50,'完整执行评价','m',23)
    d.box(860,445,270,50,'保留更优方案','f',23)
    d.link([(353,470),(445,470)]);d.link([(744,470),(845,470)])
    d.link([(995,508),(995,535),(20,535),(20,237),(35,237)],'s',width=1.5)
    d.text(38,583,'搜索结束：固定同一方案，比较无L2与有L2的执行时间',22,GRAY,anchor='start')
    d.save(3)


def q3_fifo():
    d=Drawing('q3_fifo',540)
    d.box(34,129,181,62,'读请求发射','ink',24);d.box(294,129,174,62,'按张量查询','ink',23);d.link([(228,160),(280,160)])
    d.link([(481,146),(520,146),(520,73),(574,73)],'f');d.link([(481,176),(520,176),(520,239),(574,239)],'m')
    d.text(509,42,'命中',22,F);d.text(510,288,'未命中',22,M)
    d.cube(587,45,242,63,'L2独立读带宽池','f',23);d.cube(587,212,242,63,'DDR共享读写池','m',23)
    d.text(708,150,'命中保持队列位置',21,F)
    d.link([(844,77),(902,77),(902,159),(955,159)],'f');d.link([(844,243),(902,243),(902,159)],'m',arrow=False)
    d.box(970,129,187,62,'读完成','ink',24)
    d.link([(1063,205),(1063,335),(1046,335),(1046,398)],'f');d.text(1010,315,'尝试填充',23,F)
    d.lines(34,345,['已驻留：保持原队列位置','超过总容量：跳过填充','可容纳且未驻留：插入队尾'],22,38,GRAY,anchor='start')
    d.text(678,383,'队首',22,GRAY);d.text(1139,383,'队尾',22,GRAY)
    for x,t in [(621,'旧'),(804,'⋯'),(987,'新')]:d.cube(x,413,121,47,t,'f',23)
    d.cube(444,413,118,47,'淘汰','f',23);d.link([(607,437),(579,437)],'f')
    d.text(846,509,'空间不足时，从队首依次淘汰至可容纳',22,GRAY)
    d.save(3)

if __name__=='__main__':
    for fun in [q1_overview,q1_task,q2_overview,q2_task,q3_overview,q3_fifo]:fun()
