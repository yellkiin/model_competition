"""Compact editable reconstructions for the remaining retained references."""
from authoring_support import Author
import sys
import os

PALE=['#d9e2f3','#e2f0d9','#fce4d6','#e4dfec','#fff2cc','#dDEBF7']
def make(a, ident, ref, name, kind):
    def box(k,bb,t,fill='#ffffff',fs=17,stroke='#666666',**kw):
        fs = 20 if fs >= 22 else 18
        return a.box(k,bb,t,fill,font=fs,stroke=stroke,rounded='1',arcSize='8',**kw)
    def edge(k,p,m,arrow=True,c='#666666',**kw): return a.edge(k,p,m,arrow,strokeColor=c,strokeWidth='1.5',rounded='0',**kw)
    def panel(k,x,y,w,h,title,fill):
        a.frame(k,[x,y,w,h],fill); box(k+'_title',[x+18,y+16,w-36,38],title,fill,19,'none',fontColor='#ffffff',fontStyle='1')
    def row(prefix,x,y,n,w=190,h=42,fill='#ffffff'):
        for i,t in enumerate(n): box(f'{prefix}_{i}',[x,y+i*(h+14),w,h],t,fill,16)
    if kind=='ref24':
        a.frame('outer',[35,20,1030,1700],'#6f6f6f'); box('title',[90,45,920,46],name,'#548235',22,'none',fontColor='#ffffff',fontStyle='1')
        panel('left',70,125,170,1380,'纵向研究主线','#5b9bd5'); panel('middle',270,125,560,1380,'数据—方法—结果组织','#70ad47'); panel('right',860,125,170,1380,'阶段说明与产出','#c55a11')
        row('leftnode',92,220,['问题提出','资料采集','模型构建','实证分析','结论输出'],126,50,'#d9eaf7')
        row('rightnode',882,220,['第一章：背景','第二章：综述','第三章：方法','第四章：结果','第五章：建议'],126,50,'#fce4d6')
        for i,t in enumerate(['研究对象与目标','指标体系与数据来源','描述统计与关系识别','机制检验与稳健性','策略建议与成果']) : box(f'm{i}',[320,220+i*190,460,58],t,PALE[i%len(PALE)],18)
        for i in range(4):
            edge(f'vm{i}',[[241,245+i*190],[300,245+i*190]],'阶段进入研究包',True,'#5b9bd5')
            edge(f'mr{i}',[[790,245+i*190],[850,245+i*190]],'研究包对应章节',True,'#c55a11')
        box('footer',[90,1550,920,60],'形成可复核的研究闭环：问题—数据—方法—结果—建议','#f4b183',18,'#c55a11',fontStyle='1')
    elif kind in ('ref25','ref36'):
        a.frame('outer',[50,20,1000,1680],'#666666'); box('title',[95,44,910,50],name,'#4472c4',22,'none',fontColor='#ffffff',fontStyle='1')
        colors=['#f4b183','#9dc3e6','#a9d18e']; titles=['研究设计与数据准备','实验分析与机制识别','联合验证与结论输出']
        for s,(y,c,t) in enumerate(zip([130,670,1190],colors,titles)):
            panel(f'band{s}',90,y,920,450,t,c)
            row(f'band{s}l',125,y+90,['模块 A','模块 B','模块 C'],230,48,'#fffaf5' if s==0 else '#ffffff')
            row(f'band{s}r',740,y+90,['模块 X','模块 Y','模块 Z'],230,48,'#fffaf5' if s==0 else '#ffffff')
            box(f'band{s}core',[415,y+135,270,72],'核心分析 / 结果', '#ffffff',18,'#666666',fontStyle='1')
            for i in range(3):
                edge(f'band{s}e{i}',[[356,y+113+i*62],[390,y+113+i*62],[390,y+170],[414,y+170]],'输入汇入核心',True,c)
                edge(f'band{s}o{i}',[[686,y+170],[710,y+170],[710,y+113+i*62],[739,y+113+i*62]],'核心分发输出',True,c)
            if s<2: edge(f'between{s}',[[550,y+450],[550,y+505]],'阶段向下推进',True,'#4472c4')
    elif kind=='ref28':
        a.frame('outer',[55,20,990,1539],'#4472c4'); box('title',[85,44,930,46],name,'#4472c4',22,'none',fontColor='#ffffff',fontStyle='1')
        panel('upper',85,120,930,430,'双荧光素酶实验与靶点调控','#5b9bd5')
        row('ul',125,220,['激活映射','联邦学习','状态空间'],180,42,'#d9eaf7'); row('ur',775,220,['激活映射','联邦学习','决策框架'],180,42,'#e2f0d9')
        box('uc',[375,270,350,75],'机制耦合与强化学习控制','#ed7d31',20,'none',fontColor='#ffffff',fontStyle='1'); edge('u1',[[306,295],[350,295]],'左侧输入',True); edge('u2',[[750,295],[770,295]],'右侧输入',True)
        panel('middle',85,610,930,430,'细胞水平实验框架','#4472c4'); row('ml',130,730,['梯度加权','激活映射','Grad-CAM'],190,42); row('mr',775,730,['数据模块','模型模块','验证模块'],190,42); box('mc',[395,760,310,72],'多学科交叉 / 跨模态融合','#d9e2f3',18,'#4472c4',fontStyle='1'); edge('m1',[[321,810],[375,810]],'方法汇入',True); edge('m2',[[725,810],[770,810]],'结果输出',True)
        panel('lower',85,1100,930,390,'结论与建议','#70ad47'); row('ll',140,1215,['无标注数据','特征表示','泛化能力'],220,42,'#e2f0d9'); row('lr',710,1215,['机制解释','稳健性','应用建议'],220,42,'#e2f0d9'); box('lc',[410,1280,280,62],'验证结果与策略建议','#70ad47',18,'none',fontColor='#ffffff',fontStyle='1')
        edge('down1',[[550,550],[550,610]],'实验进入框架',True); edge('down2',[[550,1040],[550,1100]],'框架进入结论',True)
    elif kind=='ref29':
        a.frame('outer',[45,25,1010,1650],'#666666'); box('title',[90,50,920,48],name,'#203864',22,'none',fontColor='#ffffff',fontStyle='1')
        for s,(y,c,t) in enumerate([(145,'#8064a2','内容一：研究基础'),(500,'#548235','内容二：方法体系'),(855,'#c55a11','内容三：实证分析'),(1210,'#c00000','内容四：政策建议')]):
            panel(f's{s}',90,y,920,280,t,c); row(f's{s}a',125,y+92,['任务模块 1','任务模块 2','任务模块 3'],225,46,'#ffffff'); box(f's{s}core',[410,y+103,280,62],'阶段核心产出',PALE[s%len(PALE)],18,'#666666',fontStyle='1'); row(f's{s}b',720,y+92,['证据','模型','结果'],225,46,'#ffffff')
            if s<3: edge(f'flow{s}',[[550,y+280],[550,y+355]],'内容阶段推进',True,c)
    elif kind=='ref34':
        a.frame('outer',[80,20,900,1680],'#666666'); box('title',[160,45,740,48],name,'#f4b183',22,'none',fontColor='#ffffff',fontStyle='1')
        colors=['#70ad47','#5b9bd5','#00a2e8','#c00000']; titles=['第一阶段：研究基础','第二阶段：理论与模型','第三阶段：实证与验证','第四阶段：成果与推广']
        for s,(y,c,t) in enumerate(zip([125,500,875,1250],colors,titles)):
            panel(f'p{s}',115,y,830,300,t,c); row(f'p{s}l',150,y+90,['研究任务','数据来源'],220,46,'#ffffff'); box(f'p{s}c',[425,y+104,220,58],'核心工作包',PALE[s%len(PALE)],17,'#666666',fontStyle='1'); row(f'p{s}r',700,y+90,['方法','评价'],180,46,'#ffffff');
            if s<3: edge(f'next{s}',[[530,y+300],[530,y+375]],'阶段成果进入下一阶段',True,'#f4b183')
    elif kind=='ref38':
        a.frame('outer',[70,20,900,1700],'#666666'); box('title',[125,45,790,46],name,'#5b9bd5',22,'none',fontColor='#ffffff',fontStyle='1')
        for s,(y,c,t) in enumerate([(120,'#e4dfec','第一章节：研究基础'),(430,'#fff2cc','第二章节：理论建模'),(740,'#f4cccc','第三章节：用户/行为分析'),(1050,'#d9ead3','第四章节：算法与验证'),(1360,'#d9e2f3','第五章节：结论与建议')]):
            panel(f'c{s}',105,y,830,250,t,c); row(f'c{s}a',140,y+82,['研究问题','研究内容','研究方法'],205,42,'#ffffff'); row(f'c{s}b',690,y+82,['阶段产出','关键证据'],190,42,'#ffffff'); box(f'c{s}m',[390,y+120,220,58],'本章核心结论',c,16,'#666666',fontStyle='1');
            if s<4: edge(f'next{s}',[[520,y+250],[520,y+310]],'章节衔接',True,'#5b9bd5')
    else: raise ValueError(kind)
    if os.environ.get('QA_OFFSET'):
        a.box('qa_round_marker',[10,10,6,6],'','#d9d9d9',font=18,stroke='none',shape='ellipse')
    a.save('独立模板保留参考图的主要分区、标题层级、阶段连接和可替换字段；模板中的示例术语仅用于演示排版，使用前须按实际题意替换并审查。', f'画布按参考图比例重建；{name}的各分区、节点和连接均采用可编辑原生图元。', '原始截图保留在reference.png/reference-crop.png；无法可靠辨识的文字采用明确演示字段，不把示例术语当作论文事实。')

CONFIG={
 'research-design-vertical-loop':('ref-24','纵向研究设计与实证闭环图','ref24'),
 'triple-band-experiment-roadmap':('ref-25','三阶段联合实验与机制验证图','ref25'),
 'dual-circle-biological-framework-variant':('ref-28','双圆机制与实验框架变体图','ref28'),
 'four-content-evidence-roadmap':('ref-29','四内容模块与证据链研究路线图','ref29'),
 'four-stage-research-framework':('ref-34','四阶段研究内容与成果推广框架图','ref34'),
 'triple-band-research-validation':('ref-36','三带研究基础实验与联合验证图','ref36'),
 'five-chapter-research-roadmap':('ref-38','五章节研究内容与方法路线图','ref38'),
}
if __name__=='__main__':
 ident=sys.argv[1] if len(sys.argv)>1 else None
 if ident not in CONFIG: raise SystemExit(f'usage: {sys.argv[0]} <{"|".join(CONFIG)}>')
 ref,name,kind=CONFIG[ident]; make(Author(ident,ref,name),ident,ref,name,kind)
