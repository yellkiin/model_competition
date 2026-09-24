"""Ref-14: measured coupled analysis, model development and experiment framework."""
from authoring_support import Author, ROOT
import base64
import json
import math
import shutil
import urllib.parse
import zlib

a=Author('coupled-method-experiment-framework','ref-14','耦合方法构建与实验验证五带研究框架图')
extra=json.loads((ROOT/'calibration/ref-14-extra.json').read_text(encoding='utf8'))

def box(k,bb,text='',fill='none',fs=28,stroke='none',**style):
    return a.box(k,bb,text,fill,font=fs,stroke=stroke,**style)

def measured(k,idx,text,fs=28,**style):
    m=a.measure['boxes'][idx];x,y,w,h=m['bbox']
    fill={'#e8e6e4':'#e8e6e2','#fbf3cf':'#faf2cf','#faf3cf':'#faf2cf','#fbf2cd':'#faf2cf','#daf0f5':'#daf0f6','#dbf0f6':'#daf0f6'}.get(m['fill'],m['fill'])
    return box(k,[x-1,y-1,w+2,h+2],text,fill,fs,'#171717',**style)

def edge(k,pts,meaning,arrow=True,**style):
    defaults=dict(strokeColor='#151515',strokeWidth='2',rounded='0');defaults.update(style)
    a.edge(k,pts,meaning,arrow,**defaults)

def frame(k,bb,dashed=True,pattern='3 2'):
    x,y,w,h=bb
    edge(k,[[x,y],[x+w,y],[x+w,y+h],[x,y+h],[x,y]],'分区边界，不表示数据流或因果',False,dashed='1' if dashed else '0',dashPattern=pattern)

def poly(k,pts,fill,stroke='#555555'):
    xs,ys=zip(*pts);x,y=min(xs),min(ys);w,h=max(xs)-x,max(ys)-y
    path=''.join(f'<{"move" if i==0 else "line"} x="{xx-x:.3f}" y="{yy-y:.3f}"/>' for i,(xx,yy) in enumerate(pts))+'<close/>'
    xml=f'<shape w="{w}" h="{h}"><foreground><strokecolor color="{stroke}"/><strokewidth width="2"/><path>{path}</path><fillstroke/></foreground></shape>'
    co=zlib.compressobj(wbits=-15);raw=urllib.parse.quote(xml,safe="~()*!.'-").encode()
    return box(k,[x,y,w,h],fill=fill,shape='stencil('+base64.b64encode(co.compress(raw)+co.flush()).decode()+')')

# Split the outer frame where the title and side flags intentionally cover it.
for i,(y1,y2) in enumerate([(50,192),(548,743),(1099,1342),(1698,1724)]):
    for side,x in [('left',34),('right',1164)]:
        edge(f'outer_{side}_{i}',[[x,y1],[x,y2]],'装饰性外框；在侧标签处断开',False,strokeColor='#666666')
edge('outer_top_left',[[34,50],[111,50]],'外框左上边界',False,strokeColor='#666666')
edge('outer_top_right',[[1123,50],[1164,50]],'外框右上边界',False,strokeColor='#666666')
edge('outer_bottom',[[34,1724],[1164,1724]],'外框底边',False,strokeColor='#666666')
poly('title_background',[(112,17),(1121,17),(1121,70),(1110,82),(112,82)],'#d8e4f2','#222222')
poly('title_fold',[(1110,82),(1112,72),(1121,70)],'#adbac9','#222222')
box('title',[129,25,970,47],'基于耦合方法构建与实验验证的研究（示例）',fs=34,fontStyle='1')
for i,(y,h) in enumerate([(97,290),(403,249),(668,443),(1132,326),(1477,218)]):
    frame(f'band_{i}',[112,y,1009,h],pattern='8 4')

for i,(y,left,right) in enumerate([(193,'研究准备与总体设计','背景梳理与方案规划'),(744,'方法构建与技术优化','耦合工艺开发与改进'),(1343,'实验验证与成果总结','性能测试与成果分析')]):
    poly(f'left_flag_{i}',[(13,y),(53,y),(94,y+176),(53,y+353),(13,y+353)],'#d3dbe4')
    box(f'left_label_{i}',[20,y+13,44,327],'\n'.join(left),fs=26,fontStyle='1')
    n=box(f'right_label_{i}',[1137,y,55,353],'\n'.join(right),fill='#d3dbe4',stroke='#555555',fs=26,fontStyle='1')
    n['text_width']=26;n['text_height']=327

for i,x in enumerate([135,657]):
    edge(f'preparation_card_{i}',[[x,176],[x,370],[x+442,370],[x+442,176]],'上部卡片下部外框；标题自身描边组成上部边界',False)
measured('basis_header',1,'研究基础与问题分析')
measured('scheme_header',2,'总体研究方案构建')
measured('key_identification',5,'关键识别')
measured('research_goal',6,'研究目标')
measured('survey',10,'文献调研 + 需求调研 + 现状梳理',26)
measured('method_selection',7,'方法选择')
measured('overall_planning',8,'整体规划')
measured('route_design',11,'总体技术路线设计')
box('plus',[854,193,45,48],'+',fs=40,fontFamily='SimSun')
edge('identify_goal',[[328,217],[383,217]],'关键识别指向研究目标')
edge('survey_join',[[355,294],[355,220]],'三类调研汇入识别到目标的路径')
edge('planning_route',[[994,248],[994,294]],'整体规划连接总体路线设计，原图无箭尖',False)
edge('route_to_method',[[758,294],[758,249]],'总体路线设计反向约束方法选择')
for i,x in enumerate([591,614]):
    poly(f'preparation_chevron_{i}',[(x,210),(x+13,210),(x+28,250),(x+13,291),(x,291),(x+15,250)],'#f8dfd5','#171717')

box('theory_background',[135,426,133,207],fill='#eae6ee')
frame('theory_frame',[135,426,133,207])
box('theory',[151,452,101,153],'理论基\n础与方\n法体系\nA',fs=26)
box('coupled_framework_background',[966,426,134,207],fill='#eae6ee')
frame('coupled_framework_frame',[966,426,134,207])
box('coupled_framework',[980,466,106,128],'耦合方\n法框架\n构建',fs=26)
for i,(li,ri,l,r) in enumerate([(12,13,'核心梳理','优势分析'),(14,15,'要素提取','适配性评估'),(16,17,'约束分析','互补性验证')]):
    measured(f'analysis_left_{i}',li,l)
    measured(f'analysis_right_{i}',ri,r)

circles=[e['cx_cy_rx_ry'] for e in extra['ellipses']]
for i,(cx,cy,rx,ry) in enumerate(circles):
    box(f'coupling_fill_{i}',[cx-rx,cy-ry,2*rx,2*ry],fill='#e2d5e8',shape='ellipse')
# White lens: sample the actual intersection of the two measured ellipses.
c0,c1=circles;xs=[];ys=[]
for j in range(401):
    t=2*math.pi*j/400
    for cx,cy,rx,ry,other in [(*c0,c1),(*c1,c0)]:
        x,y=cx+rx*math.cos(t),cy+ry*math.sin(t)
        ox,oy,orx,ory=other
        if ((x-ox)/orx)**2+((y-oy)/ory)**2<=1.0001:xs.append(x);ys.append(y)
center=(sum(xs)/len(xs),sum(ys)/len(ys))
pts=sorted(zip(xs,ys),key=lambda p:math.atan2(p[1]-center[1],p[0]-center[0]))
poly('coupling_white_lens',pts,'#ffffff','#ffffff')
for i,(cx,cy,rx,ry) in enumerate(circles):
    n=box(f'coupling_outline_{i}',[cx-rx,cy-ry,2*rx,2*ry],stroke='#171717',shape='ellipse')
    n['semantic_attributes']=dict(diagramObject='coupling-venn',diagramRole='surface',overlapReason='同一耦合交集示意的两个无字椭圆轮廓按原图有意交叠，白色交集与两圆边界均保留')
for i,x in enumerate([527,640]):box(f'coupling_label_{i}',[x,490,68,78],'耦合\n分析',fs=26)
edge('coupling_left_stem',[[508,529],[480,529]],'左耦合分析向左侧三项检查分发',False)
edge('coupling_left_bus',[[480,455],[480,604]],'左侧三项并列分析母线',False)
edge('coupling_right_stem',[[730,529],[754,529]],'右耦合分析向右侧三项检查分发',False)
edge('coupling_right_bus',[[754,455],[754,604]],'右侧三项并列分析母线',False)
for i,y in enumerate([455,529,604]):
    edge(f'coupling_left_{i}',[[480,y],[453,y]],'从耦合分析向左分析节点扇出，箭头朝左')
    edge(f'coupling_right_{i}',[[754,y],[779,y]],'从耦合分析向右验证节点扇出，箭头朝右')

box('model_background',[135,683,965,165],fill='#ededed')
frame('model_frame',[135,683,965,165])
measured('model_header',18,'核心模型 / 算法开发')
for idx,k,t in [(21,'model_structure','模型结构设计与搭建'),(20,'model_parameters','参数初始化与调优'),(23,'model_performance','瓶颈突破性能提升')]:measured(k,idx,t)
box('optimization_background',[135,861,965,236],fill='#d9e7f9')
frame('optimization_frame',[135,861,965,236])
measured('optimization_header',26,'关键技术优化与改进')
measured('optimization_diagnosis',27,'技术瓶颈诊断与优化方向分析')
for idx,k,t in [(29,'parameter_iteration','关键参数迭代优化'),(28,'structure_improvement','方法 / 模型结构改进'),(30,'performance_check','性能验证与效果提升')]:measured(k,idx,t)

for idx,k,t in [(34,'platform','实验平台搭建'),(35,'experiment_design','实验方案设计'),(36,'condition_quality','实验条件与质量管控'),(32,'preprocessing','数据预处理与标准化'),(37,'statistics','统计与结果可视化'),(38,'iteration','迭代优化与验证闭环')]:
    n=measured(k,idx,'\n'.join(t),26);n['text_width']=26;n['text_height']=282
for idx,k,t in [(31,'simulation','仿真实验开展'),(39,'data_collection','实验数据采集'),(41,'initial_analysis','结果初步分析'),(44,'performance_optimization','性能评估优化'),(33,'metric_evaluation','性能指标评估'),(40,'error_diagnosis','误差溯源与问\n题诊断'),(43,'optimization_strategy','优化策略制定')]:measured(k,idx,t)
for i,(x1,x2) in enumerate([(201,231),(298,327),(604,633),(699,728),(1005,1034)]):edge(f'experiment_step_{i}',[[x1,1295],[x2,1295]],'实验链由左向右推进，组合框从整体右边界输出')

measured('results_header',45,'研究成果总结与创新提炼')
for i,(idx,t) in enumerate([(46,'研究结论梳理'),(47,'核心创新点提炼'),(48,'应用价值分析'),(49,'不足与未来展望')]):measured(f'result_{i}',idx,t)
edge('results_stem',[[623,1557],[623,1588]],'成果总结分解为四类输出',False)
edge('results_bus',[[246,1588],[989,1588]],'四项成果共用分发母线',False)
for i,x in enumerate([246,492,741,989]):edge(f'result_drop_{i}',[[x,1588],[x,1618]],'总体成果到对应梳理、创新、应用或展望')

a.save('五带框架：研究基础与总体方案两卡，双耦合圆分别向左右三项分析扇出，模型开发与技术优化分区，六站实验处理链（包含四项与三项组合卡），成果总结四分支。左右各三条阶段标签跨带对应；模型和技术优化框之间没有凭空新增流程箭头。',
'画布1206×1743；主分带x112..1121，y97/403/668/1132/1477；卡片和填充来自ref-14实测候选框；耦合椭圆来自暗像素边缘最小二乘标定ref-14-extra.json；实验链y1148..1442，成果四分支母线y1588。全部坐标与路由见layout.json。',
'原生框、文字、箭头、折角、双箭纹和双椭圆可编辑；白色交叠透镜保留原图并重新覆盖两圆轮廓。标题标注示例。截图实验组合卡首行“仿真实验开”疑似缺末字，本模板明确采用演示文案“仿真实验开展”，不是声称精确转录。右侧“耦合工艺”保留截图措辞，不证明适用于任意方法。水印有意不重建；字体、椭圆曲线采样、箭尖与细微底色存在近似。固定五带和节点数量，允许范围内换文案，不承诺任意增删。')
shutil.copy2(ROOT/'calibration/ref-14-extra.json',ROOT/'library/assets'/a.ident/'curve-measurements.json')
