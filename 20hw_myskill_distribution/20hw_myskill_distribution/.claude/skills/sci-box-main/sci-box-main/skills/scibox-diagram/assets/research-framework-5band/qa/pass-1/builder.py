"""Ref-19: five-stage workflow with native prism cards and scenario decisions."""
from authoring_support import Author
import base64,zlib,urllib.parse

a=Author('research-framework-5band','ref-19','五阶段研究框架与多场景决策流程图')
def box(key,bb,text,fill,font=27,stroke='#365f91',**kw):
    return a.box(key,bb,text,fill,font=font,stroke=stroke,**kw)
def label(key,bb,text,font=27,**kw):return box(key,bb,text,'none',font,stroke='none',**kw)
def poly(key,points,fill,stroke='#365f91',width=2):
    xs,ys=zip(*points);x,y=min(xs),min(ys);w,h=max(xs)-x,max(ys)-y
    coords=[((xx-x)/w*100,(yy-y)/h*100) for xx,yy in points]
    commands=f'<move x="{coords[0][0]}" y="{coords[0][1]}"/>'+''.join(f'<line x="{xx}" y="{yy}"/>' for xx,yy in coords[1:])+'<close/>'
    xml=f'<shape w="100" h="100" aspect="variable" strokewidth="inherit"><foreground><path>{commands}</path><fillstroke/></foreground></shape>'
    z=zlib.compressobj(wbits=-15);encoded=urllib.parse.quote(xml,safe="~()*!.'-").encode();data=base64.b64encode(z.compress(encoded)+z.flush()).decode()
    return box(key,[x,y,w,h],'',fill,stroke=stroke,shape='stencil('+data+')',strokeWidth=str(width))
def frame(key,bb):
    x,y,w,h=bb
    a.edge(key,[[x+w/2,y],[x+w,y],[x+w,y+h],[x,y+h],[x,y],[x+w/2,y]],'分区边框，不是流程箭头',False,dashed='1',dashPattern='3 2',rounded='1',arcSize='22',strokeWidth='1.5')
for key,idx,text in [('header_framework',2,'研究框架'),('header_content',0,'研究内容'),('header_methods',1,'研究方法')]:
    a.measured(key,idx,text,'#f9dade',font=27,stroke='#7b2036',rounded='1',arcSize='20',fontStyle='1')
bands=[(108,276,'研究整体框架','#679591'),(395,291,'研究阶段流程','#829871'),(700,295,'数据处理与分析流程','#9a7c29'),(1007,426,'多场景决策与执行流程','#d99968'),(1446,283,'成果与应用方向','#6782ba')]
left=[('文献研究法',166,181),('实验研究法',454,182),('数据分析法',775,182),('对比分析法',1129,181),('归纳总结法',1507,181)]
right=['总体设计','阶段实施','数据处理','场景验证','成果总结']
for i,((y,h,title,color),(method,ly,lh)) in enumerate(zip(bands,left)):
    frame(f'band_{i}',[176,y,882,h])
    box(f'band_title_{i}',[350,y+12,533,47],title,color,30,stroke='none',fontColor='#171717',fontStyle='1',rounded='1',arcSize='16')['text_height']=36
    box(f'left_method_{i}',[38,ly,94,lh],'\n'.join(method),'#bdd7ee',27,fontStyle='1')
    ry=ly;rh=lh
    box(f'right_text_{i}',[1082,ry,94,rh],'\n'.join(right[i]),'#bdd7ee',27,fontStyle='1')['text_width']=28
    if i<4:
        bottom=ly+lh;next_y=left[i+1][1]
        for side,cx in [('left',84),('right',1129)]:
            box(f'{side}_stage_step_{i}',[cx-16,bottom+15,32,next_y-bottom-26],'','#203864',stroke='none',shape='singleArrow',direction='south',arrowWidth='0.5',arrowSize='0.14')

frame('framework_cards',[187,181,857,192])
headers=['理论基础','研究背景','核心问题','研究目标','创新点']
details=['文献综述、\n理论梳理与\n概念界定','现状分析、\n问题提出与\n研究意义','关键问题、\n研究假设与\n技术难点','总体目标、\n分阶段目标\n与研究边界','理论创新、\n方法创新与\n应用创新']
for i,x in enumerate([199,370,541,712,883]):
    box(f'framework_header_{i}',[x,189,152,40],headers[i],'#a6e7e3',27,stroke='#3b9690',rounded='1',arcSize='18')['text_height']=33
    box(f'card_front_{i}',[x,257,139,105],'','#d2f3f1',stroke='#245e5a',shape='rectangle')
    poly(f'card_top_{i}',[(x,257),(x+12,245),(x+151,245),(x+139,257)],'#e0f5f3','#245e5a')
    poly(f'card_side_{i}',[(x+139,257),(x+151,245),(x+151,350),(x+139,362)],'#a6d0cb','#245e5a')
    for node in a.nodes[-3:]:
        node['semantic_attributes']=dict(diagramRole='surface',diagramObject=f'prism_card_{i}',overlapReason='同一立体卡片的前顶侧三个原生面；投影包围盒相交，实际多边形仅共享边。')
    label(f'framework_detail_{i}',[x+8,271,123,80],details[i],22)

for i,(x,head,items) in enumerate([(199,'需求调研',['文献梳理','方案设计','可行性分析']),(508,'系统搭建',['数据录入','功能实现','初步测试']),(818,'优化迭代',['性能评估','对比实验','结论整理'])]):
    frame(f'stage_group_{i}',[x-12,471,240,204])
    for j,text in enumerate([head]+items):
        yy=481 if j==0 else 534+(j-1)*45
        box(f'stage_{i}_{j}',[x,yy,217,40],text,'#c8e4b4' if j==0 else '#e4f1d8',27,stroke='#45672e',rounded='1',arcSize='18')['text_height']=33
for i,x in enumerate([425,735]):box(f'stage_iteration_{i}',[x,554,70,32],'','#829871',stroke='none',shape='doubleArrow',arrowWidth='0.45',arrowSize='0.25')

frame('data_group',[188,775,238,207]);frame('model_group',[454,775,590,207])
box('data_header',[199,786,217,40],'数据处理','#fce494',27,stroke='#b68f1c',rounded='1',arcSize='18')['text_height']=33
box('model_header',[573,786,379,40],'模型训练与分析','#fce494',27,stroke='#b68f1c',rounded='1',arcSize='18')['text_height']=33
for i,text in enumerate(['原始数据','特征提取','数据清洗']):box(f'data_{i}',[199,840+i*45,217,40],text,'#fef0ca',27,stroke='#9a7c29',rounded='1',arcSize='18')['text_height']=33
for i,row in enumerate([['模型初始化','参数调优','训练执行'],['验证集评估','误差分析','参数优化'],['结果可视化','对比分析','结论提炼']]):
    for j,text in enumerate(row):box(f'model_{i}_{j}',[466+j*194,840+i*45,182,40],text,'#fef0ca',27,stroke='#9a7c29',rounded='1',arcSize='18')['text_height']=33
box('data_to_model',[426,867,28,34],'','#9a7c29',stroke='none',shape='singleArrow',direction='east',arrowWidth='0.55',arrowSize='0.35')

frame('scenarios',[187,1078,857,341])
for i,(x,title,l,r,decision,out) in enumerate([(208,'场景 A','初始条件','外部约束','模型\n决策','决策输出'),(490,'场景 B','信号数据','规则约束','响应\n决策','执行结果'),(786,'场景 C','状态评估','应对规范','算法\n调度','应急措施')]):
    box(f'scenario_heading_{i}',[x+10,1090,217,40],title,'#f6ccab',27,stroke='#d99968',rounded='1',arcSize='18')['text_height']=33
    for side,xx,text in [('input',x,l),('constraint',x+176,r)]:
        box(f'scenario_{i}_{side}_surface',[xx,1155,58,187],'','#fae4d5',stroke='#884a23',shape='rectangle',rounded='1',absoluteArcSize='1',arcSize='58')['semantic_attributes']=dict(diagramRole='surface',diagramObject=f'scenario_{i}',overlapReason='同一场景决策复合图元，胶囊与中心菱形按参考图交叠；文字使用独立安全区域。')
        label(f'scenario_{i}_{side}',[xx+11,1182,36,132],'\n'.join(text),27)
    poly(f'decision_surface_{i}',[(x+42,1249),(x+113,1175),(x+184,1249),(x+113,1323)],'#fae4d5','#884a23')['semantic_attributes']=dict(diagramRole='surface',diagramObject=f'scenario_{i}',overlapReason='同一场景决策复合图元，中心菱形覆盖两侧胶囊内缘；不豁免文字与连线检查。')
    label(f'decision_{i}',[x+73,1216,80,65],decision,27)
    a.edge(f'decision_output_{i}',[[x+113,1325],[x+113,1364]],'该场景决策形成对应输出')
    box(f'scenario_output_{i}',[x+6,1367,217,39],out,'#fae4d5',27,stroke='#884a23',rounded='1',arcSize='15')['text_height']=33
for i,(start,end) in enumerate([(437,498),(719,794)]):
    a.edge(f'scenario_relation_{i}',[[start,1110],[end,1110]],'相邻场景双向关联，不预设因果机制',True,startArrow='open',startFill='0',endFill='0',strokeWidth='1.5')
    a.edges[-1]['style']['endArrow']='open'

frame('outcome_group',[187,1519,857,199])
box('core_outcome',[213,1531,795,43],'核心研究成果（示例）','#deeaf6',27,rounded='1',arcSize='50')['text_height']=33
a.edge('outcome_trunk',[[610,1576],[610,1588]],'核心成果向五个应用方向分发',False)
a.edge('outcome_bus',[[283,1588],[942,1588]],'五个成果分支的分发母线',False)
for i,(x,text) in enumerate(zip([210,373,538,704,869],['理论贡献','方法创新','实践价值','推广应用','未来展望'])):
    box(f'outcome_{i}',[x,1617,146,90],text,'#deeaf6',27)['text_height']=33
    a.edge(f'outcome_branch_{i}',[[x+73,1588],[x+73,1615]],'对应本项成果方向')

a.save('五个彩色工作包按阶段推进：整体框架、双向关联的三阶段、数据到模型分析、三个相互关联场景及五分支成果。左右分别为独立向下的研究方法链和研究阶段链；不使用ref-04的向内箭头侧栏。首带保留五个立体卡片，场景输入与约束围绕菱形决策，不能解释成串行条目。与ref-04存在相同结构族但侧链、配色和成果节点设计不同，独立ID与配置调用。',
'画布1206×1743；中栏x176–1058，五带y108–384/395–686/700–995/1007–1433/1446–1729；左右栏分别x38–132及1082–1176，均含四支向下实心块箭头。五立体卡片步长171，阶段列x199/508/818，模型网格步长194。ref-19候选框/色采样见measurement.json；同族框线按原图描边校正至统一栅格，弧度与曲线存在近似。',
'前一简化初稿已退回rejected-drafts/ref19-simplified，不采用其坐标或语义；现重建全部卡片面、胶囊、菱形、双向箭头和母线。水印不复刻。标题条沿用原参考色系但改深色文字，改善灰度可读性；底部可见示例标记，参考文案不是赛题事实。场景胶囊与菱形为同对象原生表面有意交叠，文字使用独立安全区。固定五带和三场景，实测例图与容量边界必须实际渲染复查，不能凭脚本执行宣称完成。')
