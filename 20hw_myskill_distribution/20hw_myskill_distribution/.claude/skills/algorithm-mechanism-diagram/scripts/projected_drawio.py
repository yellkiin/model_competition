"""Editable draw.io primitives with explicit projected geometry; no model facts invented."""
from pathlib import Path
import xml.etree.ElementTree as E
import base64,zlib

class Drawing:
    def __init__(self,width=960,height=480):
        self.xml=E.Element('mxfile',host='app.diagrams.net')
        d=E.SubElement(self.xml,'diagram',id='diagram',name='结构图')
        m=E.SubElement(d,'mxGraphModel',pageWidth=str(width),pageHeight=str(height),page='1',math='0')
        self.root=E.SubElement(m,'root')
        E.SubElement(self.root,'mxCell',id='0');E.SubElement(self.root,'mxCell',id='1',parent='0')
    def vertex(self,id,x,y,w,h,text='',style='',**attrs):
        c=E.SubElement(self.root,'mxCell',id=id,value=text,vertex='1',parent='1',
            style='fontFamily=Microsoft YaHei;fontSize=18;fontColor=#23384d;html=0;whiteSpace=wrap;'+style,**attrs)
        E.SubElement(c,'mxGeometry',x=str(x),y=str(y),width=str(w),height=str(h),attrib={'as':'geometry'})
    def text(self,id,x,y,w,h,text,fs=18):
        self.vertex(id,x,y,w,h,text,f'text;fillColor=none;strokeColor=none;align=center;fontSize={fs};')
    def edge(self,id,points,dashed=False,color='#315879',arrow=True):
        c=E.SubElement(self.root,'mxCell',id=id,edge='1',parent='1',style=f'edgeStyle=none;strokeColor={color};strokeWidth=1.7;endArrow={"block" if arrow else "none"};endSize=6;dashed={int(dashed)};')
        g=E.SubElement(c,'mxGeometry',relative='1',attrib={'as':'geometry'})
        for pt,key in [(points[0],'sourcePoint'),(points[-1],'targetPoint')]:
            E.SubElement(g,'mxPoint',x=str(pt[0]),y=str(pt[1]),attrib={'as':key})
        arr=E.SubElement(g,'Array',attrib={'as':'points'})
        for pt in points[1:-1]:E.SubElement(arr,'mxPoint',x=str(pt[0]),y=str(pt[1]))
    def polygon(self,id,points,color,obj):
        x=min(p[0] for p in points);y=min(p[1] for p in points)
        w=max(p[0] for p in points)-x;h=max(p[1] for p in points)-y
        shape=E.Element('shape',name=id,w='100',h='100',aspect='variable',strokewidth='inherit')
        bg=E.SubElement(shape,'background');path=E.SubElement(bg,'path')
        for i,(px,py) in enumerate(points):E.SubElement(path,'move' if i==0 else 'line',x=str((px-x)/w*100),y=str((py-y)/h*100))
        E.SubElement(path,'close');fg=E.SubElement(shape,'foreground');E.SubElement(fg,'fillstroke')
        compressed=zlib.compress(E.tostring(shape,encoding='utf8'))[2:-4]
        stencil=base64.b64encode(compressed).decode()
        self.vertex(id,x,y,w,h,style=f'shape=stencil({stencil});fillColor={color};strokeColor=#53748b;opacity=78;',
                     diagramObject=obj,diagramRole='surface',overlapReason='同一特征张量的前顶侧表面与连续叠片，刻意展示深度层次')
    def slab(self,id,x,y,w,h,depth=14,color='#bedcf0',object_id=None):
        dx,dy=depth,-depth*.55
        obj=object_id or id
        self.polygon(id+'-top',[(x,y),(x+dx,y+dy),(x+w+dx,y+dy),(x+w,y)],color,obj)
        self.polygon(id+'-side',[(x+w,y),(x+w+dx,y+dy),(x+w+dx,y+h+dy),(x+w,y+h)],color,obj)
        self.polygon(id+'-front',[(x,y),(x+w,y),(x+w,y+h),(x,y+h)],color,obj)
    def save(self,path):
        E.indent(self.xml);Path(path).write_bytes(E.tostring(self.xml,encoding='utf-8',xml_declaration=True))
