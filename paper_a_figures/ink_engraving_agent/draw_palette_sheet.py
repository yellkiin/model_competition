"""Editable palette/line guide, built locally from the same tokens as the diagram."""
from pathlib import Path
import sys
import xml.etree.ElementTree as E
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from paper_a_figures.ink_engraving_agent.style import palette, wash
S='http://www.w3.org/2000/svg';E.register_namespace('',S)

def el(p,tag,**a):return E.SubElement(p,'{'+S+'}'+tag,{k.replace('_','-'):str(v) for k,v in a.items()})
def text(p,x,y,s,size=24,**a):
    e=el(p,'text',x=x,y=y,font_size=size,**a);e.text=s;return e

def draw(path):
    r=E.Element('{'+S+'}svg',{'width':'360mm','height':'245mm','viewBox':'0 0 1800 1225'})
    st=el(r,'style');st.text="text{font-family:'Noto Sans CJK SC','Microsoft YaHei',sans-serif;fill:#202724}path{stroke-linecap:round;stroke-linejoin:round}"
    el(r,'rect',width=1800,height=1225,fill='white')
    el(r,'path',d='M65 54H1735',stroke='#202724',stroke_width=2)
    text(r,70,127,'线刻设色 · 论文图件共同语言',44,font_weight=700)
    text(r,70,179,'黑白轮廓与细排线不变；同一篇论文固定一套角色配色，不逐图重新抽色。',24,fill='#535E59')
    for i,name in enumerate(['qinglu','qianjiang','yanlan','mono']):
        p=palette(name);y=269+i*206
        text(r,70,y,p['name'],32,font_weight=700)
        text(r,70,y+43,'默认推荐' if i==0 else ('黑白打印' if i==3 else '整篇替代方案'),21,fill=p['muted'])
        for j,(role,label) in enumerate([('structure','结构／状态'),('memory','驻留／搬运'),('fifo','FIFO／读窗口')]):
            x=480+j*410
            g=el(r,'g',id=f'{name}-{role}')
            el(g,'rect',x=x,y=y-33,width=330,height=53,fill=wash(p[role],.16),stroke=p[role],stroke_width=1.4)
            el(g,'path',d=f'M{x+14} {y+13} L{x+43} {y-17} M{x+24} {y+13} L{x+53} {y-17}',stroke=p[role],stroke_width=.7)
            el(g,'path',d=f'M{x+90} {y-6}H{x+244}',stroke=p[role],stroke_width=2.8)
            el(g,'path',d=f'M{x+236} {y-12}L{x+247} {y-6}L{x+236} {y}',fill='none',stroke=p[role],stroke_width=1.8)
            el(g,'circle',cx=x+73,cy=y-6,r=11,fill='white',stroke=p[role],stroke_width=2)
            el(g,'rect',x=x+260,y=y-18,width=26,height=24,fill=p[role])
            text(g,x,y+61,label,24);text(g,x,y+99,p[role],21,fill=p['muted'])
        el(r,'path',d=f'M65 {y+139}H1735',stroke='#CFD4D0',stroke_width=1)
    text(r,70,1139,'主流程 2.8 · 反馈 2.1 · 模块内 1.8 · 轮廓 2.0 · 细排线 0.85（SVG单位）',23)
    text(r,70,1184,'流程图、折线、散点、柱图与热图共享墨色、字体和角色表；数据与科学含义保持原样。',23,fill='#535E59')
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);E.ElementTree(r).write(path,encoding='utf8',xml_declaration=True)
    return path

if __name__=='__main__':
    print(draw(Path(__file__).with_name('palette_sheet.svg')))
