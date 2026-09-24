"""Ref-23: editable dual-circle mechanism and two-layer framework."""
from authoring_support import Author
import math

ID='dual-circle-biological-framework'
a=Author(ID,'ref-23','双圆机制与双层实验框架图')
B='#4472c4'; BD='#2f5597'; G='#548235'; GL='#e2f0d9'; PALE='#dae3f3'; ORANGE='#c55a11'; LT='#eef4f8'
def box(k,bb,t='',fill='none',fs=22,stroke='#202020',**kw):
    fs={17:18,19:18,21:20,28:22}.get(fs,fs)
    return a.box(k,bb,t,fill,font=fs,stroke=stroke,**kw)
def label(k,bb,t,fs=22,**kw): return box(k,bb,t,'none',fs,'none',**kw)
def card(k,bb,t,fill=LT,fs=20,stroke='#202020',**kw): return box(k,bb,t,fill,fs,stroke,rounded='1',arcSize='12',**kw)
def edge(k,pts,m,arrow=False,color='#202020',**kw):
    st=dict(strokeColor=color,strokeWidth='2',rounded='0');st.update(kw);a.edge(k,pts,m,arrow,**st)
def frame(k,bb,color='#6d7d88'):
    x,y,w,h=bb;edge(k,[[x,y],[x+w,y],[x+w,y+h],[x,y+h],[x,y]],'分区边界，不表示方向或因果',False,color,dashed='1',dashPattern='4 3')
def ellipse_arcs(k,cx,cy,rx,ry,avoid,colour,dash=None):
    parts=[];pts=[]
    for i in range(721):
        t=2*math.pi*i/720;px=cx+rx*math.cos(t);py=cy+ry*math.sin(t)
        hidden=any(x-2<=px<=x+w+2 and y-2<=py<=y+h+2 for x,y,w,h in avoid)
        if hidden:
            if len(pts)>2: parts.append(pts)
            pts=[]
        else: pts.append([round(px,2),round(py,2)])
    if len(pts)>2: parts.append(pts)
    for i,p in enumerate(parts):
        st=dict(strokeColor=colour,strokeWidth='2',rounded='0')
        if dash: st.update(dashed='1',dashPattern=dash)
        a.edge(f'{k}_{i}',p,'实测椭圆轮廓；原图无方向箭头',False,**st)

# Top mechanism panel. The background remains a borderless editable surface.
box('upper_surface',[46,3,986,498],'',LT,20,'none')
frame('upper_border',[46,3,986,498],B)
label('upper_left_title',[78,27,260,35],'双荧光素酶实验',28,fontColor=BD,fontStyle='1')
label('upper_right_title',[775,27,240,35],'靶点抑制 / 活化',28,fontColor=G,fontStyle='1')
label('upper_left_subtitle',[78,74,430,30],'知识蒸馏技术在小样本学习中的模型压缩方法',18)
label('upper_right_subtitle',[623,74,391,30],'自监督学习在无标注数据下的特征表示优化方法',18)
edge('upper_separator',[[58,117],[1018,117]],'顶部说明与机制区分隔线',False,'#b6b6b6',dashed='1',dashPattern='3 3')
left=[('upper_left_0','激活映射','突发流量'),('upper_left_1','联邦学习','一般分布'),('upper_left_2','状态空间','决策过程')]
right=[('upper_right_0','激活映射','离散伸缩'),('upper_right_1','联邦学习','笛卡尔积'),('upper_right_2','决策框架','智能调度')]
for side,items,x,colour in [('left',left,67,B),('right',right,839,G)]:
    for i,(k,h,b) in enumerate(items):
        y=158+i*104;ww=160 if side=='left' else 175
        card(k+'_head',[x,y,ww,38],h,colour,21,'none',fontColor='#ffffff',fontStyle='1')
        card(k+'_body',[x+5,y+46,ww-10,38],b,'#ffffff',20,colour)
        edge(k+'_stem',[[x+ww/2,y+39],[x+ww/2,y+44]],'标题对应下方观测项',False,colour)
avoid=[(419,257,239,99),(437,130,212,35),(437,459,212,35),(477,233,122,35),(494,241,119,28),(502,335,83,27),(467,363,143,31),(488,379,114,30),(321,370,113,36),(648,370,113,36)]
ellipse_arcs('outer_blue',452.02,308.00,158.89,143.97,avoid,B)
ellipse_arcs('outer_green',624.74,308.00,158.83,143.94,avoid,G)
ellipse_arcs('inner_blue',400.42,308.04,100.93,98.35,avoid,BD,'4 3')
ellipse_arcs('inner_green',676.25,307.96,100.69,98.45,avoid,G,'4 3')
label('upper_top_capsule',[437,130,212,35],'细胞生物学行为',21,fontColor='#ffffff',fontStyle='1')
label('upper_bottom_capsule',[437,459,212,35],'细胞生物学行为',21,fontColor='#ffffff',fontStyle='1')
label('upper_strategy',[494,241,119,28],'进化策略',19,fontColor='#536b2a',fontStyle='1')
card('upper_arrow_body',[466,270,145,72],'DQN 强化学\n控制回路',ORANGE,21,'none',fontColor='#ffffff',fontStyle='1')
box('upper_arrow_left',[419,270,49,72],'',ORANGE,20,'none',shape='singleArrow',direction='west',arrowWidth='.6',arrowSize='.35')
box('upper_arrow_right',[611,270,47,72],'',ORANGE,20,'none',shape='singleArrow',direction='east',arrowWidth='.6',arrowSize='.35')
card('upper_warmup',[503,346,83,27],'预热',ORANGE,18,'none',fontColor='#ffffff',fontStyle='1')
label('upper_simulation',[488,379,114,30],'缓解仿真',18,fontColor=ORANGE)
label('blue_strategy',[316,269,112,32],'策略生成',22,fontColor=BD,fontStyle='1')
label('blue_rule',[322,310,103,50],'伸缩 / 迁\n移',20,fontColor=BD)
card('blue_action',[321,370,113,36],'动作序列',B,20,'none',fontColor='#ffffff',fontStyle='1')
label('green_strategy',[649,269,112,32],'近似推理',22,fontColor=G,fontStyle='1')
label('green_rule',[652,310,109,50],'在线 / 学',20,fontColor=G)
card('green_space',[648,370,113,36],'高维空间',G,20,'none',fontColor='#ffffff',fontStyle='1')
for side,x,colour in [('left',282,B),('right',795,G)]:
    y=209;edge(f'{side}_dotline',[[x,y],[x-35 if side=='left' else x+35,y]],'外侧输入关联，圆点为接口',False,colour)
    box(f'{side}_dot',[x-4,y-4,8,8],'',colour,20,'none',shape='ellipse')
edge('upper_green_flow',[[244,209],[839,209]],'绿色横向输入/输出关联',True,G)
edge('upper_orange_flow',[[243,416],[838,416]],'橙色横向验证关联',True,ORANGE)
edge('upper_black_top',[[249,178],[329,158],[433,145]],'上弧线向两侧输出',True)
edge('upper_black_top_right',[[660,145],[750,158],[811,178]],'上弧线向两侧输出',True)
edge('upper_black_bottom',[[249,447],[329,468],[433,485]],'下弧线向两侧输出',True)
edge('upper_black_bottom_right',[[660,485],[750,468],[811,447]],'下弧线向两侧输出',True)

# Two-layer experimental framework. Large panels are outlines so every inner
# card remains independently selectable and the strict checker sees no opaque
# container collision.
label('framework_title',[122,539,807,43],'细胞水平明确［Target Name］对细胞恶性生物学行为的影响及作用机制',22,fontColor='#ffffff',fontStyle='1')
frame('main_frame',[45,625,987,761],G)
frame('blue_frame',[77,652,926,228],B)
frame('green_frame',[77,1125,926,228],G)
card('blue_panel_title',[97,671,891,37],'细胞水平明确［Target Name］对细胞恶性生物学行为的影响及作用机制','#b4c7e7',20,'#202020',fontStyle='1')
card('green_panel_title',[97,1145,891,41],'细胞水平明确［Target Name］对细胞恶性生物学行为的影响及作用机制','#c5e0b4',20,'#202020',fontStyle='1')
def framework_row(prefix,y,leftx,rightx,colour):
    for side,x in [('l',leftx),('r',rightx)]:
        for j,h in enumerate(['联邦学习框架']*3):
            card(f'{prefix}_{side}_{j}',[x,y+j*49,183 if side=='l' else 183,33],h,'#ffffff',18,'#202020')
        edge(f'{prefix}_{side}_bus',[[x+184,y+16],[x+197,y+16],[x+197,y+115]],'三项框架共享母线',False,colour)
framework_row('blue_framework',731,230,666,BD)
framework_row('green_framework',1207,242,630,G)
label('blue_left_note',[96,746,121,112],'梯度加权\n激活映射\nGrad-CA\n优化',18)
label('blue_right_note',[870,746,121,112],'梯度加权\n激活映射\nGrad-CA\n优化',18)
label('green_left_note',[99,1200,117,125],'无标注数\n据下的特征\n表示',18)
label('green_right_note',[864,1200,117,125],'无标注数\n据下的特征\n表示',18)
def closed_edge(k,pts,m='原生斜面轮廓，无额外方向',colour='#202020'):
    edge(k,pts+[pts[0]],m,False,colour)
closed_edge('blue_butterfly_left',[(436,730),(541,730),(541,862),(436,862)])
closed_edge('blue_butterfly_right',[(541,730),(646,730),(646,862),(541,862)])
label('blue_butterfly_left_text',[449,766,79,56],'多学科\n交叉',18,fontStyle='1')
label('blue_butterfly_right_text',[552,766,79,56],'跨模态\n融合',18,fontStyle='1')
label('blue_cloud',[482,826,22,24],'☁',18);label('blue_target',[586,826,26,24],'◎',18)
for side,x in [('l',84),('r',866)]:
    card(f'blue_side_{side}',[x,905,130,38],'到达过程',BD,20,'none',fontColor='#ffffff',fontStyle='1')
    card(f'blue_side_{side}_body',[x+4,951,122,38],'突发流量','#ffffff',18,'#999999')
    card(f'blue_side_{side}_2',[x,1009,130,38],'激活映射',BD,20,'none',fontColor='#ffffff',fontStyle='1')
    card(f'blue_side_{side}_body2',[x+4,1055,122,38],'一般分布','#ffffff',18,'#999999')
box('blue_data',[260,960,67,92],'数\n据',B,20,'#202020',shape='halfCircle',fontColor='#ffffff')
box('blue_model',[748,960,67,92],'模\n型',G,20,'#202020',fontColor='#ffffff',shape='halfCircle',flipH='1')
box('blue_arrow_left',[339,902,52,166],'数\n据\n成\n对\n标\n注',PALE,17,'#202020',shape='upArrow',fontStyle='1')
box('blue_arrow_right',[686,902,52,166],'知\n识\n蒸\n馏\n模\n型',PALE,17,'#202020',shape='upArrow',fontStyle='1')
card('blue_core',[392,957,288,32],'细胞生物学行为',B,19,'none',fontColor='#ffffff',fontStyle='1')
label('blue_core_middle',[392,996,288,44],'细胞水平明确对细胞生物学\n行为的影响及作用机制',18,fontColor='#ffffff',fontStyle='1')
card('blue_core_bottom',[392,1042,288,32],'细胞生物学行为',PALE,19,'#202020',fontStyle='1')
edge('blue_arrow_left_out',[[258,978],[229,978]],'数据模块向左侧到达过程输出',True,BD)
edge('blue_arrow_right_out',[[816,978],[865,978]],'模型模块向右侧到达过程输出',True,G)
label('green_multi',[470,1204,130,61],'多学科\n交叉',18,fontStyle='1');label('green_cross',[470,1271,130,57],'跨模态\n融合',18,fontStyle='1')
label('green_cloud',[430,1188,24,24],'☁',18);label('green_target',[430,1324,26,24],'◎',18)
label('lower_bar',[122,1429,807,43],'细胞水平明确［Target Name］对细胞恶性生物学行为的影响及作用机制',22,fontColor='#ffffff',fontStyle='1')
edge('green_panel_baseline',[[77,1386],[1003,1386]],'上下实验框架分隔线',False,'#a9d18e')

a.save('上部保留双荧光素酶/靶点抑制双栏、四个实测椭圆轮廓、中央双向强化学习块、三类侧向输入和上下细胞行为胶囊。中部保留蓝色联邦学习框架、蝴蝶结交叉模块、数据/模型半圆、双头标注箭和两侧到达过程。下部保留绿色双层联邦框架与多学科/跨模态中心。所有原图混杂术语均为演示文案，不能直接当作论文科学事实。',
'画布1075×1535；顶部实测框和椭圆中心/半轴见calibration/ref-23-extra.json；中部蓝/绿面板及上下横条按ref-23.json逐框标定。重叠椭圆采用分段原生曲线，中央文字区和卡片区主动留缺口，避免箭头/文字被轮廓穿过。',
'所有框、文字、椭圆曲线、双向块箭头、斜面、半圆、双头箭与分区边界均为原生可编辑图元，无整图位图。顶部半透明渐变与下部梯形阴影以无文字分区框和线条近似；原图遮挡/不确定文字使用明确演示字段。ref-28为独立保留变体，不能合并。A4/A3尺寸、三轮渲染、容量替换和视觉得分尚待实际验证。')
