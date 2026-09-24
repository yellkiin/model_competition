"""Render fixed, independently measured native draw.io templates.

The layout belongs to the selected template; all displayed text belongs to the
caller JSON. No raster image or text-outline conversion is used.
"""
from __future__ import annotations
import argparse
import html
import json
import math
from pathlib import Path
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET

SKILL_ROOT=Path(__file__).resolve().parents[1]

def width_units(text):
    return sum(0 if unicodedata.combining(c) else 1 if unicodedata.east_asian_width(c) in 'WFA' else .5 for c in text)

def normalize(value, key):
    if isinstance(value,list) and all(isinstance(x,str) for x in value):value='\n'.join(value)
    if not isinstance(value,str) or not value.strip():raise ValueError(f'texts.{key}: 须为非空字符串或字符串数组')
    if any(ord(c)<32 and c!='\n' for c in value):raise ValueError(f'texts.{key}: 不允许控制字符或制表符')
    return value

def load_and_validate(template_id,content):
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',template_id):raise ValueError('非法 template_id')
    layout=json.loads((SKILL_ROOT/'assets'/template_id/'layout.json').read_text(encoding='utf8'))
    if not isinstance(content,dict) or set(content)!={'template_id','texts'}:raise ValueError('配置须且仅须包含 template_id、texts')
    if content['template_id']!=template_id:raise ValueError(f'template_id: 本入口只接受 {template_id}')
    if not isinstance(content['texts'],dict):raise ValueError('texts 须为字段对象')
    fields={n['id']:n for n in layout['nodes'] if n.get('text_slot')}
    actual=set(content['texts']);expected=set(fields)
    if actual!=expected:raise ValueError(f'texts 字段/固定节点数量不符；缺少 {sorted(expected-actual)}；多余 {sorted(actual-expected)}')
    values={}
    for key,node in fields.items():
        value=normalize(content['texts'][key],key)
        lines=value.split('\n');font=node['font_size'];w,h=node['bbox'][2:]
        horizontal_limit=node.get('text_width',w-8)
        vertical_limit=node.get('text_height',h)
        for i,line in enumerate(lines,1):
            estimated=width_units(line)*font
            if estimated>horizontal_limit+.01:raise ValueError(f'texts.{key} 第{i}行: 宽{estimated:.1f}px > {horizontal_limit:.1f}px；约{math.floor(horizontal_limit/font)}个全角字，请手动断行')
        line_height=max(font+3,1.2*font)
        if len(lines)*line_height>vertical_limit+.01:raise ValueError(f'texts.{key}: {len(lines)}行超过槽位高度，最多{math.floor(vertical_limit/line_height)}行')
        values[key]=value
    return layout,values

def render(template_id,content):
    layout,texts=load_and_validate(template_id,content)
    mxfile=ET.Element('mxfile',host='app.diagrams.net',agent='scibox-diagram',version='24.7.17',pages='1')
    diagram=ET.SubElement(mxfile,'diagram',id=template_id,name=layout['name'])
    w,h=layout['canvas'];model=ET.SubElement(diagram,'mxGraphModel',pageWidth=str(w),pageHeight=str(h),page='1',pageScale='1',grid='0',math='0',shadow='0')
    root=ET.SubElement(model,'root');ET.SubElement(root,'mxCell',id='0');ET.SubElement(root,'mxCell',id='1',parent='0')
    background=ET.SubElement(root,'mxCell',id='canvas_background',value='',vertex='1',parent='1',style='fillColor=#ffffff;strokeColor=none;')
    ET.SubElement(background,'mxGeometry',x='0',y='0',width=str(w),height=str(h),attrib={'as':'geometry'})
    used={'0','1','canvas_background'}
    def add_id(ident):
        if ident in used:raise ValueError(f'布局重复ID: {ident}')
        used.add(ident)
    # Layout lists are ordered explicitly: containers first, then native objects.
    for node in layout['nodes']:
        key=node['id'];add_id(key)
        style=dict(html='1',whiteSpace='wrap',fontFamily='Microsoft YaHei',fontSize=str(node.get('font_size',20)),
                   fontColor='#171717',align='center',verticalAlign='middle',spacing='0',rounded='0')
        style.update(node['style'])
        value='<br>'.join(html.escape(s,quote=True) for s in texts.get(key,'').split('\n'))
        attrib=dict(id=key,value=value,vertex='1',parent='1',style=';'.join(f'{k}={v}' for k,v in style.items())+';')
        attrib.update(node.get('semantic_attributes',{}))
        cell=ET.SubElement(root,'mxCell',attrib)
        x,y,nw,nh=node['bbox'];ET.SubElement(cell,'mxGeometry',x=str(x),y=str(y),width=str(nw),height=str(nh),attrib={'as':'geometry'})
    for edge in layout['edges']:
        key=edge['id'];add_id(key)
        if not edge.get('meaning'):raise ValueError(f'{key}: 连接缺少语义')
        style=dict(edgeStyle='none',html='1',endArrow='block',endFill='1',endSize='8',strokeWidth='2',strokeColor='#202020')
        style.update(edge.get('style',{}))
        cell=ET.SubElement(root,'mxCell',id=key,value='',edge='1',parent='1',style=';'.join(f'{k}={v}' for k,v in style.items())+';')
        geo=ET.SubElement(cell,'mxGeometry',relative='1',attrib={'as':'geometry'})
        points=edge['points']
        for point,role in [(points[0],'sourcePoint'),(points[-1],'targetPoint')]:ET.SubElement(geo,'mxPoint',x=str(point[0]),y=str(point[1]),attrib={'as':role})
        if len(points)>2:
            arr=ET.SubElement(geo,'Array',attrib={'as':'points'})
            for point in points[1:-1]:ET.SubElement(arr,'mxPoint',x=str(point[0]),y=str(point[1]))
    ET.indent(mxfile,space='  ')
    return ET.tostring(mxfile,encoding='unicode',xml_declaration=True)+'\n'

def main(template_id):
    ap=argparse.ArgumentParser(description=f'{template_id} 独立可编辑模板')
    ap.add_argument('content',type=Path);ap.add_argument('-o','--output',type=Path);ap.add_argument('--check',action='store_true')
    args=ap.parse_args()
    if not args.check and not args.output:ap.error('生成时须指定 -o；仅校验使用 --check')
    try:
        content=json.loads(args.content.read_text(encoding='utf-8-sig'))
        xml=render(template_id,content)
        if not args.check:
            args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(xml,encoding='utf8')
        print(f'{template_id}: '+('配置校验通过' if args.check else str(args.output)))
    except (ValueError,KeyError,OSError,TypeError) as exc:
        print(str(exc),file=sys.stderr);raise SystemExit(2)
