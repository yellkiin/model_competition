#!/usr/bin/env python3
"""Figure 1.1, version 3: reuse ink_v2 engraving, redraw the conceptual flow.

Only reads ink_v2 vector assets. Does not use other figure PRs, execute a solver,
embed bitmaps/fonts, or edit the second version. Python 3.10+; Inkscape for export.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
import gzip
import json
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
SVG = 'http://www.w3.org/2000/svg'
INK = 'http://www.inkscape.org/namespaces/inkscape'
ET.register_namespace('', SVG)
ET.register_namespace('inkscape', INK)
NS = {'s': SVG}
BASE_COMMIT = '70d4888886cd9f77037f7b010ce0241349ef056d'
PALETTES = ('mono', 'qinglu', 'qianjiang', 'yanlan')

def tag(s): return '{' + SVG + '}' + s

def element(parent, kind, **a):
    return ET.SubElement(parent, tag(kind), {k.replace('_', '-'): str(v) for k, v in a.items()})

def text(parent, x, y, value, size=28, cls='', anchor='start', ident=None):
    e = element(parent, 'text', x=x, y=y, font_size=size, text_anchor=anchor, **{'class': cls})
    if ident: e.set('id', ident)
    e.text = value
    return e

def group(root, ident, title, transform=None):
    e = element(root, 'g', id=ident)
    e.set('{'+INK+'}groupmode', 'layer')
    e.set('{'+INK+'}label', title)
    if transform: e.set('transform', transform)
    element(e, 'title').text = title
    return e

def find(root, ident):
    e = root.find('.//*[@id="'+ident+'"]')
    if e is None: raise ValueError('Missing ink_v2 object: '+ident)
    return e

def change(g, ident, value=None, **attrs):
    e = find(g, ident)
    if value is not None:
        for c in list(e): e.remove(c)
        e.text = value
    for k,v in attrs.items(): e.set(k.replace('_','-'), str(v))
    return e

def omit(g, ids):
    for parent in g.iter():
        for e in list(parent):
            if e.get('id') in ids: parent.remove(e)

def arrow(parent, ident, source, target, d, feedback=False):
    e = element(parent, 'path', id=ident, d=d, **{'class': 'concept-feedback' if feedback else 'concept-main',
        'marker-end': 'url(#concept-feedback-arrow)' if feedback else 'url(#concept-arrow)',
        'data-source':source,'data-target':target})
    return e

def local_arrow(parent, d):
    return element(parent, 'path', d=d, **{'class':'fine', 'marker-end':'url(#arrow)'})

def panel_heading(g, x, number, title_, subtitle):
    text(g,x,285,number,43,'serif')
    text(g,x+83,285,title_,43,'bold')
    text(g,x+83,327,subtitle,27,'muted')

def bevel(parent,x,y,w,h,ident,role='structure'):
    g=element(parent,'g',id=ident)
    element(g,'path',d=f'M{x},{y} l12,-12 h{w} l-12,12 Z',**{'class':'hatch'})
    element(g,'path',d=f'M{x+w},{y} l12,-12 v{h} l-12,12 Z',**{'class':'hatch'})
    element(g,'rect',x=x,y=y,width=w,height=h,**{'class':'paper wash-'+role})
    return g

def render(name, source_dir, out_dir):
    src=Path(source_dir)/f'workflow_{name}.svg'
    master=ET.parse(src).getroot()
    root=ET.Element(tag('svg'),{'width':'420mm','height':'255.5mm','viewBox':'0 0 3000 1825',
        'role':'img','aria-labelledby':'title desc','data-version':'ink_v3','data-input-version':'ink_v2'})
    element(root,'title',id='title').text='图1.1 计算图调度的联合优化：联合决策、多邻域协同与统一执行评价'
    element(root,'desc',id='desc').text=('由第二版原始矢量重组的第三版。主阅读方向从左至右：当前方案、完整候选、统一执行评价；'
        '评价反馈回到当前方案，停止时输出最好可行方案。底部无图例、无字典序判定菱形。六算子图和硬件为示意。')
    defs=deepcopy(master.find('s:defs',NS));root.append(defs)
    old_main=find(defs,'ink-main-arrow').find('s:path',NS).get('fill')
    old_feedback=find(defs,'ink-feedback-arrow').find('s:path',NS).get('fill')
    for ident,col in [('concept-arrow',old_main),('concept-feedback-arrow',old_feedback)]:
        m=element(defs,'marker',id=ident,viewBox='0 0 24 24',markerWidth=24,markerHeight=24,
                  refX=22,refY=12,orient='auto',markerUnits='userSpaceOnUse')
        element(m,'path',d='M2,2 L22,12 L2,22 L6.8,12 Z',fill=col,stroke='none')
    element(defs,'style').text=f'''
.concept-main {{fill:none;stroke:{old_main};stroke-width:4.0;stroke-linejoin:round;stroke-linecap:round;}}
.concept-feedback {{fill:none;stroke:{old_feedback};stroke-width:3.1;stroke-linejoin:round;stroke-linecap:round;}}
.card-rule {{fill:none;stroke:{old_main};stroke-width:1.8;}}
.panel-divider {{fill:none;stroke:{old_main};stroke-width:1;opacity:.16;}}
.v3-notes {{font-size:27px;}}
'''
    page=group(root,'page-v3','版面与标题')
    element(page,'rect',x=0,y=0,width=3000,height=1825,fill='white',stroke='none')
    element(page,'path',d='M88,54H2918',**{'class':'route'})
    text(page,90,137,'计算图调度的联合优化',60,'serif bold',ident='figure-title')
    text(page,92,192,'联合决策 · 多邻域协同 · 统一执行评价',31,ident='figure-subtitle')
    text(page,2915,133,'图 1.1  ·  方法总览',29,'serif muted','end')
    element(page,'path',d='M90,224H2916',**{'class':'fine'})
    for x in (981,2023):
        element(page,'path',d=f'M{x},351V1301',**{'class':'panel-divider'})

    # 01: reuse exact bipartite graph and engraved task/core strips.
    left=group(root,'joint-decision-v3','01 联合决策')
    panel_heading(left,88,'01','联合决策','子图划分 · 核心映射 · 核内顺序')
    text(left,92,380,'输入：计算图、硬件配置与搜索预算',28,'muted')
    graph=deepcopy(find(master,'bipartite-example'));left.append(graph)
    graph.set('transform','translate(116,435) scale(.91)')
    text(left,92,929,'𝒫 = {A, B, C, D}',34,'math',ident='partition-expression')
    text(left,914,929,'原始算子与依赖保持不变',26,'muted','end')
    rails=element(left,'g',id='core-assignment-v3',transform='translate(0,-40)')
    original=find(master,'joint-decision')
    for e in list(original)[10:44]: rails.append(deepcopy(e))
    text(left,883,1300,'核心映射 a  ·  核内顺序 π',28,'math muted','end')

    # 02: four original illustrations are preserved; captions are shortened.
    mid=group(root,'neighborhoods-v3','02 多邻域协同')
    panel_heading(mid,1030,'02','多邻域协同','共享当前方案，探索互补改进')
    element(mid,'rect',x=1050,y=357,width=910,height=96,rx=5,fill='white',stroke=old_feedback,stroke_width=1.5)
    text(mid,1505,396,'依据收益与成本分配搜索机会',34,'bold','middle',ident='selection-principle')
    text(mid,1505,435,'每轮选择一个来源',27,'muted','middle')
    local_arrow(mid,'M1505,454V478')
    for ident in ('source-base','source-structure','source-residency','source-fifo'):
        g=deepcopy(find(master,ident));g.set('transform','translate(0,-36)');mid.append(g)
        for e in g.iter(tag('text')):
            if e.get('font-size') and float(e.get('font-size'))<25:e.set('font-size','25')
    base=find(mid,'source-base')
    change(base,'text-047','拓扑排序 · 分组粒度',font_size=27)
    change(base,'text-054','形成初始候选',font_size=27)
    structure=find(mid,'source-structure')
    change(structure,'text-056','结构与负载',font_size=31)
    change(structure,'text-057','迁移 · 交换 · 切分',font_size=27)
    residency=find(mid,'source-residency')
    change(residency,'text-068','数据驻留',font_size=31)
    change(residency,'text-069','调整分组与顺序',font_size=27)
    change(residency,'text-082','缩短同时驻留区间',font_size=27)
    fifo=find(mid,'source-fifo')
    change(fifo,'text-084','FIFO 复用时序 · Q3',font_size=30)
    change(fifo,'text-085','保持划分与归核，仅调整顺序',font_size=26)
    change(fifo,'text-091','将读取移入驻留窗口',font_size=27,y=1318)
    omit(fifo,{'text-092'})
    element(mid,'path',d='M1050,883H1960',**{'class':'faint'})

    # 03: retain the engraved two-core execution cutaway; move detail to prose.
    right=group(root,'execution-v3','03 统一执行评价')
    panel_heading(right,2090,'03','统一执行评价','任务 · 存储 · 流水线 · 共享带宽')
    text(right,2090,372,'候选示意：B 迁至 k₂',29,'bold')
    hardware=element(right,'g',id='hardware-cutaway-v3',transform='translate(0,0)')
    for e in list(find(master,'execution'))[6:130]: hardware.append(deepcopy(e))
    change(hardware,'text-124','DDR · 共享带宽',font_size=33)
    change(hardware,'text-125','只读 L2 · FIFO · Q3',font_size=30)
    change(hardware,'text-127','未命中读 DDR',font_size=25)
    change(hardware,'text-128','读完成后填充',font_size=25)
    omit(hardware,{'text-126'})

    # One straight, left-to-right process lane; no long inter-column detours.
    lane=group(root,'main-process-v3','主流程：当前方案 → 完整候选 → 统一评价')
    current=bevel(lane,92,1370,802,106,'current-state-v3')
    text(current,493,1413,'当前最好可行方案',33,'bold','middle')
    text(current,493,1456,'x = (𝒫, a, π)',34,'math','middle')
    candidate=bevel(lane,1050,1370,910,106,'candidate-v3')
    text(candidate,1505,1413,'完整候选 y = (𝒫′, a′, π′)',34,'math','middle')
    text(candidate,1505,1456,'可行性与下界筛选',27,'muted','middle')
    objective=bevel(lane,2090,1370,815,106,'objective-v3')
    text(objective,2497,1412,'总体任务执行时间（Makespan）',31,'bold','middle')
    formula=text(objective,2497,1456,'C',36,'math','middle',ident='makespan-v3')
    element(formula,'tspan',baseline_shift='sub',font_size='70%').text='q'
    element(formula,'tspan').text='(y) = max'
    element(formula,'tspan',baseline_shift='sub',font_size='70%').text='j'
    element(formula,'tspan').text=' f'
    element(formula,'tspan',baseline_shift='sub',font_size='70%').text='j'
    arrow(lane,'current-to-candidate','current-state-v3','candidate-v3','M925,1422H1036')
    arrow(lane,'candidate-to-evaluation','candidate-v3','objective-v3','M1988,1422H2075')

    # A single visual return loop and a stop/output branch replace code-level gates.
    feedback=group(root,'feedback-output-v3','评价反馈、迭代与输出')
    node=element(feedback,'g',id='feedback-v3')
    element(node,'rect',x=1070,y=1536,width=890,height=100,rx=4,fill='white',stroke=old_feedback,stroke_width=1.8)
    text(node,1515,1575,'反馈改进',35,'bold','middle')
    text(node,1515,1614,'保留更优方案 · 更新搜索依据',28,'muted','middle')
    arrow(feedback,'evaluation-to-feedback','objective-v3','feedback-v3',
          'M2497,1488V1559Q2497,1586 2470,1586H1972',True)
    arrow(feedback,'feedback-to-current','feedback-v3','current-state-v3',
          'M1057,1586H520Q493,1586 493,1559V1488',True)
    text(feedback,731,1629,'预算内继续迭代',26,'text-structure','middle')
    arrow(feedback,'finish-to-output','feedback-v3','outputs-v3','M1515,1637V1706')
    text(feedback,1550,1682,'停止时',26,'muted')
    out=element(feedback,'g',id='outputs-v3')
    text(out,1515,1754,'输出：调度方案 · 性能指标 · 时间—质量曲线',34,'bold','middle')
    text(out,1515,1796,'Q3：固定同一方案，比较无 L2 / 有 L2',27,'muted','middle')
    dest=Path(out_dir)/'assets';dest.mkdir(parents=True,exist_ok=True)
    file=dest/f'workflow_{name}_v3.svg'
    ET.indent(root,space='  ')
    ET.ElementTree(root).write(file,encoding='utf-8',xml_declaration=True)
    with (dest/f'workflow_{name}_v3.svgz').open('wb') as raw:
        with gzip.GzipFile(fileobj=raw,mode='wb',mtime=0) as compressed:compressed.write(file.read_bytes())
    return file

def export(svg, out_dir, width):
    exe=shutil.which('inkscape')
    if not exe: raise RuntimeError('Editable SVG is ready; install Inkscape to export PDF and PNG.')
    folder=Path(out_dir)/'exports';folder.mkdir(parents=True,exist_ok=True)
    for suffix,opts in [('.pdf',['--export-text-to-path']),('.png',[f'--export-width={width}']),('_preview.png',['--export-width=1800'])]:
        target=folder/(svg.stem+suffix)
        cmd=[exe,str(svg),f'--export-filename={target}','--export-area-page',
             '--export-background=white','--export-background-opacity=1',*opts]
        p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=180)
        if p.returncode:raise RuntimeError(p.stderr)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-dir',type=Path,default=HERE.parent/'ink_v2/assets')
    p.add_argument('--out',type=Path,default=HERE)
    p.add_argument('--palettes',nargs='+',choices=PALETTES,default=['mono','qinglu'])
    p.add_argument('--svg-only',action='store_true');p.add_argument('--png-width',type=int,default=6000)
    a=p.parse_args()
    if a.png_width<1200:p.error('png-width must be at least 1200')
    for name in a.palettes:
        svg=render(name,a.source_dir,a.out)
        if not a.svg_only:export(svg,a.out,a.png_width)
        print(svg)
    report={'version':'ink_v3','source_version':'ink_v2','source_commit':BASE_COMMIT,
        'canvas_viewbox':[0,0,3000,1825],'palettes':a.palettes,'main_inter_module_links':2,
        'feedback_links':2,'output_links':1,'legend_removed':True,'lexicographic_diamond_removed':True,
        'exact_execution_parameters_moved_to_prose':True,'embedded_raster':False,'font_files_embedded':False,
        'new_experiments':0}
    (a.out/'BUILD_INFO.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')

if __name__=='__main__':main()
