"""只绘制原官方响应中已有事件。"""
import csv
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
W=Path(__file__).resolve().parent.parent;D=W/'求解/规范化数据/studies'
events=list(csv.DictReader((D/'trace_fifo_events.csv').open(encoding='utf-8-sig')))
ops=list(csv.DictReader((D/'trace_pipe_ddr.csv').open(encoding='utf-8-sig')))
plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['SimHei','Microsoft YaHei'],'font.size':9,'axes.unicode_minus':False,'pdf.fonttype':42,'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False})
f,axs=plt.subplots(3,1,figsize=(6.3,5.0),gridspec_kw={'height_ratios':[1,1,1.55]},layout='constrained')
spec=[('1000000001','甲：4096 字节',12000,[(345,5254),(11337,12000)]),('1000000187','乙：8192 字节',6500,[(1030,5599)])]
color={'miss':'#D58B36','insert':'#138B85','hit':'#24618F','evict':'#AC6464'};name={'miss':'未命中','insert':'填充','hit':'命中','evict':'淘汰'}
for a,(tensor,title,end,intervals) in zip(axs[:2],spec):
 a.set_title('张量'+title,loc='left',fontsize=10);a.set(xlim=(-end*.02,end*1.03),ylim=(-1,1.5),xlabel='时间 / 周期',yticks=[]);a.spines['left'].set_visible(False)
 a.axhline(0,color='#B6C8D0',lw=.7)
 for s,t in intervals:a.broken_barh([(s,t-s)],(-.13,.26),facecolors='#B5DDD5')
 selected=[]
 for e in events:
  t=int(e['cycle'])
  if t>end:continue
  if e['tensor_id']==tensor:selected.append((t,e['event']))
  if tensor in e['evicted_tensor_ids'].split(';'):selected.append((t,'evict'))
 for j,(t,ev) in enumerate(selected):
  dy=.58 if j%2==0 else -.55;a.plot(t,0,'o',color=color[ev],ms=4)
  a.annotate(name[ev]+'\n'+str(t),(t,0),(t,dy),ha='left' if t==0 else 'center',va='center',fontsize=8,arrowprops=dict(arrowstyle='-',color=color[ev],lw=.6))
a=axs[2];a.set_title('开始阶段的五核读入流水线',loc='left',fontsize=10)
for r in ops:
 s=int(r['start_cycle']);t=int(r['end_cycle']);k=int(r['core_id'])
 if s>=1400:continue
 c='#24618F' if r['memory_path']=='DDR' else '#138B85';a.broken_barh([(s,t-s)],(k-.28,.56),facecolors=c,edgecolor='white',lw=.5)
a.set(xlim=(0,1400),yticks=range(5),yticklabels=[f'核心 {i+1}' for i in range(5)],xlabel='时间 / 周期');a.grid(axis='x',color='#DFE8EC',lw=.65);a.set_axisbelow(True)
a.text(1,1.04,'蓝：主存读入　绿：二级缓存读入',ha='right',transform=a.transAxes,fontsize=8)
out=W/'求解/问题三/图片'
for ext in ['pdf','svg','png']:f.savefig(out/('q3_trace.'+ext),dpi=300,bbox_inches='tight',pad_inches=.06)
print('已生成真实缓存事件与读入流水线图。')
