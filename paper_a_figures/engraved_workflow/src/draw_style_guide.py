#!/usr/bin/env python3
"""Draw the reusable figure vocabulary with the same primitives as the workflow."""
from pathlib import Path
import draw_workflow as w
w.W,w.H=1800,1180
w.D=w.Drawing();w.definitions();d=w.D
with d.group('style-page','黑白线刻图形语法',layer=True):
    d.rect(0,0,1800,1180,'',fill='white',stroke='none')
    d.line(70,65,1730,65,'route')
    d.text(70,139,'黑白线刻 / 图形语法',51,'serif bold')
    d.text(70,191,'共用节点、线条、材质与文字层级；后续图件直接复用 Drawing。',27)
    d.line(70,220,1730,220,'fine')
with d.group('line-grammar','线条与信息层级',layer=True):
    d.text(70,285,'01  线条层级',34,'bold')
    for yy,cl,lab in [(345,'hair','0.85  细部排线 / 曲面描线'),(405,'fine','1.60  依赖边 / 内部结构'),(465,'route','3.00  主流程 / 方向')]:
        d.line(80,yy,300,yy,cl);d.text(340,yy+9,lab,26)
    d.arrow('M80,525H300','dashed');d.text(340,534,'虚线：条件路径与反馈',26)
    d.fibre(80,610,690,610,260,510,480,710,11)
    d.text(80,700,'一条主路径 + 收束曲线；箭头只标一次。',25,'muted')
with d.group('object-grammar','对象与操作对象',layer=True):
    d.text(960,285,'02  对象与操作对象',34,'bold')
    d.tensor(1053,393,'',1.6);d.op(1248,389,'o₁');d.slab(1380,355,180,76,'B',True)
    d.text(1050,491,'张量',27,'','middle');d.text(1250,491,'算子',27,'','middle');d.text(1490,491,'本轮操作对象',27,'','middle')
    d.path('M990,560C1060,519 1450,519 1550,560V638C1450,679 1060,679 990,638Z','boundary')
    d.op(1100,600,'o₂');d.tensor(1260,600,'t₂',1.05);d.op(1430,600,'o₄')
    d.arrow('M1153,600H1230','fine');d.arrow('M1288,600H1375','fine')
    d.text(1275,714,'封闭虚线包络表示一个子图',25,'muted','middle')
with d.group('material-grammar','材质：不用彩色面板区分信息',layer=True):
    d.line(70,750,1730,750,'fine')
    d.text(70,821,'03  材质与黑白对比',34,'bold')
    for x,cls,lab in [(80,'paper','留白'),(274,'hatch','斜排线'),(468,'grid','张量格'),(662,'black','实黑')]:
        d.rect(x,864,140,87,cls);d.text(x+70,993,lab,26,'','middle')
    d.text(80,1050,'白底；不使用阴影滤镜、渐变或外部位图。',24,'muted')
with d.group('type-grammar','文字保留为可编辑text与tspan',layer=True):
    d.text(960,821,'04  文字层级',34,'bold')
    d.text(965,884,'主标题：Noto Serif CJK SC / 59',29,'serif')
    d.text(965,940,'模块：39 / 31；说明：24–28',27)
    d.text(965,997,'ℰ_q(G, x; θ)  →  (C_q, D_q)',35,'math')
    d.text(965,1050,'数学下标使用 tspan；正文不转轮廓。',24,'muted')
d.line(70,1110,1730,1110,'fine');d.text(70,1148,'线宽与字号以上述 3000 × 2120 母版坐标为准；只在关键对象上使用实黑。',22,'muted')
d.add('</svg>')
s='\n'.join(d.parts).replace('width="420mm" height="296.8mm"','width="300mm" height="196.667mm"')
s=s.replace('计算图调度的联合优化：联合决策—统一执行—多邻域迭代改进','黑白线刻图形语法与可编辑组件')
out=Path(__file__).resolve().parents[1]/'assets/style_guide.svg';out.write_text(s+'\n',encoding='utf-8');print(out)
