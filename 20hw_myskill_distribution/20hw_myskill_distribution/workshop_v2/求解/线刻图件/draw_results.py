"""Redraw the paper's bound result figures; no solver and no new experiments."""
from pathlib import Path
import csv,json,lzma
import numpy as np
from matplotlib import pyplot as plt
from matplotlib.colors import LinearSegmentedColormap,TwoSlopeNorm
from matplotlib.ticker import PercentFormatter,MaxNLocator,FuncFormatter
from matplotlib.patches import Rectangle
from matplotlib.lines import Line2D
from style import *

D=WORK/'求解/规范化数据/combined'
ST=WORK/'求解/规范化数据/studies'
DATA=HERE/'plot_data';DATA.mkdir(exist_ok=True)

def read(p):
    opener=lzma.open if Path(p).suffix=='.xz' else open
    with opener(p,'rt',encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def record(name,rows):
    if not rows:return
    with (DATA/f'{name}.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)

MAIN=read(D/'main.csv');lookup={(r['case'],int(r['q']),int(r['n'])):r for r in MAIN}
CASES=sorted({r['case'] for r in MAIN})
Q3=read(WORK/'数据/l2_patch_60_62/q3_latest_500.csv.xz')
Q={(r['case'],int(r['n'])):r for r in Q3}
assert len(CASES)==100 and len(Q)==500
manifest=[]

def vec(q,n,key='speedup'):
    if q in (1,2) and n==1:
        if key=='speedup':return np.ones(len(CASES))
        return np.array([float(lookup[c,0,1][key]) for c in CASES])
    if q==3:
        if key=='speedup':return np.array([float(Q[c,n]['reference_t1'])/float(Q[c,n]['makespan']) for c in CASES])
        if key=='cache_speedup':return np.array([float(Q[c,n]['no_l2_makespan'])/float(Q[c,n]['makespan']) for c in CASES])
        return np.array([float(Q[c,n][key]) for c in CASES])
    return np.array([float(lookup[c,q,n][key]) for c in CASES])

def save(fig,q,name,meaning,inputs):
    target=finish(fig,q,name)
    manifest.append({'figure':name,'question':q,'files':[target+'.'+e for e in ['pdf','svg','png']],
                     'meaning':meaning,'input_files':inputs,'plot_data':f'求解/线刻图件/plot_data/{name}.csv'})

# Shared axes, pigment roles and direct labels for all three core-scaling figures.
for q in (1,2,3):
    f,a=figure((6.35,3.55));ns=np.arange(1,6)
    mean=np.array([np.mean(vec(q,n)) for n in ns]);role=[None,S,M,F][q]
    a.plot(ns,ns,ls=(0,(5,3)),color=wash(INK,.38),lw=.95,label='核数参照线')
    rs=[]
    if q==3:
        no=np.array([np.mean([float(Q[c,n]['reference_t1'])/float(Q[c,n]['no_l2_makespan']) for c in CASES]) for n in ns])
        a.plot(ns,no,ls='--',marker='s',mfc='white',mec=INK,color=INK,lw=1.15,ms=4,label='同方案无 L2')
    else:no=[None]*5
    a.plot(ns,mean,'o-',color=role,mfc='white',mec=role,mew=1.2,lw=1.85,ms=5,label='同方案有 L2' if q==3 else '100 图平均加速比')
    for n,y,z in zip(ns,mean,no):
        a.annotate(f'{y:.4f}',(n,y),xytext=(0,12),textcoords='offset points',ha='center',fontsize=9.5,color=role,bbox=dict(facecolor='white',edgecolor='none',pad=1.0))
        if q==3:a.annotate(f'{z:.4f}',(n,z),xytext=(0,-17),textcoords='offset points',ha='center',fontsize=9,color=INK,bbox=dict(facecolor='white',edgecolor='none',pad=1.0))
        rs.append({'n':int(n),'mean_speedup':y,'same_plan_no_l2_mean_speedup':z if z is not None else ''})
    a.set(xlabel='核心数 n',ylabel='平均加速比',xticks=ns,xlim=(.72,5.32),ylim=(.45 if q==3 else .7,5.48))
    a.legend(loc='upper left',ncol=1,handlelength=2.7)
    record(f'q{q}_mean',rs)
    save(f,q,f'q{q}_mean','每图先求相对原始整图单核的比值，再取100图算术平均；Q3无L2线固定Q3方案',
         ['求解/规范化数据/combined/main.csv'] if q<3 else ['数据/l2_patch_60_62/q3_latest_500.csv.xz'])

f,a=figure();rs=[]
for n in range(2,6):
    x=np.sort(vec(1,n));y=np.arange(1,101)/100
    a.step(np.r_[x[0],x],np.r_[0,y],where='post',label=f'{n} 核',**core_style(n))
    rs += [{'n':n,'rank':i+1,'speedup':xx,'fraction':yy} for i,(xx,yy) in enumerate(zip(x,y))]
a.set(xlabel='逐图加速比',ylabel='累计算例比例',ylim=(0,1.035),xlim=(0,6.65))
a.yaxis.set_major_formatter(PercentFormatter(1));a.legend(loc='lower right',ncol=2,handlelength=2.8)
record('q1_distribution',rs);save(f,1,'q1_distribution','二至五核全部100图的经验累计分布',['求解/规范化数据/combined/main.csv'])

# Replaces near-uniform 100-row heat map by three interpretable attainment curves.
T=read(D/'anytime.csv');rs=[]
for second in range(0,601,30):
    rows=[r for r in T if r['q']=='1' and r['n']=='5' and int(r['seconds'])==second]
    assert len(rows)==100
    available=[r for r in rows if r['makespan']!='' and r['has_solution'].lower()=='true']
    within=sum(float(r['makespan'])<=1.05*float(lookup[r['case'],1,5]['makespan']) for r in available)
    exact=sum(float(r['makespan'])==float(lookup[r['case'],1,5]['makespan']) for r in available)
    rs.append({'seconds':second,'total_cases':100,'available':len(available),'within_five_percent':within,'at_final':exact})
f,a=figure((6.35,3.75));tt=[r['seconds'] for r in rs]
for key,label,c,ls,marker in [('available','取得可用解',INK,':','s'),('within_five_percent','距最终周期不超过 5%',M,'--','D'),('at_final','达到最终周期',S,'-','o')]:
    yy=[r[key] for r in rs];a.step(tt,yy,where='post',color=c,ls=ls,lw=1.6,label=label)
    for pos in [1,4,10,20]:a.plot(tt[pos],yy[pos],marker=marker,ms=4,mfc='white',mec=c,mew=.85)
    a.annotate(str(yy[1]),(30,yy[1]),xytext=(8,8),textcoords='offset points',color=c,fontsize=8.5,va='center')
a.set(xlabel='本次运行累计用时 / 秒',ylabel='算例数（共 100 图）',xlim=(0,612),ylim=(0,105),xticks=[0,60,120,180,300,450,600],yticks=[0,20,40,60,80,100])
a.axvline(30,color=wash(INK,.2),lw=.6,ls=':');a.legend(loc='lower right',handlelength=2.8)
record('q1_anytime',rs);save(f,1,'q1_anytime','每30秒采样；尚无解不算达标，最终周期是已记录终值而非理论最优',['求解/规范化数据/combined/anytime.csv','求解/规范化数据/combined/main.csv'])

f,a=figure((6.35,3.7),grid=None);x=vec(1,5,'global_lower');y=vec(1,5,'makespan')
lo=min(x.min(),y.min())*.75;hi=max(x.max(),y.max())*1.25
# Redundant colour encoding is removed: relation is already shown by the two axes.
a.scatter(x,y,s=23,facecolor=wash(S,.5),edgecolor=S,lw=.55,zorder=3)
a.plot([lo,hi],[lo,hi],color=INK,lw=1,ls='--',label='$U=L$')
a.plot([lo,hi/2],[2*lo,hi],color=wash(INK,.35),lw=.85,ls=':',label='$U=2L$')
a.set(xscale='log',yscale='log',xlim=(lo,hi),ylim=(lo,hi),xlabel='全局下界 L / 周期',ylabel='五核可行周期 U / 周期')
a.grid(which='major',color=wash(INK,.10),lw=.5);a.legend(loc='upper left',handlelength=2.8)
record('q1_bound',[{'case':c,'lower':xx,'makespan':yy,'lower_over_makespan':xx/yy} for c,xx,yy in zip(CASES,x,y)])
save(f,1,'q1_bound','对数坐标上的100个可行周期与全局下界；U=2L仅为阅读参照',['求解/规范化数据/combined/main.csv'])

f,a=figure((6.35,3.75));ys=[vec(1,5),vec(2,5)];offset=np.linspace(-.095,.095,100)
for i in range(100):a.plot([1+offset[i],2+offset[i]],[ys[0][i],ys[1][i]],color=wash(INK,.3),alpha=.4,lw=.55,zorder=1)
bp=a.boxplot(ys,positions=[1,2],widths=.38,patch_artist=True,showfliers=False,
             medianprops={'color':INK,'lw':1.5},whiskerprops={'color':GRAY,'lw':.75},capprops={'color':GRAY,'lw':.75})
for box,c in zip(bp['boxes'],[S,M]):box.set(facecolor=wash(c,.12),edgecolor=c,linewidth=.85)
for j,y in enumerate(ys):a.scatter(j+1+offset,y,s=14,facecolor='white',edgecolor=[S,M][j],lw=.65,zorder=3)
a.set(xticks=[1,2],xticklabels=['第一问：子图级任务','第二问：核心级任务'],ylabel='五核逐图加速比',xlim=(.55,2.5),ylim=(1.15,9.25))
note(f,'细线连接同一算例在两问中的结果。')
record('q2_distribution',[{'case':c,'q1_speedup':p,'q2_speedup':q} for c,p,q in zip(CASES,*ys)])
save(f,2,'q2_distribution','同图两问各自最优方案配对，保留100个结果和箱线统计',['求解/规范化数据/combined/main.csv'])

f,a=figure((6.35,3.7),grid=None)
delta=(vec(2,5,'added_copy_bytes')-vec(1,5,'added_copy_bytes'))/1e6
gain=100*(1-vec(2,5,'makespan')/vec(1,5,'makespan'))
a.axhline(0,color=INK,lw=.9,ls=(0,(5,3)));a.axvline(0,color=INK,lw=.9,ls=(0,(5,3)))
for mask,color in [(delta<0,S),(delta>0,M),(delta==0,GRAY)]:
    a.scatter(delta[mask],gain[mask],s=26,facecolor=wash(color,.55),edgecolor=color,lw=.7,zorder=3)
a.set(xscale='symlog',xlim=(min(-1,float(delta.min())*1.5),max(1,float(delta.max())*1.5)),ylim=(min(-2.5,float(gain.min())*1.5),max(5,float(gain.max())*1.12)),xlabel='额外 COPY 变化：第二问 − 第一问 / MB',ylabel='周期减少比例 / %')
a.set_xticks([-100,-10,-1,0,1,10]);a.set_xticklabels(['−100','−10','−1','0','1','10'])
a.grid(which='major',color=wash(INK,.1),lw=.45);a.set_axisbelow(True)
a.text(.02,.96,'减少搬运 · 缩短周期',transform=a.transAxes,color=S,fontsize=9,ha='left',va='top')
a.text(.98,.96,'增加搬运 · 缩短周期',transform=a.transAxes,color=M,fontsize=9,ha='right',va='top')
note(f,'横轴采用对称对数刻度；MB = 10⁶ 字节；虚线表示变化为0。')
record('q2_copy',[{'case':c,'copy_difference_MB':d,'cycle_reduction_percent':g} for c,d,g in zip(CASES,delta,gain)])
save(f,2,'q2_copy','全部100图的搬运差与相对Q1周期减少比例，两个轴都保留零和负值',['求解/规范化数据/combined/main.csv'])

src=[r for r in read(D/'source_summary.csv') if r['q']=='2' and r['source'] in ['b','s','m']];src.sort(key=lambda r:['b','s','m'].index(r['source']))
f,a=figure((6.35,2.75),grid='x');a.spines['left'].set_visible(False)
for i,(r,c) in enumerate(zip(src,[INK,S,M])):
    count=int(r['evaluations']);n=int(r['makespan_improvements'])
    a.barh(i,count,height=.40,color=wash(c,.10),edgecolor=c,lw=.7)
    a.barh(i,n,height=.40,color=c,edgecolor=c,lw=.7,hatch='///')
    a.text(count+320,i,f'{n:,} / {count:,}  ({n/count:.2%})',va='center',fontsize=9,color=c)
a.set(xlim=(0,22700),ylim=(-.65,2.65),yticks=range(3),yticklabels=['基础 B','结构 S','驻留 M'],xlabel='候选评价次数')
a.invert_yaxis();a.xaxis.set_major_locator(MaxNLocator(5));a.tick_params(axis='y',length=0)
note(f,'深色段表示周期改善次数；右侧依次为改善次数 / 评价次数及改善比例。',space=.11)
record('q2_sources',[{'source':r['source'],'evaluations':r['evaluations'],'makespan_improvements':r['makespan_improvements'],'rate':int(r['makespan_improvements'])/int(r['evaluations'])} for r in src])
save(f,2,'q2_sources','实际来源机会分配后的计数，不是关闭来源的因果贡献',['求解/规范化数据/combined/source_summary.csv'])

f,a=figure((6.35,3.75));rs=[]
for n in range(1,6):
    ratios=vec(3,n,'cache_speedup');reduction=100*(1-1/ratios);order=np.argsort(reduction);values=reduction[order]
    a.plot(np.arange(1,101),values,label=f'{n} 核',**core_style(n))
    rs.extend({'n':n,'rank':j+1,'case':CASES[i],'cache_ratio':ratios[i],'time_reduction_percent':reduction[i]} for j,i in enumerate(order))
a.set(xlabel='算例按时间缩短幅度从小到大排列的名次',ylabel='开启 L2 后执行时间缩短 / %',xlim=(1,100),ylim=(-1,53),xticks=[1,20,40,60,80,100])
a.axhline(0,color=wash(INK,.5),lw=.7,ls='--');a.legend(loc='upper left',ncol=2,handlelength=2.8)
note(f,'每条线含100个同方案配对；各核数分别排序，0%表示执行时间未缩短。')
record('q3_pairs',rs);save(f,3,'q3_pairs','同方案开启L2后的执行时间缩短百分比，按核数分别排序展示100个算例',['数据/l2_patch_60_62/q3_latest_500.csv.xz'])

f,a=figure((6.35,3.5));xx=vec(3,5,'cache_hit_rate');ratio=vec(3,5,'cache_speedup');yy=100*(1-1/ratio)
a.scatter(xx,yy,s=25,facecolor=wash(F,.45),edgecolor=F,lw=.6,zorder=3)
a.axhline(0,color=INK,ls='--',lw=.8);a.set(xlabel='L2 字节命中率',ylabel='开启 L2 后执行时间缩短 / %',ylim=(-1.5,max(yy)*1.12),xlim=(-.02,max(.75,max(xx)*1.05)))
a.xaxis.set_major_formatter(PercentFormatter(1))
i=int(np.argmax(yy));a.annotate('算例 '+CASES[i][-3:],(xx[i],yy[i]),xytext=(-7,11),textcoords='offset points',ha='right',color=F,fontsize=9)
note(f,'每点为五核下同一完整方案的缓存开关对照；0%表示执行时间未缩短。')
record('q3_hit_gain',[{'case':c,'hit_rate':x,'cache_ratio':r,'time_reduction_percent':y} for c,x,r,y in zip(CASES,xx,ratio,yy)])
save(f,3,'q3_hit_gain','五核同方案L2字节命中率与执行时间缩短百分比，保留全部100个算例',['数据/l2_patch_60_62/q3_latest_500.csv.xz'])

study=read(ST/'cache_parameter_grid.csv');cs=['case_001','case_080','case_006','case_044','case_004','case_046'];caps=[262144,1048576,4194304];bws=[60,250,500]
matrices=[];rs=[]
for c in cs:
    data=[r for r in study if r['case']==c and r['mode']=='fixed_plan']
    assert len(data)==9
    z=np.array([[float(next(r for r in data if int(r['capacity_bytes'])==cap and int(r['bandwidth_bytes_per_cycle'])==bw)['makespan_cycles']) for bw in bws] for cap in caps]);matrices.append(z)
    rs.extend({'case':c,'capacity_bytes':cap,'bandwidth_bytes_per_cycle':bw,'makespan_cycles':z[i,j],'relative_to_study_default':z[i,j]/z[1,1]} for i,cap in enumerate(caps) for j,bw in enumerate(bws))
ratios=np.concatenate([(z/z[1,1]-1).flat for z in matrices]);vmin=min(-.05,float(min(ratios)));vmax=max(.05,float(max(ratios)))
cm=LinearSegmentedColormap.from_list('ink_response',[S,'#FFFFFF',F])
f,axes=plt.subplots(2,3,figsize=(6.6,5.25),layout='constrained')
for a,c,z in zip(axes.flat,cs,matrices):
    im=a.pcolormesh(np.arange(-.5,3,1),np.arange(-.5,3,1),z/z[1,1]-1,cmap=cm,norm=TwoSlopeNorm(vmin=vmin,vcenter=0,vmax=vmax),shading='flat',rasterized=False)
    a.set(xlim=(-.5,2.5),ylim=(2.5,-.5))
    for i in range(3):
        for j in range(3):
            rgb=cm(im.norm(z[i,j]/z[1,1]-1))[:3];light=.2126*rgb[0]+.7152*rgb[1]+.0722*rgb[2]
            a.text(j,i,f'{z[i,j]/1000:.2f}',ha='center',va='center',fontsize=9,color='white' if light<.50 else INK)
    a.add_patch(Rectangle((.5,.5),1,1,fill=False,edgecolor=INK,lw=1.25))
    a.set(xticks=range(3),xticklabels=bws,yticks=range(3),yticklabels=['0.25','1','4'],title='算例 '+c[-3:])
    a.set_xticks(np.arange(-.5,3,1),minor=True);a.set_yticks(np.arange(-.5,3,1),minor=True);a.grid(which='minor',color=wash(INK,.25),lw=.4);a.tick_params(which='both',length=0)
    for sp in a.spines.values():sp.set_visible(False)
    if a in axes[1]:a.set_xlabel('L2 带宽 /（B/周期）',fontsize=9)
    if a in axes[:,0]:a.set_ylabel('L2 容量 / MiB',fontsize=9)
cb=f.colorbar(im,ax=list(axes.flat),orientation='horizontal',fraction=.065,pad=.06,shrink=.83,aspect=35)
cb.solids.set_rasterized(False)
cb.set_label('相对默认配置的执行时间变化（负值更短，正值更长）',fontsize=9);cb.ax.tick_params(labelsize=8)
cb.ax.xaxis.set_major_formatter(PercentFormatter(1))
note(f,'格内数字：千周期；每个算例的9格固定同一方案。\n黑框：默认配置1 MiB、250 B/周期；MiB = 2²⁰ 字节。',space=.115)
record('q3_parameters',rs);save(f,3,'q3_parameters','54个固定方案格点，颜色为相对默认配置的执行时间变化，0为默认；格内标注千周期',['求解/规范化数据/studies/cache_parameter_grid.csv'])

(HERE/'RESULT_FIGURES.json').write_text(json.dumps({'theme':THEME,'figures':manifest,'main_counts':{'q1':500,'q2':500,'q3':500},'sources_unchanged':True},ensure_ascii=False,indent=2),encoding='utf8')
print('Result figures:',len(manifest),'all saved at their original manuscript locations')
