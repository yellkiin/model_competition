"""Render original FIFO events, preserving exact times and observation windows."""
import csv,json
import numpy as np
from matplotlib import pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from style import *

D=WORK/'求解/规范化数据/studies'
def read(name):
    with (D/name).open(encoding='utf-8-sig') as f:return list(csv.DictReader(f))
events=read('trace_fifo_events.csv');ops=read('trace_pipe_ddr.csv')
styles={'miss':(M,'s','未命中'),'insert':(S,'o','填充'),'hit':(F,'D','命中'),'evict':(INK,'x','淘汰')}
fig,axes=plt.subplots(3,1,figsize=(6.4,5.55),layout='constrained',gridspec_kw={'height_ratios':[1,1,1.6]})
used=[]
for ax,tid,title in zip(axes[:2],['1000000001','1000000187'],['（a）张量甲 · 4096 B','（b）张量乙 · 8192 B']):
    end=12000;selected=[];intervals=[];resident_start=None
    for row in events:
        t=int(row['cycle'])
        if t>end:break
        if tid in row['evicted_tensor_ids'].split(';'):
            selected.append((t,'evict'))
            if resident_start is not None:intervals.append((resident_start,t));resident_start=None
        if row['tensor_id']==tid:
            selected.append((t,row['event']))
            if row['event']=='insert' and resident_start is None:resident_start=t
    if resident_start is not None:intervals.append((resident_start,end))
    ax.set_title(title,loc='left',pad=5,fontsize=10.5)
    ax.set(xlim=(-250,12400),ylim=(-.72,1.43),yticks=[],xticks=[0,3000,6000,9000,12000])
    ax.tick_params(axis='x',length=2,labelsize=8)
    ax.spines['left'].set_visible(False)
    ax.axhline(.36,color=wash(INK,.35),lw=.65,zorder=0)
    for start,stop in intervals:
        ax.broken_barh([(start,stop-start)],(.25,.22),facecolors=wash(F,.16),edgecolors=F,lw=.5,hatch='///')
    for i,(t,ev) in enumerate(selected):
        c,m,label=styles[ev]
        ax.plot(t,.36,marker=m,ms=4.8,mfc='white' if m!='x' else c,mec=c,mew=.9,zorder=4,color=c)
        # Spread annotations on fixed clean rows; marker stays at original t.
        above=ev in ('insert','evict')
        texty=1.06 if above else -.32
        textx=t
        if tid=='1000000001':
            textx={0:320,345:1150,5254:5254,10823:10200,11337:11550}.get(t,t)
        else:textx={345:450,1030:1350,1380:2775,5599:5599}.get(t,t)
        ax.annotate(f'{label}\n{t}',xy=(t,.36),xytext=(textx,texty),ha='center',va='center',fontsize=8.5,color=c,
                    arrowprops={'arrowstyle':'-','color':wash(c,.65),'lw':.6,'shrinkA':3,'shrinkB':4})
        used.append({'tensor_id':tid,'cycle':t,'event':ev,'observation_end':end})
    if resident_start is not None:
        ax.plot(end,.36,marker='>',ms=4,color=F,mfc='white')
axes[1].set_xlabel('时间 / 周期',fontsize=9)
ax=axes[2];ax.set_title('（c）开始阶段的五核读入流水线',loc='left',fontsize=10.5,pad=13)
for r in ops:
    start,stop,k=int(r['start_cycle']),int(r['end_cycle']),int(r['core_id'])
    if start>=1400:continue
    color=M if r['memory_path']=='DDR' else F
    ax.broken_barh([(start,min(stop,1400)-start)],(k-.26,.52),facecolors=wash(color,.38),edgecolors=color,lw=.55,hatch='///' if r['memory_path']=='DDR' else None)
ax.set(xlim=(0,1400),yticks=range(5),yticklabels=[f'核心 {i+1}' for i in range(5)],xticks=[0,345,700,1030,1400],xlabel='时间 / 周期')
ax.invert_yaxis();ax.grid(axis='x',color=wash(INK,.12),lw=.5);ax.set_axisbelow(True);ax.tick_params(labelsize=8.5)
ax.legend(handles=[Patch(facecolor=wash(M,.38),edgecolor=M,hatch='///',lw=.6,label='DDR 读入'),Patch(facecolor=wash(F,.38),edgecolor=F,lw=.6,label='L2 读入')],loc='upper right',bbox_to_anchor=(1,1.20),ncol=2,fontsize=8,handlelength=1.8,borderaxespad=0)
finish(fig,3,'q3_trace')
DATA=HERE/'plot_data';DATA.mkdir(exist_ok=True)
with (DATA/'q3_trace_events.csv').open('w',encoding='utf-8-sig',newline='') as f:
    wr=csv.DictWriter(f,list(used[0]));wr.writeheader();wr.writerows(used)
selected_ops=[r for r in ops if int(r['start_cycle'])<1400]
with (DATA/'q3_trace_reads.csv').open('w',encoding='utf-8-sig',newline='') as f:
    wr=csv.DictWriter(f,list(selected_ops[0]));wr.writeheader();wr.writerows(selected_ops)
print('Trace rendered from original events:',len(used),'and read records:',len(selected_ops))
