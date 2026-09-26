"""三问中文总览图：统一决策、实际执行、候选改进和原记录结果。"""
from pathlib import Path
import csv,json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch,FancyArrowPatch
import numpy as np
W=Path(__file__).resolve().parent.parent;D=W/'求解/规范化数据/combined'
def rows(name):return list(csv.DictReader((D/name).open(encoding='utf-8-sig')))
means=rows('means.csv');pairs=rows('pairs.csv');main=rows('main.csv')
plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['SimHei','Microsoft YaHei'],'font.size':9,'axes.unicode_minus':False,'pdf.fonttype':42,'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False,'axes.edgecolor':'#B2C1CA','axes.labelcolor':'#243746','xtick.color':'#435C6C','ytick.color':'#435C6C'})
blue='#24618F';teal='#138B85';orange='#D58B36';ink='#243746'
content={1:('子图任务：协调并行与边界代价','每个子图一个任务','同核等待 100 周期\n跨核前驱等待 1000 周期','所有跨子图数据\n经共享主存（DDR）','结构迁移 / 拆分 / 交换','通信驻留候选','五核平均加速比 3.9180'),2:('核心任务：协调驻留与跨核交接','同核子图合为一个任务','同核保留片上状态\n容量不足则自动换出','跨核写出完成后\n等待 500 周期再读入','结构迁移 / 合并 / 重划分','张量整体迁移','五核平均加速比 4.4538'),3:('共享缓存：协调读入与驻留窗口','核心任务与只读二级缓存','发射时查询，完成后填入\n命中不改变先入先出顺序','主存与二级缓存\n分别共享各自带宽','基础 / 结构 / 驻留候选','缓存时序候选','五核平均加速比 4.5978')}
for q,(title,task,timing,memory,source1,source2,result) in content.items():
 f=plt.figure(figsize=(6.3,5.6));a=f.add_axes([.02,.43,.96,.52]);a.set(xlim=(0,100),ylim=(0,100));a.axis('off')
 def box(x,y,w,h,head,body,color=blue):
  a.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=.4,rounding_size=1.4',facecolor=color+'0F',edgecolor='#CEDAE0',lw=.65))
  a.text(x+2.3,y+h-5,head,fontsize=10,color=color,va='top',weight='bold');a.text(x+2.3,y+h-16,body,fontsize=8.5,color=ink,va='top',linespacing=1.45)
 def arrow(x1,y1,x2,y2,color=blue,rad=0):a.add_patch(FancyArrowPatch((x1,y1),(x2,y2),arrowstyle='-|>',mutation_scale=9,lw=1.0,color=color,connectionstyle=f'arc3,rad={rad}',clip_on=False))
 f.text(.035,.982,title,ha='left',va='top',size=13,color=ink,weight='bold')
 box(1,62,29,31,'联合决策','子图划分 · 核心归属\n每核子图顺序')
 box(35,62,29,31,'任务组织',task+'\n'+('核心内外区别交接' if q<3 else '先进先出（FIFO）'),teal)
 box(69,62,29,31,'统一目标','总体任务执行时间最小\n等周期时减少额外搬运')
 arrow(30,77,35,77);arrow(64,77,69,77)
 a.text(1,51,'执行语义',fontsize=10,weight='bold',color=teal)
 a.text(21,52,timing,fontsize=8.5,va='center',linespacing=1.35,color=ink)
 a.text(61,52,memory,fontsize=8.5,va='center',linespacing=1.35,color=ink)
 a.plot([1,99],[38,38],color='#D6E2E7',lw=.7)
 for x,w,head,body,col in [(1,29,'互补候选',source1+'\n'+source2,blue),(35,29,'完整执行','依赖 · 容量 · 流水线\n共享带宽 · 事件推进',teal),(69,29,'保留改善','可行且目标严格改进\n更新当前方案',blue)]:box(x,3,w,29,head,body,col)
 arrow(30,17,35,17);arrow(64,17,69,17)
 arrow(83,3,15,3,orange,-.10);a.text(50,-5,'围绕当前可行方案继续迭代',ha='center',fontsize=8.5,color=orange,bbox=dict(facecolor='white',edgecolor='none',pad=2))
 left=f.add_axes([.115,.115,.36,.235]);right=f.add_axes([.615,.115,.35,.235])
 yy=[float(r['mean_speedup']) for r in means if int(r['q'])==q]
 left.plot(range(1,6),yy,'o-',color=blue,lw=1.6,ms=3.5);left.set(xticks=range(1,6),xlabel='核心数',ylabel='平均加速比',ylim=(.8,5.1));left.grid(axis='y',color='#E5ECF0',lw=.6)
 left.set_title('100 图核数扩展',fontsize=9,loc='left');left.tick_params(labelsize=8)
 if q==1:
  values=sorted(float(r['speedup']) for r in main if r['q']=='1' and r['n']=='5');right.step(values,np.arange(1,101)/100,color=teal,lw=1.5,where='post');right.set(xlabel='五核逐图加速比',ylabel='累计图比例',ylim=(0,1.02));right.set_title('逐图差异',fontsize=9,loc='left')
 elif q==2:
  right.barh(['更长','相同','更短'],[2,9,89],color=['#DDB881','#CDD9DE',teal],height=.5);right.set(xlabel='图数',xlim=(0,104));right.set_title('与第一问五核周期比较',fontsize=9,loc='left')
  for y,v in enumerate([2,9,89]):right.text(v+2,y,str(v),va='center',fontsize=8)
 else:
  p=[r for r in pairs if r['n']=='5'];right.scatter([float(r['hit_rate']) for r in p],[float(r['cache_speedup']) for r in p],s=9,alpha=.65,color=teal);right.set(xlabel='字节命中率',ylabel='无缓存 / 有缓存周期');right.set_title('100 组同方案缓存配对',fontsize=9,loc='left')
 right.grid(axis='y',color='#E5ECF0',lw=.6);right.tick_params(labelsize=8)
 f.text(.5,.024,result,ha='center',fontsize=11,color=blue,weight='bold')
 out=W/'求解'/('问题'+['','一','二','三'][q])/'图片';out.mkdir(exist_ok=True,parents=True)
 for ext in ['pdf','svg','png']:f.savefig(out/f'q{q}_overview.{ext}',dpi=300,facecolor='white')
 plt.close(f)
 frag=W/'论文/综合图片段';frag.mkdir(exist_ok=True)
 (frag/f'q{q}.tex').write_text('\\begin{figure}[htbp]\n\\centering\n\\includegraphics[width=\\textwidth]{../求解/问题'+['','一','二','三'][q]+'/图片/q'+str(q)+'_overview.pdf}\n\\caption{问题'+['','一','二','三'][q]+'的联合建模与迭代改进框架}\\label{fig:q'+str(q)+'_overview}\n\\end{figure}\n',encoding='utf-8')
print('三问总览图已生成。')
