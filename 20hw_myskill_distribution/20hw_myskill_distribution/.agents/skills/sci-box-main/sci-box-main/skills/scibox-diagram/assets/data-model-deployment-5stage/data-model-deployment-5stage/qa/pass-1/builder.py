"""Ref-20: measured database/preparation/training/deployment workflow."""
from authoring_support import Author
import base64,zlib,urllib.parse

a=Author('data-model-deployment-5stage','ref-20','数据归集建模与系统落地五阶段流程图')
def box(key,bb,text,fill,font=27,stroke='#191919',**kw):
    return a.box(key,bb,text,fill,font=font,stroke=stroke,**kw)
def label(key,bb,text,font=27,**kw):return box(key,bb,text,'none',font,stroke='none',**kw)
def poly(key,points,fill,stroke='#191919'):
    xs,ys=zip(*points);x,y=min(xs),min(ys);w,h=max(xs)-x,max(ys)-y
    coords=[((xx-x)/w*100,(yy-y)/h*100) for xx,yy in points]
    commands=f'<move x="{coords[0][0]}" y="{coords[0][1]}"/>'+''.join(f'<line x="{xx}" y="{yy}"/>' for xx,yy in coords[1:])+'<close/>'
    xml=f'<shape w="100" h="100" aspect="variable" strokewidth="inherit"><foreground><path>{commands}</path><fillstroke/></foreground></shape>'
    z=zlib.compressobj(wbits=-15);encoded=urllib.parse.quote(xml,safe="~()*!.'-").encode();data=base64.b64encode(z.compress(encoded)+z.flush()).decode()
    return box(key,[x,y,w,h],'',fill,stroke=stroke,shape='stencil('+data+')')
def surface(node,obj,reason):
    node['semantic_attributes']=dict(diagramRole='surface',diagramObject=obj,overlapReason=reason)
def line(key,pts,meaning):a.edge(key,pts,meaning,False)

stages=[(12,410,30,380,'数据源头归集与预处理','#d7e8d1','#46652d'),(463,247,479,211,'数据集成型','#e8dfec','#7030a0'),(754,326,770,290,'模型搭建与训练','#d8e1f5','#203864'),(1120,347,1139,306,'模型优化','#f9d5b8','#843c0c'),(1507,220,1522,192,'成果落地','#ffe699','#806000')]
for i,(y,h,fy,fh,text,fill,stroke) in enumerate(stages):
    a.frame(f'stage_frame_{i}',[18,y,1162,h],True)
    cy=fy+fh/2
    poly(f'flag_{i}',[(37,fy),(112,fy),(112,cy-15),(124,cy-15),(124,cy-30),(153,cy),(124,cy+30),(124,cy+15),(112,cy+15),(112,fy+fh),(37,fy+fh)],fill,stroke)
    node=label(f'flag_text_{i}',[56,fy+18,38,fh-36],'\n'.join(text),28)
    node['text_width']=28
    if i<4:
        bottom=y+h;end=stages[i+1][0]-2
        box(f'stage_down_{i}',[549,bottom+1,92,end-bottom-1],'','#858585',stroke='none',shape='singleArrow',direction='south',arrowWidth='0.50',arrowSize='0.44')

for i,(x,text) in enumerate(zip([183,432,685,936],['工况实测数据库','仿真样本数据库','文献标准数据库','故障案例数据库'])):
    cylinder=box(f'database_{i}',[x,30,225,95],'','#d0e8d2',shape='cylinder3',size='12',boundedLbl='1',backgroundOutline='1')
    surface(cylinder,f'database_{i}','同一数据库圆柱的筒身与浅色顶面，标签位于筒身内。')
    cap=box(f'database_cap_{i}',[x,30,225,24],'','#e3f0e3',shape='ellipse')
    surface(cap,f'database_{i}','圆柱同对象浅色顶面覆盖筒身的顶椭圆。')
    label(f'database_name_{i}',[x+8,65,209,35],text,27)['text_height']=33
    line(f'database_stem_{i}',[[x+112.5,126],[x+112.5,150]],'该数据库接入共享数据归集母线')
line('source_bus',[[295.5,150],[1048.5,150]],'四类数据源共同连接两个处理模块；无单向因果箭头')
for i,(x,title,detail) in enumerate([(183,'多源数据清洗处理','缺失值填充、异常值剔除、\n数据降噪、归一化处理'),(690,'数据特征标注划分','样本标签标定、数据集分层、\n训练 / 验证 / 测试集拆分')]):
    node=box(f'prepare_body_{i}',[x,202,477,201],'','#d2e9e4',shape='rectangle',rounded='1',arcSize='20')
    surface(node,f'prepare_{i}','同一处理模块的正文面板与跨边界标题胶囊，有意叠层且文字留在安全区。')
    cap=box(f'prepare_cap_{i}',[x+82,177,337,73],'','#c6e0d9',shape='rectangle',rounded='1',absoluteArcSize='1',arcSize='73')
    surface(cap,f'prepare_{i}','标题胶囊覆盖同一处理面板的上边界。')
    label(f'prepare_title_{i}',[x+95,192,311,40],title,27)['text_height']=33
    label(f'prepare_detail_{i}',[x+22,272,433,92],detail,27)
    line(f'preparation_branch_{i}',[[x+250.5,150],[x+250.5,175]],'共同数据源进入该处理模块')

# Keep all three editable prisms. Slightly narrower fronts create independent
# visible side faces instead of the source's overlapping neighboring prisms.
prisms=[('结构化数据集构建','整理规整原始数据，\n划分训练 / 验证 /\n测试集'),('特征库矩阵封装','把提取的各类特征封\n装为矩阵格式，适配\n模型输入计算'),('数据脱敏与格式适配','去除涉密敏感信息、\n统一文件格式')]
for i,(x,(title,detail)) in enumerate(zip([183,511,839],prisms)):
    front=box(f'package_front_{i}',[x,534,270,156],'','#e9deed',shape='rectangle')
    top=poly(f'package_top_{i}',[(x,534),(x+52,482),(x+322,482),(x+270,534)],'#eee7f2')
    side=poly(f'package_side_{i}',[(x+270,534),(x+322,482),(x+322,638),(x+270,690)],'#b9b1bd')
    for n in [front,top,side]:surface(n,f'package_{i}','单个立体数据封装模块的前顶侧原生表面，实际多边形共享边；正文与顶面标签独立。')
    label(f'package_title_{i}',[x+48,493,259,33],title,25)['text_height']=30
    label(f'package_detail_{i}',[x+10,560,250,112],detail,26)

for i,(y,text) in enumerate([(778,'模型输\n入模块'),(940,'参数配\n置模块')]):
    box(f'model_input_{i}',[183,y,149,120],text,'#d6e7fa',27,rounded='1',arcSize='30')
    line(f'input_trunk_{i}',[[334,y+60],[357,y+60]],'输入或配置模块连接两个并列分支')
    line(f'input_bus_{i}',[[357,y+28],[357,y+93]],'该模块的二分支母线')
    for j,dy in enumerate([28,93]):line(f'input_branch_{i}_{j}',[[357,y+dy],[382,y+dy]],'模块关联对应特征或配置项')
line('input_config_link',[[257,900],[257,938]],'输入模块与参数模块的配合关系；原图无方向')
for i,(y,text) in enumerate([(778,'特征提取分支1'),(843,'特征提取分支2'),(940,'超参初始化设定'),(1005,'训练策略调控')]):
    box(f'training_branch_{i}',[383,y,295,55],text,'#d6e7fa',27)
    line(f'training_merge_{i}',[[680,y+27],[710,y+27]],'本分支连接核心训练的共同母线')
line('training_bus',[[710,805],[710,1032]],'四项训练输入汇合母线')
line('training_root',[[710,919],[742,919]],'输入特征及参数配置共同用于核心算法模型训练')
box('core_training',[744,806,183,227],'核心算法模\n型训练','#b6c7e8',27)
box('weight_interface',[985,806,183,227],'模型权重文\n件与推理接\n口','#b6c7e8',27)
box('training_interface_relation',[929,902,53,39],'','#335eaa',stroke='none',shape='doubleArrow',arrowWidth='0.48',arrowSize='0.35')

for key,x,text in [('optimization',183,'模型迭代优化'),('evaluation',625,'模型性能评估')]:
    box(key,[x,1140,60,202],'\n'.join(text),'#fdf0e2',27)['text_width']=28
line('optimization_trunk',[[245,1241],[265,1241]],'迭代优化展开为三个并列改进方向')
line('optimization_bus',[[265,1176],[265,1307]],'三项优化方向共享母线')
line('evaluation_bus',[[603,1176],[603,1307]],'三个方向汇入模型性能评估')
line('evaluation_root',[[603,1241],[623,1241]],'三项改进共同接受性能评估')
for i,(y,text) in enumerate([(1148,'精度优化'),(1213,'收敛提速'),(1278,'鲁棒性增强')]):
    box(f'optimization_axis_{i}',[287,y,295,56],text,'#fdf0e2',27)
    line(f'optimization_branch_{i}',[[265,y+28],[285,y+28]],'对应优化方向')
    line(f'evaluation_branch_{i}',[[584,y+28],[603,y+28]],'该方向的性能评估关联')
box('optimization_down',[398,1347,73,33],'','#843c0c',stroke='none',shape='singleArrow',direction='south',arrowWidth='0.58',arrowSize='0.42')
box('model_deployment',[183,1393,502,51],'模型轻量化与算法固化','#f8ceab',27)
box('system_architecture',[812,1140,274,64],'系统总体架构设计','#f8ceab',27,rounded='1',arcSize='30')
for i,(x,text) in enumerate(zip([732,804,878,952,1027,1102],['人机交互界面','数据通讯模块','采集驱动模块','预警判别模块','存储管理模块','输出执行模块'])):
    box(f'system_module_{i}',[x,1241,59,203],'\n'.join(text),'#fdf0e2',27)['text_width']=28
    line(f'architecture_branch_{i}',[[949,1206],[x+29.5,1239]],'总体架构分为该功能模块；保留原图六条无箭头斜分支')

box('integration',[455,1522,442,65],'系统集成联调与整体验证','#feedb1',27,rounded='1',arcSize='30')
line('integration_trunk',[[676,1589],[676,1614]],'整体验证关联四种落地与总结活动')
line('integration_bus',[[286,1614],[1048,1614]],'四种活动共享母线')
for i,(x,text) in enumerate(zip([175,430,686,937],['仿真试验验证','实物样机测试','工程现场试运行','成果总结'])):
    box(f'implementation_{i}',[x,1644,224,69],text,'#fbf2cf',27)
    line(f'implementation_branch_{i}',[[x+112,1614],[x+112,1642]],'验证与落地活动并列关联，无额外因果方向')

a.save('五阶段数据到模型及系统落地路线：四数据库共同连接清洗与标注两个面板；三立体数据封装块；双输入各二分支汇入核心训练并与推理接口双向关联；三项优化与性能评估相连，右侧六模块架构并列展开；最终集成联调分出四项落地活动。阶段之间使用灰色向下箭头，内部黑色无箭头关联不改成单向流程。',
'画布1206×1743。实测五个虚线框x18–1180，y12–422/463–710/754–1080/1120–1467/1507–1727。数据库与正文矩形来自measurement.json。三立体模块正面宽由原约294调整为270，深度52保留，起点x183/511/839，清楚保留各模块侧面并避免相邻遮挡；其余模块沿实测栅格。各平行框数量固定，所有文字独立JSON字段。',
'完整保留四圆柱数据库、三块立体封装、所有分支与共享母线、双向接口箭头和六条架构斜线。三块立体封装稍缩正面并调整步距，是明确的可读性适配，不能称像素一致；原“归一化归一处理”重复文字规范为演示文案“归一化处理”。不复刻水印。参考流程为教学示例，训练/验证拆分必须按真实赛题避免泄漏，不能由本模板推断已完成计算。实际渲染与印刷尺寸尚待复查。')
