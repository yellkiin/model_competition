"""从已规范化原记录绘制中文论文图；不调用求解器。"""
import csv,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap,Normalize,PowerNorm
from matplotlib.ticker import PercentFormatter,MaxNLocator

W=Path(__file__).resolve().parent.parent
D=W/'求解/规范化数据/combined'
def read(name):return list(csv.DictReader((D/name).open(encoding='utf-8-sig')))
main=read('main.csv');pairs=read('pairs.csv');means=read('means.csv')
M={(r['case'],int(r['q']),int(r['n'])):r for r in main}
cases=sorted({r['case'] for r in main})
blue='#24618F';teal='#138B85';orange='#D58B36';ink='#243746'
colors=['#BCCBD6','#719CB7',blue,teal,orange]
plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['SimHei','Microsoft YaHei','DejaVu Sans'],
 'font.size':10,'axes.labelsize':10,'axes.titlesize':11,'axes.titleweight':'bold','axes.edgecolor':'#9EAEB9',
 'axes.labelcolor':ink,'text.color':ink,'xtick.color':ink,'ytick.color':ink,'axes.unicode_minus':False,
 'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.65,'pdf.fonttype':42,'ps.fonttype':42,
 'svg.fonttype':'none','savefig.facecolor':'white','figure.facecolor':'white','legend.frameon':False})
manifest=[]
def figure(size=(6.3,3.65)):
 f,a=plt.subplots(figsize=size,layout='constrained');a.grid(axis='y',color='#E5ECF0',lw=.65);a.set_axisbelow(True);return f,a
def val(q,n,key='speedup'):return np.array([float(M[(c,q,n)][key]) for c in cases])
def export(f,q,name,inputs,meaning):
 out=W/'求解'/('问题'+['','一','二','三'][q])/'图片';out.mkdir(parents=True,exist_ok=True)
 for ext in ['pdf','svg','png']:f.savefig(out/(name+'.'+ext),dpi=300,bbox_inches='tight',pad_inches=.07)
 manifest.append(dict(id=name,question=q,language='zh-CN',files=[str(out/(name+'.'+e)) for e in ['pdf','svg','png']],editable_source=str(Path(__file__).resolve()),inputs=inputs,meaning=meaning))
 plt.close(f)

# 题面分别要求的三条核数扩展曲线，采用同一视觉尺度。
for q in [1,2,3]:
 f,a=figure();ns=np.arange(1,6)
 yy=[float(r['mean_speedup']) for r in means if int(r['q'])==q]
 a.plot(ns,ns,ls='--',color='#AFBDC6',lw=1,label='核数参照线')
 if q==3:
  no=[np.mean([float(M[(p['case'],0,1)]['makespan'])/float(p['without_l2']) for p in pairs if int(p['n'])==n]) for n in ns]
  a.plot(ns,no,'s--',color=orange,lw=1.6,ms=4,label='同方案，无二级缓存（L2）')
 a.plot(ns,yy,'o-',color=blue if q<3 else teal,lw=2.1,ms=5,label='本问最终方案' if q<3 else '同方案，有二级缓存（L2）')
 for x,y in zip(ns,yy):a.annotate(f'{y:.4f}',(x,y),xytext=(0,-18 if q==3 else 9),textcoords='offset points',ha='center',fontsize=9,color=blue if q<3 else teal)
 a.set(xlabel='核心数',ylabel='平均加速比',xticks=ns,xlim=(.7,5.4),ylim=(.65,5.55));a.legend(loc='upper left')
 a.text(.98,.03,'100 图逐例比值的算术平均',transform=a.transAxes,ha='right',fontsize=9,color='#617989')
 export(f,q,f'q{q}_mean',['means.csv','pairs.csv'],'各核数平均加速比；第三问以同一方案无L2评价对照')

f,a=figure()
for n in range(2,6):
 x=np.sort(val(1,n));a.step(x,np.arange(1,101)/100,where='post',lw=1.8,color=colors[n-1],label=f'{n} 核')
a.set(xlabel='逐图加速比',ylabel='累计图比例',ylim=(0,1.025));a.yaxis.set_major_formatter(PercentFormatter(1));a.legend(loc='lower right',ncol=2)
export(f,1,'q1_distribution',['main.csv'],'第一问2至5核100图经验累计分布')

f,a=figure((6.3,4.3));time=read('anytime.csv');matrix=np.full((100,21),np.nan)
for r in time:
 if int(r['q'])==1 and int(r['n'])==5 and r['relative_excess_to_final']:
  matrix[cases.index(r['case']),int(r['seconds'])//30]=float(r['relative_excess_to_final'])
cmap=LinearSegmentedColormap.from_list('progress',['#F0F6F5',teal,blue]);cmap.set_bad('#DBDFE2')
im=a.imshow(matrix,aspect='auto',origin='lower',interpolation='nearest',cmap=cmap,norm=PowerNorm(gamma=.35,vmin=0,vmax=1))
a.grid(False);a.set(xticks=np.arange(0,21,2),xticklabels=np.arange(0,601,60),yticks=[0,19,39,59,79,99],yticklabels=['001','020','040','060','080','100'],xlabel='原搜索已用时间 / 秒',ylabel='图编号')
cb=f.colorbar(im,ax=a,pad=.025,extend='max');cb.set_label('相对最终周期的超额比例');cb.ax.yaxis.set_major_formatter(PercentFormatter(1))
a.set_title('每 30 秒已取得的可用方案',loc='left',pad=10)
a.text(1,1.025,'灰色：尚无可用记录',transform=a.transAxes,ha='right',fontsize=8.5,color='#637785')
export(f,1,'q1_anytime',['anytime.csv'],'仅使用采样点前已经取得的方案；灰色不以前缀后的结果补齐')

f,a=figure();x=val(1,5,'global_lower');y=val(1,5,'makespan');ratio=x/y
im=a.scatter(x,y,c=ratio,cmap='viridis',s=23,alpha=.9,edgecolors='white',linewidths=.3)
lo=min(x.min(),y.min())*.7;hi=max(x.max(),y.max())*1.4;a.plot([lo,hi],[lo,hi],ls='--',color='#8397A6',lw=1,label='周期等于下界')
a.set(xscale='log',yscale='log',xlabel='全局下界 / 周期',ylabel='五核总体任务执行时间 / 周期',xlim=(lo,hi),ylim=(lo,hi));a.legend(loc='upper left')
f.colorbar(im,ax=a,pad=.025,label='下界 / 当前周期')
export(f,1,'q1_bound',['main.csv'],'第一问五核周期及全局下界；等值线不是最优性证明')

f,a=figure();ys=[val(1,5),val(2,5)];offset=np.linspace(-.11,.11,100)
for i in range(100):a.plot([1+offset[i],2+offset[i]],[ys[0][i],ys[1][i]],color='#AABEC8',alpha=.22,lw=.6,zorder=1)
bp=a.boxplot(ys,positions=[1,2],widths=.32,patch_artist=True,showfliers=False,medianprops=dict(color=ink,lw=1.4),whiskerprops=dict(color='#859BAA'),capprops=dict(color='#859BAA'))
for b,c in zip(bp['boxes'],[blue,teal]):b.set(facecolor=c,alpha=.2,edgecolor=c)
offset=np.linspace(-.11,.11,100)
for j,y in enumerate(ys):a.scatter(j+1+offset,y,s=12,color=[blue,teal][j],alpha=.75,zorder=3)
a.set(xticks=[1,2],xticklabels=['第一问','第二问'],ylabel='五核逐图加速比',xlim=(.55,2.45));a.text(.02,.97,'细线连接同一张图',transform=a.transAxes,ha='left',va='top',fontsize=9)
export(f,2,'q2_distribution',['main.csv'],'两个独立寻优结果的逐图配对分布；无显著性星号')

f,axs=plt.subplots(1,4,figsize=(6.3,3.7),sharey=True,layout='constrained')
delta=val(2,5,'added_copy_bytes')-val(1,5,'added_copy_bytes');order=np.argsort(delta,kind='stable')
for j,a in enumerate(axs):
 ids=order[j*25:(j+1)*25];a.grid(axis='y',color='#E5ECF0',lw=.6)
 for i in ids:
  yy=[1/ys[0][i],1/ys[1][i]];a.plot([1,2],yy,color='#9DAFB8',alpha=.45,lw=.6)
  a.scatter([1,2],yy,c=[blue,teal],s=10,alpha=.8)
 a.set(xticks=[1,2],xticklabels=['问一','问二'],xlim=(.7,2.3),title=f'第 {j+1} 四分位')
 a.text(.5,-.17,f'变化范围\n{delta[ids].min()/1e6:.2f} 至 {delta[ids].max()/1e6:.2f} MB',transform=a.transAxes,ha='center',fontsize=8)
axs[0].set_ylabel('总体任务执行时间 / 单核参考周期')
export(f,2,'q2_copy',['main.csv'],'按额外COPY字节变化排序分为四组，每组25张图且每一连线均为同图配对')

f,axs=plt.subplots(1,2,figsize=(6.3,3.2),layout='constrained');src=[r for r in read('source_summary.csv') if r['q']=='2' and r['source'] in ['b','s','m']];src.sort(key=lambda r:['b','s','m'].index(r['source']))
names=['基础候选','结构候选','驻留候选']
for a in axs:a.grid(axis='x',color='#E5ECF0',lw=.6);a.spines['left'].set_visible(False);a.set_ylim(-.6,2.6)
for i,r in enumerate(src):
 count=int(r['evaluations']);improved=int(r['makespan_improvements']);rate=improved/count
 axs[0].hlines(i,0,count,color='#C5D8E0',lw=4);axs[0].plot(count,i,'o',color=blue);axs[0].text(count+250,i,str(count),va='center',fontsize=9)
 axs[1].hlines(i,0,rate,color='#C2E0DA',lw=4);axs[1].plot(rate,i,'o',color=teal);axs[1].text(rate+.002,i,f'{rate:.2%}（{improved} 次）',va='center',fontsize=9)
axs[0].set(yticks=range(3),yticklabels=names,xlabel='完成评价的候选数',xlim=(0,20500));axs[1].set(yticks=range(3),yticklabels=[],xlabel='周期改善次数 / 评价次数',xlim=(0,.085));axs[1].xaxis.set_major_formatter(PercentFormatter(1))
export(f,2,'q2_sources',['source_summary.csv'],'实际调用及改善记录的描述性比较，不解释为关闭来源的因果消融')

f,a=figure()
for n in range(1,6):
 x=np.sort([float(p['cache_speedup']) for p in pairs if int(p['n'])==n]);a.step(x,np.arange(1,len(x)+1)/len(x),where='post',color=colors[n-1],lw=1.6,label=f'{n} 核')
a.axvline(1,ls=':',color='#8197A6',lw=.9);a.set(xlabel='同方案无 L2 周期 / 有 L2 周期',ylabel='累计图比例',ylim=(0,1.025));a.yaxis.set_major_formatter(PercentFormatter(1));a.legend(ncol=2,loc='lower right')
export(f,3,'q3_pairs',['pairs.csv'],'每个核数均为100图同一完整方案缓存对照')

f,a=figure();p5=[p for p in pairs if p['n']=='5'];xx=np.array([float(p['hit_rate']) for p in p5]);yy=np.array([float(p['cache_speedup']) for p in p5]);a.scatter(xx,yy,s=27,color=teal,alpha=.75,edgecolors='white',lw=.4)
a.axhline(1,color='#8197A6',ls='--',lw=.8);a.set(xlabel='L2 字节命中率',ylabel='同方案无 L2 周期 / 有 L2 周期',ylim=(.97,2.05));a.xaxis.set_major_formatter(PercentFormatter(1))
for case in ['case_046','case_001']:
 idx=next(i for i,p in enumerate(p5) if p['case']==case);a.annotate('图 '+case[-3:],(xx[idx],yy[idx]),xytext=(8,8),textcoords='offset points',fontsize=9)
export(f,3,'q3_hit_gain',['pairs.csv'],'五核缓存命中与周期改善的逐图关系，不进行因果拟合')

study=list(csv.DictReader((W/'求解/规范化数据/studies/cache_parameter_grid.csv').open(encoding='utf-8-sig')))
f,axs=plt.subplots(2,3,figsize=(6.3,5.45),layout='constrained');cs=['case_001','case_080','case_006','case_044','case_004','case_046'];caps=[262144,1048576,4194304];bws=[60,250,500]
cm=LinearSegmentedColormap.from_list('parameter',['#F3F7F6','#B9DBD5',teal,blue])
for a,case in zip(axs.flat,cs):
 g=[r for r in study if r['case']==case and r['mode']=='fixed_plan'];z=np.array([[float(next(r for r in g if int(r['capacity_bytes'])==cap and int(r['bandwidth_bytes_per_cycle'])==bw)['makespan_cycles']) for bw in bws] for cap in caps]);base=z[1,1]
 im=a.imshow(z/base,cmap=cm,vmin=.6,vmax=1.8,aspect='auto')
 for i in range(3):
  for j in range(3):a.text(j,i,f'{z[i,j]/1000:.2f}',ha='center',va='center',fontsize=8.5,color='white' if z[i,j]/base>1.2 else ink)
 a.set(xticks=range(3),xticklabels=bws,yticks=range(3),yticklabels=['0.25','1','4'],title='图 '+case[-3:],xlabel='L2 带宽 /（字节/周期）',ylabel='L2 容量 / MiB');a.tick_params(labelsize=8.5);a.xaxis.label.set_size(8.5);a.yaxis.label.set_size(8.5)
cb=f.colorbar(im,ax=axs,pad=.03,shrink=.75);cb.set_label('周期 / 本图默认配置周期',fontsize=9);cb.ax.tick_params(labelsize=8)
f.suptitle('固定同一方案；格内数值为千周期',fontsize=10)
export(f,3,'q3_parameters',['../studies/cache_parameter_grid.csv'],'六图54组固定方案实测参数格；12组重新调整方案不混入')

(W/'求解/RESULT_FIGURES.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print('已输出',len(manifest),'张中文结果图，每图包含 PDF、SVG、PNG 与 Python 源。')
