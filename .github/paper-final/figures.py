"""Change plotted observations only; retain vector axes, fonts and styles."""
from pathlib import Path
import re, os
import numpy as np
import pandas as pd
import fitz
from lxml import etree as E
W=Path('20hw_myskill_distribution/20hw_myskill_distribution/workshop_v2');F=W/'求解/问题三/图片'
D=pd.read_csv(W/'数据/l2_patch_60_62/q3_latest_500.csv.xz',encoding='utf-8-sig');D['s']=D.reference_t1/D.makespan;D['r']=D.no_l2_makespan/D.makespan
NS={'s':'http://www.w3.org/2000/svg'}
def load(stem):
 p=F/stem;tr=E.parse(str(p.with_suffix('.svg')));doc=fitz.open(p.with_suffix('.pdf'));stream=doc.xref_stream(doc[0].get_contents()[0]).decode('latin1');return p,tr,doc,stream
def find(tr,id):return tr.xpath('//*[@id="'+id+'"]')[0]
def nums(path):return np.array([tuple(map(float,m)) for m in re.findall(r'[ML]\s*([-\d.]+)\s+([-\d.]+)',path)])
def pathdata(xy,pdf=False):return '\n'.join((f'{x:.6f} {y:.6f} '+('m' if i==0 else 'l')) if pdf else (('M' if i==0 else 'L')+f' {x:.6f} {y:.6f}') for i,(x,y) in enumerate(xy))
def replace_path(s,old,new,height):
 pat=r'(?m)^[-\d.]+ [-\d.]+ m\n(?:[-\d.]+ [-\d.]+ l\n)+';matches=[]
 for m in re.finditer(pat,s):
  pts=np.array([tuple(map(float,x)) for x in re.findall(r'([-\d.]+) ([-\d.]+) [ml]',m.group())]);want=old.copy();want[:,1]=height-want[:,1]
  if len(pts)==len(want) and np.max(np.abs(pts-want))<2e-5:matches.append(m)
 if len(matches)!=1:raise ValueError(('path not unique',len(old),len(matches)))
 m=matches[0];pts=new.copy();pts[:,1]=height-pts[:,1];return s[:m.start()]+pathdata(pts,True)+'\n'+s[m.end():]
def save(p,tr,doc,s):
 tr.write(str(p.with_suffix('.svg')),encoding='utf-8',xml_declaration=True)
 doc.update_stream(doc[0].get_contents()[0],s.encode('latin1'));tmp=p.with_suffix('.new.pdf');doc.save(tmp,deflate=True);doc.close();os.replace(tmp,p.with_suffix('.pdf'))
 with fitz.open(p.with_suffix('.pdf')) as d:d[0].get_pixmap(matrix=fitz.Matrix(2.5,2.5)).save(p.with_suffix('.png'))
def marker_stream(s,key,xy):
 pat=r'(?:1 0 0 1 [-\d.]+ [-\d.]+ cm /'+key+r' Do\n)+'
 matches=[m for m in re.finditer(pat,s) if m.group().count(' Do')==len(xy)]
 if len(matches)!=1:raise ValueError(('markers',key,len(matches)))
 m=matches[0];prev=(0,0);lines=[]
 for x,y in xy:lines.append(f'1 0 0 1 {x-prev[0]:.10f} {y-prev[1]:.10f} cm /{key} Do');prev=(x,y)
 return s[:m.start()]+'\n'.join(lines)+'\n'+s[m.end():]
p,tr,doc,s=load('q3_mean');H=float(tr.getroot().attrib['height'][:-2]);xs=np.array([57.9506076596,147.6526331915,237.3546587234,327.0566842553,416.7587097872])
for gid,key,vals in [('line2d_17','M0',[(g.reference_t1/g.no_l2_makespan).mean() for _,g in D.groupby('n')]),('line2d_18','M1',[g.s.mean() for _,g in D.groupby('n')])]:
 g=find(tr,gid);path=g.find('s:path',NS);old=nums(path.attrib['d']);ys=52.1685371429+(np.array(vals)-1)*46.0815346939;new=np.c_[xs,H-ys]
 s=replace_path(s,old,new,H);path.attrib['d']=pathdata(new)
 for el,(x,y) in zip(g.xpath('.//s:use',namespaces=NS),new):el.attrib.update({'x':f'{x:.6f}','y':f'{y:.6f}'})
 s=marker_stream(s,key,np.c_[xs,ys])
 if key=='M1':
  for i,(x,y,val) in enumerate(zip(xs,ys,vals)):
   el=find(tr,f'text_{13+i}').find('s:text',NS);oldtext=el.text;txt=f'{val:.4f}';el.text=txt;el.attrib['y']=f'{H-y+18:.6f}';el.attrib['transform']=f'rotate(-0 {el.attrib["x"]} {el.attrib["y"]})'
   ot=oldtext.encode('utf-16-be').decode('latin1');nt=txt.encode('utf-16-be').decode('latin1');pattern=r'q\n1 0 -0 1 ([-\d.]+) ([-\d.]+) cm\nBT\n/F1 9 Tf\n0 0 Td\n\[ \('+re.escape(ot)+r'\) \] TJ\nET\nQ'
   def rep(m):return m.group().replace(m.group(2)+' cm',f'{y-18:.10f} cm').replace(ot,nt)
   s,n=re.subn(pattern,rep,s)
   if n!=1:raise ValueError(('mean label',oldtext,n))
save(p,tr,doc,s)
p,tr,doc,s=load('q3_pairs');H=float(tr.getroot().attrib['height'][:-2])
for n in range(1,6):
 path=find(tr,f'line2d_{17+n}').find('s:path',NS);old=nums(path.attrib['d']);r=np.sort(D[D.n==n].r.to_numpy());ex=64.525378188+(r-1)*395.287957503;ey=230.83952-np.arange(1,101)/100*220.292214634
 xy=[(ex[0],ey[0])]
 for i in range(1,100):xy.extend([(ex[i],ey[i-1]),(ex[i],ey[i])])
 new=np.array(xy);s=replace_path(s,old,new,H);path.attrib['d']=pathdata(new)
save(p,tr,doc,s)
p,tr,doc,s=load('q3_hit_gain');H=float(tr.getroot().attrib['height'][:-2]);d=D[D.n==5].sort_values('case');xs=59.7490690909+d.cache_hit_rate.to_numpy()*466.809050647;ys=H-224.567311+(d.r.to_numpy()-1)*209.07363
for el,x,y in zip(find(tr,'PathCollection_1').xpath('.//s:use',namespaces=NS),xs,ys):el.attrib.update({'x':f'{x:.6f}','y':f'{H-y:.6f}'})
keys=re.findall(r'cm /(\w+) Do',s);key=max(set(keys),key=keys.count);s=marker_stream(s,key,np.c_[xs,ys]);save(p,tr,doc,s)
print('Three Q3 plots updated in PDF/SVG/PNG with existing styles retained.')
