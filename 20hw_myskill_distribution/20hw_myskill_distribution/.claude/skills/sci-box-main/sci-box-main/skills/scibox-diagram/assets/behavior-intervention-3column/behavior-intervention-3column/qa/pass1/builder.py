"""Ref-16: four-stage, three-column behavior/intervention research framework."""
from authoring_support import Author
import base64, math, urllib.parse, zlib

a=Author('behavior-intervention-3column','ref-16','行为机制与干预研究四阶段三栏框架图')
BLUE='#bad0e4';NAVY='#1a4775';GREEN='#235431';PALE='#d1e6c8';PURPLE='#ad9bd2';LIGHT='#e4daf1';YELLOW='#fae8a3'
def box(k,bb,text='',fill='none',fs=24,stroke='none',**style):return a.box(k,bb,text,fill,font=fs,stroke=stroke,**style)
def rect(k,bb,text,fill,fs=24,rounded=False,**style):return box(k,bb,text,fill,fs,'#171717',rounded='1' if rounded else '0',arcSize='22',**style)
def measured(k,i,t,fill=None,fs=24,rounded=False,**style):
    m=a.measure['boxes'][i];x,y,w,h=m['bbox'];return rect(k,[x-1,y-1,w+2,h+2],t,fill or m['fill'],fs,rounded,**style)
def edge(k,pts,meaning,arrow=True,**style):
    defaults=dict(strokeColor='#111111',strokeWidth='2',rounded='0');defaults.update(style)
    a.edge(k,pts,meaning,arrow,**defaults)
def frame(k,bb,rounded=False):
    x,y,w,h=bb
    if rounded:
        r=20;pts=[[x+r,y],[x+w-r,y]]
        for cx,cy,start in [(x+w-r,y+r,-90),(x+w-r,y+h-r,0),(x+r,y+h-r,90),(x+r,y+r,180)]:
            for j in range(9):
                t=math.radians(start+90*j/8);pts.append([round(cx+r*math.cos(t),2),round(cy+r*math.sin(t),2)])
        pts.append(pts[0])
    else:pts=[[x,y],[x+w,y],[x+w,y+h],[x,y+h],[x,y]]
    edge(k,pts,'阶段分区外框，不表示任务流',False,dashed='1',dashPattern='3 2')
def native(k,bb,path,fill,stroke='#171717',sw=2):
    w,h=bb[2:];action='stroke' if fill=='none' else 'fillstroke'
    xml=f'<shape w="{w}" h="{h}"><foreground><strokecolor color="{stroke}"/><strokewidth width="{sw}"/><path>{path}</path><{action}/></foreground></shape>'
    co=zlib.compressobj(wbits=-15);raw=urllib.parse.quote(xml,safe="~()*!.'-").encode()
    return box(k,bb,fill=fill,shape='stencil('+base64.b64encode(co.compress(raw)+co.flush()).decode()+')')
def poly(k,pts,fill,stroke='#171717'):
    xs,ys=zip(*pts);x,y=min(xs),min(ys);w,h=max(xs)-x,max(ys)-y
    path=''.join(f'<{"move" if i==0 else "line"} x="{xx-x}" y="{yy-y}"/>' for i,(xx,yy) in enumerate(pts))+'<close/>'
    return native(k,[x,y,w,h],path,fill,stroke)
def right_arrow(k,x,y,fill=GREEN):
    poly(k,[(x,y+6),(x+23,y+6),(x+23,y),(x+37,y+13),(x+23,y+26),(x+23,y+20),(x,y+20)],fill)

for k,idx,t in [('thinking',1,'研究思路'),('content',2,'研究内容'),('methods',0,'研究方法')]:measured(k,idx,t,NAVY,28,fontColor='#ffffff',fontStyle='1')
box('demo_note',[238,1635,722,40],'版式示例：以下内容仅用于模板演示',fs=22,fontColor='#555555')
bands=[(159,211),(416,240),(699,316),(1057,557)]
for i,(y,h) in enumerate(bands):
    frame(f'left_band_{i}',[23,y,185,h]);frame(f'content_band_{i}',[238,y,722,h],True);frame(f'right_band_{i}',[985,y,193,h])
for i,(idx,t) in enumerate([(4,'基于背景'),(9,'提出问题'),(13,'理论搜寻'),(20,'框架构建'),(25,'调查研究'),(31,'数据统计'),(35,'分析问题'),(43,'提出建议')]):measured(f'thinking_{i}',idx,t,BLUE,28)
for i,(idx,t,fill) in enumerate([(5,'文本分析法',BLUE),(14,'文本分析法',BLUE),(24,'问卷调查法','#e5e5e5'),(28,'实验法',BLUE),(40,'逻辑归纳法',BLUE)]):measured(f'method_{i}',idx,t,fill,28)
rect('method_interview',[997,945,168,54],'访谈法',BLUE,28)
for side,cx in [('left',116),('right',1080)]:
    for i,(y,h) in enumerate([(371,44),(657,41),(1016,40)]):
        poly(f'{side}_down_{i}',[(cx-12,y),(cx+12,y),(cx+12,y+h-22),(cx+24,y+h-22),(cx,y+h),(cx-24,y+h-22),(cx-12,y+h-22)],'#8b9fab','#8b9fab')

measured('digital_context',3,'数字技术发展','#177676',24,True,fontColor='#ffffff',fontStyle='1')
rect('usage_context',[651,177,174,52],'网络成瘾频发','#177676',24,True,fontColor='#ffffff',fontStyle='1')
for i,(idx,t) in enumerate([(6,'大学生网络\n使用现状如何？'),(7,'大学生过度\n使用为何发生？'),(8,'大学生网络\n使用如何干预？')]):measured(f'question_{i}',idx,t,'#b9e6e5',22,True)
for i,x in enumerate([479,738]):edge(f'context_stem_{i}',[[x,230],[x,256]],'研究背景进入共同问题母线',False)
edge('questions_bus',[[360,256],[839,256]],'共同背景对应三个研究问题',False)
for i,x in enumerate([360,599,839]):edge(f'question_drop_{i}',[[x,256],[x,284]],'背景引出一个并列研究问题')

# The three theories share two narrow native ribbons; left ribbon turns down.
for i,x in enumerate([482,713]):
    for j,y in enumerate([453,466]):poly(f'theory_ribbon_{i}_{j}',[(x,y),(x+30,y),(x+30,y+7),(x,y+7)],GREEN)
native('theory_to_framework_curve',[247,459,34,124],'<move x="31" y="0"/><curve x1="-4" y1="0" x2="-4" y2="93" x3="23" y3="111"/><line x="22" y="105"/><line x="33" y="116"/><line x="22" y="124"/><line x="24" y="117"/><curve x1="-10" y1="99" x2="-8" y2="-1" x3="31" y3="5"/><close/>','#73967b')
for i,(idx,t) in enumerate([(10,'行为主义理论'),(11,'使用与满足理论'),(12,'社会认知理论')]):measured(f'theory_{i}',idx,t,GREEN,24,True,fontColor='#ffffff',fontStyle='1')
for i,bb in enumerate([[278,519,669,111],[285,526,655,97]]):
    x,y,w,h=bb
    edge(f'framework_frame_{i}',[[x,y],[x+w,y],[x+w,y+h],[x,y+h],[x,y]],'三步框架的双层组合边界',False)
for i,(idx,t) in enumerate([(18,'①大学生网络\n使用的行为特征'),(17,'②大学生过度\n使用的影响机制'),(19,'③大学生网络\n使用的应对策略')]):measured(f'framework_{i}',idx,t,PALE,22)
right_arrow('framework_step_0',482,560);right_arrow('framework_step_1',708,560)

research=[('问卷发放','设计并发放大学生网络使用调查问卷'),('机制分析','验证过度使用行为的影响因素及作用路径'),('干预研究','设计干预方案，进行网络使用行为试验'),('个别访谈','选择个别样本对于干预状况进行访谈')]
for i,(y,(title,content)) in enumerate(zip([718,793,868,945],research)):
    rect(f'research_title_{i}',[259,y,150,51],title,PURPLE,24,True,fontColor='#ffffff',fontStyle='1')
    rect(f'research_detail_{i}',[458,y,474,51],content,LIGHT,22,True)
    right_arrow(f'research_step_{i}',416,y+9,'#604786')
    if i<3:edge(f'research_sequence_{i}',[[334,y+52],[334,[793,868,945][i]-1]],'左列调查、分析、干预、访谈的顺序衔接，原图无箭尖',False)

rect('synthesis',[494,1077,210,51],'综合分析','#e39634',24,True,fontColor='#ffffff',fontStyle='1')
native('synthesis_brace',[247,1134,700,36],'<move x="0" y="36"/><quad x1="2" y1="22" x2="20" y2="22"/><line x="328" y="22"/><quad x1="350" y1="22" x2="350" y2="0"/><quad x1="350" y1="22" x2="372" y2="22"/><line x="680" y="22"/><quad x1="697" y1="22" x2="700" y2="36"/>','none')
for i,(bb,t) in enumerate([([247,1177,246,65],'总结网络使用的\n行为模式、成因机制'),([509,1177,245,65],'基于理论与实证结\n果进行系统分析'),([772,1177,178,65],'与相关文献进\n行对比分析')]):rect(f'analysis_{i}',bb,t,YELLOW,22,True)
for i,x in enumerate([370,631,861]):edge(f'analysis_join_{i}',[[x,1243],[x,1275]],'三项综合分析汇入成果与应用的共同母线',False)
edge('analysis_output_bus',[[370,1275],[861,1275]],'共同分析汇入两个成果输出',False)
for i,(cx,bb,t,detailbb,detail) in enumerate([(423,[351,1309,145,51],'成果发表',[258,1390,332,72],'以研究报告和学术论文形式\n投稿相关期刊'),(775,[703,1309,145,51],'策略应用',[610,1390,331,72],'应用于大学生网络使用指导\n与行为干预')]):
    edge(f'output_drop_{i}',[[cx,1275],[cx,1308]],'三项分析对应成果发表或策略应用')
    rect(f'output_{i}',bb,t,YELLOW,22,True)
    edge(f'output_detail_drop_{i}',[[cx,1361],[cx,1389]],'输出类别细化为可执行安排')
    rect(f'output_detail_{i}',detailbb,detail,YELLOW,22,True)
    edge(f'final_join_{i}',[[cx,1463],[cx,1493]],'两个输出路径汇入末端总结',False)
edge('final_bus',[[423,1493],[775,1493]],'两个输出路径共同汇流',False)
edge('final_drop',[[599,1493],[599,1521]],'汇流进入最后学术表达节点')
rect('final_output',[258,1523,683,65],'以学术论文形式发表至相关期刊','#f8d67c',24,True)

a.save('三栏对应研究思路、研究内容、研究方法，四阶段分别为背景与三个问题、三类理论与三步框架、四项调查/干预工作、三项综合分析到双输出及末端汇流。保留三理论之间的双细带、左侧下弯曲箭头、综合分析大括号与左右两列阶段箭头。',
'画布1206×1743；左列x23..208，中列x238..960，右列x985..1178；阶段y159/416/699/1057；色框候选坐标来自calibration/ref-16.json，缺失合并框按原图连续边界补齐；顶端母线y256，成果母线y1275及1493。',
'全部主要元素为原生可编辑mxGraph。原图多处XXXXX占位替换为明确网络使用行为研究演示文案，底部增示例说明；不当作真实赛题事实或成果。原末端将策略应用也汇入学术发表节点的关系保留，仅适用于确实有此报告汇总关系的任务。理论双带与弯曲箭头用原生路径近似，字体、圆角与水印省略存在差异。固定四阶段及三/四/三/二的内部数量，支持字段容量内替换，不任意增加节点。')
