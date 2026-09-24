"""Ref-22: independently editable multifeature detection research workflow."""
from authoring_support import Author,ROOT
import math,json,base64,zlib,urllib.parse

a=Author('feature-detection-research-5band','ref-22','多特征融合与目标检测五带研究路线图')
ORANGE='#fbd6bc';GREEN='#e0edd6';BLUE='#b8dce9';PURPLE='#b5c6e9';PEACH='#fae4d5'
def box(k,bb,text,fill,fs=26,stroke='#171717',**st):return a.box(k,bb,text,fill,font=fs,stroke=stroke,**st)
def label(k,bb,text,fs=26,**st):return box(k,bb,text,'none',fs,'none',**st)
def rect(k,bb,text,fill,fs=26,stroke='#171717',**st):return box(k,bb,text,fill,fs,stroke,rounded='1',arcSize='18',**st)
def edge(k,pts,meaning,arrow=True,**st):a.edge(k,pts,meaning,arrow,**st)
def poly(k,pts,fill,stroke='#171717'):
    xs,ys=zip(*pts);x,y=min(xs),min(ys);w,h=max(xs)-x,max(ys)-y
    coords=[((px-x)/w*100,(py-y)/h*100) for px,py in pts]
    commands=''.join(f'<{"move" if i==0 else "line"} x="{px}" y="{py}"/>' for i,(px,py) in enumerate(coords))+'<close/>'
    xml=f'<shape w="100" h="100" aspect="variable"><foreground><path>{commands}</path><fillstroke/></foreground></shape>'
    c=zlib.compressobj(wbits=-15);raw=urllib.parse.quote(xml,safe="~()*!.'-").encode();encoded=base64.b64encode(c.compress(raw)+c.flush()).decode()
    return box(k,[x,y,w,h],'',fill,stroke=stroke,shape='stencil('+encoded+')')
def frame(k,bb,color='#404040'):
    a.frame(k,bb,True);a.edges[-1]['style'].update(dashPattern='4 3',strokeColor=color)

box('title',[34,14,1142,73],'基于多特征融合的图像目标检测方法研究技术路线（示例）','#cdd5df',30,stroke='none',fontStyle='1')['text_height']=38
for i,(y,h,text) in enumerate([(175,296,'特征提取网络'),(605,296,'特征融合'),(1033,296,'目标检测'),(1429,295,'分类输出层')]):
    cy=y+h/2
    poly(f'flag_{i}',[(34,y),(102,y),(102,cy-13),(112,cy-13),(112,cy-27),(137,cy),(112,cy+27),(112,cy+13),(102,cy+13),(102,y+h),(34,y+h)],'#e9edf4','#a3acbd')
    label(f'flag_text_{i}',[54,y+26,30,h-52],'\n'.join(text),27,fontStyle='1')['text_width']=27
bands=[(94,200,109,'研究总体流程','#f7c79f','#91591c'),(310,388,327,'关键技术路径分解','#a9b39b','#536b2a'),(718,354,730,'核心方法与优化机制','#92cddb','#39768b'),(1088,496,1107,'研究实施与验证流程','#f3b6bf','#d18c42'),(1599,126,1614,'研究迭代与应用闭环','#fce298','#91591c')]
for i,(y,h,ty,title,fill,stroke) in enumerate(bands):
    frame(f'band_{i}',[149,y,1027,h]);rect(f'band_title_{i}',[373,ty,568,39],title,fill,27,stroke,fontStyle='1')['text_height']=33

for i,(x,head,detail) in enumerate(zip([158,421,684,947],['研究准备','特征提取','模型构建','结果分析'],['数据采集','特征筛选','模型训练','性能评估'])):
    rect(f'overview_stage_{i}',[x,162,210,45],head,ORANGE,27,'#975923')['text_height']=33
    rect(f'overview_detail_{i}',[x,239,210,45],detail,ORANGE,27,'#975923')['text_height']=33
    edge(f'overview_drop_{i}',[[x+105,209],[x+105,237]],'本阶段对应下方具体活动')
    if i<3:edge(f'overview_step_{i}',[[x+212,184],[x+261,184]],'总体流程按四阶段向右推进')
for i,bb in enumerate([[162,379,483,313],[680,379,480,313]]):frame(f'technical_panel_{i}',bb,'#5c5c5c')
for k,bb,t in [('data_base',[174,389,456,45],'基础数据构建'),('feature_engineering',[174,448,456,45],'特征工程模块'),('method_design',[691,389,456,45],'方法 / 模型框架设计'),('method_implementation',[691,495,456,45],'模型 / 方法实现')]:rect(k,bb,t,GREEN,27,'#65813e')['text_height']=33
for i,(x,t,d) in enumerate(zip([174,330,486],['构建','问题','定义'],['图像数\n据集','颜色特\n征集','深度卷\n积特征'])):
    rect(f'feature_definition_{i}',[x,510,144,45],t,GREEN,27,'#65813e')['text_height']=33
    rect(f'feature_object_{i}',[x,579,144,100],d,GREEN,27,'#65813e')
    edge(f'feature_object_drop_{i}',[[x+72,557],[x+72,577]],'该项特征工程定义对应下方数据或特征集')
for i,(x,w,t) in enumerate([(691,153,'理论推导'),(849,153,'方案优化'),(1007,140,'工艺实现')]):
    if i==0:pts=[(x,446),(x+w-18,446),(x+w,464),(x+w-18,482),(x,482)]
    elif i==1:pts=[(x,446),(x+w-18,446),(x+w,464),(x+w-18,482),(x,482),(x+18,464)]
    else:pts=[(x,446),(x+w,446),(x+w,482),(x,482),(x+18,464)]
    poly(f'design_chevron_{i}',pts,GREEN,'#65813e')
    label(f'design_chevron_text_{i}',[x+18,450,w-34,29],t,24)['text_height']=29
box('technical_transfer',[647,524,30,33],'','#82985b',stroke='none',shape='singleArrow',direction='east',arrowWidth='0.50',arrowSize='0.40')
edge('validation_root',[[919,542],[919,558]],'方法实现分为三项并列验证',False)
edge('validation_bus',[[763,558],[1075,558]],'三项验证共享母线',False)
for i,x in enumerate([691,847,1003]):
    rect(f'validation_{i}',[x,579,144,100],f'验证 {i+1}',GREEN,27,'#65813e')
    edge(f'validation_drop_{i}',[[x+72,558],[x+72,577]],'方法进入该项验证')

# Circle is split only at the five foreground node rectangles. Visible arcs
# retain the measured contour and no invented arrowheads.
circle=json.loads((ROOT/'calibration/ref-22-extra.json').read_text(encoding='utf8'));cx,cy=circle['center'];radius=circle['radius']
cycle=[('input',[305,834,83,36],'输入'),('processing',[222,884,82,36],'处理'),('features',[382,884,82,36],'特征'),('assessment',[247,953,82,37],'评估'),('model',[352,953,82,37],'模型')]
arcs=[];current=[]
for i in range(721):
    t=2*math.pi*i/720;x=cx+radius*math.cos(t);y=cy+radius*math.sin(t)
    hidden=any(bx-2<=x<=bx+w+2 and by-2<=y<=by+h+2 for _,(bx,by,w,h),_ in cycle)
    if hidden:
        if len(current)>1:arcs.append(current)
        current=[]
    else:current.append([round(x,2),round(y,2)])
if len(current)>1:arcs.append(current)
for i,points in enumerate(arcs):edge(f'cycle_arc_{i}',points,'左侧五节点共同环形关联，原图圆环没有方向箭头',False,strokeColor='#75869a',strokeWidth='2')
for k,bb,t in cycle:rect('cycle_'+k,bb,t,PURPLE,20,'#75869a')['text_height']=25
rect('data_node',[159,854,49,134],'数\n据',BLUE,27,'#39768b')['text_width']=28
rect('optimization_node',[1116,854,49,134],'优\n化',BLUE,27,'#39768b')['text_width']=28
box('core_background',[476,781,376,279],'','#ffffff',stroke='none')
edge('core_left_outline',[[476,838],[476,1004]],'核心模型面板左边界',False,strokeColor='#6cb5c4')
edge('core_right_outline',[[852,838],[852,1004]],'核心模型面板右边界',False,strokeColor='#6cb5c4')
for k,y,t in [('heading',781,'核心模型 / 方法主体'),('output',1006,'输出 / 结果')]:rect('core_'+k,[477,y,374,55],t,BLUE,27,'#39768b')['text_height']=33
for i,y in enumerate([853,903,952]):rect(f'core_submodule_{i}',[489,y,350,37],f'子模块 {i+1}','#d9edf2',27,'#8dc9d3')['text_height']=33
for i,(y,end_y) in enumerate([(808,852),(1034,990)]):
    edge(f'core_to_data_{i}',[[475,y],[183,y],[183,end_y]],'核心主体或输出向左侧数据接口回接；保持参考箭尖落于数据节点',True,dashed='1',dashPattern='4 3',strokeColor='#3c6e78')
    edge(f'optimization_to_core_{i}',[[1140,end_y],[1140,y],[853,y]],'右侧优化接口分别回接核心主体和输出端',True,dashed='1',dashPattern='4 3',strokeColor='#3c6e78')
for k,bb,t in [('action',[947,854,82,36],'动作'),('result',[884,941,82,36],'结果'),('feedback',[1007,941,82,36],'反馈')]:rect('optimization_'+k,bb,t,PURPLE,20,'#75869a')['text_height']=25
edge('action_to_result',[[971,892],[927,939]],'动作影响结果；参考为单向箭头',strokeColor='#75869a')
edge('action_feedback',[[1010,892],[1046,939]],'动作与反馈双向关联',strokeColor='#75869a',startArrow='block',startFill='1')
for i,y in enumerate([951,966]):edge(f'result_feedback_{i}',[[968,y],[1005,y]],'结果与反馈的双向关联，保留参考的两条平行关系',strokeColor='#75869a',startArrow='block',startFill='1')

rect('research_question',[185,1161,432,45],'研究问题 / 假设提出',PEACH,27,'#b96820')['text_height']=33
rect('research_implementation',[705,1161,435,45],'模型 / 方法实施',PEACH,27,'#b96820')['text_height']=33
edge('question_to_implementation',[[619,1183],[703,1183]],'研究问题引出方法实施')
poly('condition_surface',[(400,1234),(497,1285),(400,1337),(303,1285)],PEACH,'#b96820')
label('condition_text',[365,1251,70,67],'条件\n判断',27).update(text_width=56,text_height=65)
edge('question_to_condition',[[400,1208],[400,1232]],'研究问题进入条件判断')
edge('condition_root',[[400,1339],[400,1348]],'条件判断连接三个路径',False)
edge('condition_bus',[[241.5,1348],[570.5,1348]],'三个路径分支共享母线',False)
for i,x in enumerate([168,333,497]):
    rect(f'path_{i}',[x,1372,147,43],f'路径 {i+1}',PEACH,27,'#b96820')['text_height']=33
    edge(f'path_drop_{i}',[[x+73.5,1348],[x+73.5,1370]],'条件对应该路径，不补造原图未给出的分支条件')
    edge(f'path_merge_{i}',[[x+73.5,1417],[x+73.5,1430]],'路径结果汇入整合母线',False)
edge('path_merge_bus',[[241.5,1430],[570.5,1430]],'三路径结果汇合',False)
edge('path_merge_root',[[400,1430],[400,1452]],'汇合结果进入路径融合')
rect('path_integration',[184,1454,433,45],'路径融合 / 结果整合',PEACH,27,'#b96820')['text_height']=33
rect('phase_conclusion',[252,1529,295,44],'阶段结论',PEACH,27,'#b96820')['text_height']=33
edge('integration_conclusion',[[400,1501],[400,1527]],'整合后形成阶段结论')
edge('experiment_root',[[922,1208],[922,1224]],'方法实施进入两个验证分支',False)
edge('experiment_bus',[[804.5,1224],[1043.5,1224]],'对比与方案验证并列',False)
for i,(x,w,t) in enumerate([(705,199,'对比实验'),(947,193,'方案验证')]):
    rect(f'experiment_{i}',[x,1244,w,43],t,PEACH,27,'#b96820')['text_height']=33
    edge(f'experiment_drop_{i}',[[x+w/2,1224],[x+w/2,1242]],'实施方法进入本验证活动')
    edge(f'experiment_join_{i}',[[x+w/2,1289],[x+w/2,1306]],'验证结果汇入整合',False)
edge('experiment_merge_bus',[[804.5,1306],[1043.5,1306]],'双验证结果汇合',False)
edge('experiment_merge_root',[[922,1306],[922,1324]],'共同结果进入统计分析')
rect('result_analysis',[705,1326,435,43],'结果整合 / 统计分析',PEACH,27,'#b96820')['text_height']=33
rect('result_visualization',[705,1397,435,43],'结果可视化 / 解释',PEACH,27,'#b96820')['text_height']=33
edge('analysis_to_visualization',[[922,1371],[922,1395]],'统计结果进入可视化解释')
poly('conclusion_surface',[(924,1468),(1016,1521),(924,1574),(832,1521)],PEACH,'#b96820')
label('conclusion_text',[889,1486,70,67],'结论\n判断',27).update(text_width=56,text_height=65)
edge('visualization_to_conclusion',[[922,1442],[924,1466]],'解释结果进入结论判断')
for i,(x,t) in enumerate(zip([158,431,705,978],['初始方案','实施','评估','优化'])):
    rect(f'iteration_{i}',[x,1668,188,46],t,'#fff1cc',27,'#ad8b21')['text_height']=33
    if i<3:box(f'iteration_pair_{i}',[x+190,1678,79,25],'','#9b551c',stroke='none',shape='doubleArrow',arrowWidth='0.5',arrowSize='0.20')

a.save('五带研究路线：四阶段总体流程、双栏关键技术路径、核心方法及左圆环/右反馈图、双栏实施验证、四节点双向迭代。左侧四个竖旗为特征提取网络/融合/检测/输出层说明，不擅自增加旗标间流程箭头。保留条件判断三路汇合、双验证合流、结果反馈双平行双向线与原图各虚线箭头方向。',
'画布1206×1743，主栏x149–1176，五带y94–294/310–698/718–1072/1088–1584/1599–1725；副旗x34–137。大多数矩形由measurement.json实测框映射至统一栅格。左侧环线使用ref-22-extra.json拟合圆心/半径，在实测五标签覆盖区域断开可见弧。三枚路径设计箭形保留前进轮廓并给相邻轮廓留4–5px，文字须在斜边安全区。',
'全部框、菱形、圆弧、箭头与文字原生可编辑，无整图位图。水印不复刻；主标题添加示例标记。三枚浅绿箭形是路径标签，不新增节点间因果线；左环无方向，右侧两条双向反馈线照参考保留而不解释成独立实验。源图概念模块混合算法与研究流程，文案仅作演示；真实论文按所需专用skill路由，不可代替算法内部科学说明。字体、圆角与斜边间距存在明确近似，尚待实际三轮渲染审查。')
