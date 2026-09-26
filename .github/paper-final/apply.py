"""Apply the reviewed manuscript changes and summarize existing records only."""
from pathlib import Path
import subprocess, re, json
import pandas as pd
ROOT=Path.cwd(); W=ROOT/'20hw_myskill_distribution/20hw_myskill_distribution/workshop_v2'; P=W/'论文'; C=P/'章节内容'
OLD='bb9ef99b041a2715c97fcadbd018dce2fbd7239d'
subprocess.run(['git','fetch','--depth=1','origin',OLD],check=True)
names=['paper-review.sty','论文.tex','论文.pdf','摘要.tex','参考文献.bib','图片/workflow_mono_v3.pdf']
names += ['章节内容/'+n+'.tex' for n in ['01_问题重述','02_模型假设','03_关键性符号说明','04_问题一','05_问题二','06_问题三','90_模型评价与展望','99_附录.generated','方法补充','缓存事件补充']]
names += ['章节内容/数据表/'+n+'.tex' for n in ['appendix_results','appendix_pairs','q3_means','q3_pairs']]
for name in names:
 p=P/name;p.parent.mkdir(parents=True,exist_ok=True)
 p.write_bytes(subprocess.check_output(['git','show',OLD+':'+p.relative_to(ROOT).as_posix()]))
d=pd.read_csv(W/'数据/l2_patch_60_62/q3_latest_500.csv.xz',encoding='utf-8-sig')
if len(d)!=500 or d[['case','n']].drop_duplicates().shape[0]!=500:raise ValueError('Expected 500 unique complete pairs')
d['s']=d.reference_t1/d.makespan;d['r']=d.no_l2_makespan/d.makespan
q=(C/'06_问题三.tex').read_text(encoding='utf-8')
q=q.replace('实验分为三种口径：100 图的第三问主结果，同一第三问方案有无 L2 的配对结果，以及六张定向图在固定方案下的容量、带宽格点。三者分别刻画总体性能、固定方案缓存收益和定向参数响应。','在此基础上，进一步比较多尺度划分、通信感知归核及归属保持的拆分重排候选。主实验覆盖100图、五种核数；同方案缓存配对刻画固定方案的L2影响，六张定向图的固定方案容量、带宽格点刻画参数响应。')
q=q.replace(r'\subsubsection{同方案配对的识别量}',(ROOT/'.github/paper-final/q3-extra.tex').read_text(encoding='utf-8')+'\n'+r'\subsubsection{同方案配对的识别量}')
for a,b in {'1.1008':'1.1012','2.1222':'2.1307','3.0320':'3.0428','3.8376':'3.8586','4.5978':'4.6333','4.8565':'4.8798','66 图周期短于第二问、18 图相等、16 图更长':'73 图周期短于第二问、16 图相等、11 图更长','8293721.4':'8534644.76','1.0558':'1.0560','1.0077':'1.0082','77 图的周期缩短，23 图相等':'76 图的周期缩短，24 图相等'}.items():q=q.replace(a,b)
q=q.replace('第三问主结果的全局下界与当前五核周期给出的相对差距上界逐图平均为 $0.2248$；其中 6 图在 $1\\%$ 以内。该界由计算路径、Pipe负载和对全部可行方案成立的必要流量松弛得到。','')
q=q.replace('从主实验中定向选取六张图','定向选取六张图').replace('其中各图的默认配置格沿用对应主实验响应','各图的默认配置格作为该参数研究的参考点')
(C/'06_问题三.tex').write_text(q,encoding='utf-8')
a=(P/'摘要.tex').read_text(encoding='utf-8').replace('4.5978','4.6333').replace('1.0558','1.0560').replace('77图周期缩短、23图相同','76图周期缩短、24图相同')
a=a.replace('该类候选保持划分与归核不变，根据填充、重复未命中和淘汰事件调整完整子图的核内位置。','纯顺序候选保持划分与归核不变，按实际填充与淘汰窗口调整子图位置；结合多尺度划分、通信感知归核和归属保持的拆分重排，通过完整评价选择方案。')
(P/'摘要.tex').write_text(a,encoding='utf-8')
c=(C/'缓存事件补充.tex').read_text(encoding='utf-8');start=c.index('同方案配对中也存在很小的周期反例：')
c=c[:start]+'正式结果的500组同方案配对中，有L2周期均不高于无L2周期；这一观察不构成对所有图和方案的单调性证明。算例046五核同方案的有L2与无L2周期分别为 $49119$ 与 $95050$，周期比为 $1.9351$，字节命中率约为 $0.7132$。命题4刻画单段FIFO驻留期的条件；固定方案参数响应与同方案周期对照则说明，字节命中率与总体周期收益需要分别报告。候选评价同时检查驻留窗口与共享服务，仍以总体任务执行时间为主目标。\n'
(C/'缓存事件补充.tex').write_text(c,encoding='utf-8')
p=C/'04_问题一.tex';p.write_text(p.read_text(encoding='utf-8').replace('每个图、问题及核数配置的累计主机时间上限','自适应迭代阶段中，每个图、问题及核数配置的累计主机时间上限'),encoding='utf-8')
p=C/'02_模型假设.tex';p.write_text(p.read_text(encoding='utf-8').replace('缓存换出（Spill）','片上存储换出（Spill）'),encoding='utf-8')
p=C/'90_模型评价与展望.tex';p.write_text(p.read_text(encoding='utf-8').replace('基础构造在整个过程中保留探索机会。','基础构造在整个过程中保留探索机会，第三问还以多尺度和通信感知候选扩展方案选择。').replace('100 图主表反映给定题面配置和有限搜索预算下的方案表现','100 图主表反映固定硬件配置和有限候选搜索下的方案表现'),encoding='utf-8')
for fn,caption,label,cols,rows in [
 ('q3_means.tex','问题三各核数逐图加速比统计','q3_mean',r'核心数 & 样本数 & 平均加速比 & 中位加速比 & 最小加速比 & 最大加速比',[(int(n),len(g),g.s.mean(),g.s.median(),g.s.min(),g.s.max()) for n,g in d.groupby('n')]),
 ('q3_pairs.tex','第三问同一个方案有无 L2 的周期配对统计','q3_pairs',r'核数 & 配对数 & \shortstack{平均\\周期比} & \shortstack{中位\\周期比} & 改善 & 相同 & 退化 & \shortstack{平均字节\\命中率}',[(int(n),len(g),g.r.mean(),g.r.median(),int((g.r>1).sum()),int((g.r==1).sum()),int((g.r<1).sum()),g.cache_hit_rate.mean()) for n,g in d.groupby('n')])]:
 body='\n'.join(' & '.join(str(v) if isinstance(v,int) else f'{v:.4f}' for v in row)+r' \\' for row in rows)
 s='% 正式500组数据；逐图计算比值后取算术平均。\n'+r'\begin{table}[htbp]'+'\n'+rf'\caption{{{caption}}}\label{{tab:{label}}}'+'\n'+r'\centering\normalsize\setlength{\tabcolsep}{4pt}'+'\n'+r'\begin{tabular}{'+'r'*len(rows[0])+'}\n'+r'\toprule'+'\n'+cols+r' \\'+'\n'+r'\midrule'+'\n'+body+'\n'+r'\bottomrule\end{tabular}\end{table}'+'\n'
 (C/'数据表'/fn).write_text(s,encoding='utf-8')
s=(C/'数据表/appendix_results.tex').read_text(encoding='utf-8');seg=s.index(r'\caption{问题三');before=s[:seg];tail=s[seg:];active=[]
def row_match(m):
 case=int(m.group(1));g=d[d['case']==f'case_{case:03}'].set_index('n')
 return f'{case:03} & '+' & '.join(f'{int(g.loc[n,c]):,}' for n in active for c in ['makespan','added_copy_bytes'])+r'\\'
parts=re.split(r'(\\caption\{问题三逐例结果[^\n]*\n)',tail)
for i in range(len(parts)):
 if parts[i].startswith(r'\caption{问题三'):
  active=[1,2] if '1、2' in parts[i] else [3,4] if '3、4' in parts[i] else [5]
 elif active:parts[i]=re.sub(r'^(\d{3}) & .*?\\\\$',row_match,parts[i],flags=re.M)
(C/'数据表/appendix_results.tex').write_text(before+''.join(parts),encoding='utf-8')
s=(C/'数据表/appendix_pairs.tex').read_text(encoding='utf-8')
def pair_match(m):
 case,n=int(m.group(1)),int(m.group(2));r=d[(d['case']==f'case_{case:03}')&(d.n==n)].iloc[0]
 return f'{case:03} & {n} & '+' & '.join(f'{int(r[c]):,}' for c in ['no_l2_makespan','makespan','no_l2_added_copy_bytes','added_copy_bytes'])+f' & {r.cache_hit_rate:.6f}'+r'\\'
s=re.sub(r'^(\d{3}) & ([1-5]) & .*?\\\\$',pair_match,s,flags=re.M).replace('由 combined/pairs.csv 的 500 组实际同方案官方响应生成','由正式500组同方案完整评价记录生成')
(C/'数据表/appendix_pairs.tex').write_text(s,encoding='utf-8')
binding={'scope':'A题正式论文统一结果','source_commit':'f1574d71b7aa273d9971171ffbe9698ab6d792c2','q1_q2':'求解/规范化数据/combined/','q3':'数据/l2_patch_60_62/q3_latest_500.csv.xz','graphs':100,'q3_cases_by_cores':500,'reference':'逐图原始整图单核周期；先求逐图比值，再算术平均','paired_control':'同一完整方案，仅关闭L2；不使用第二问独立优选方案代替','parameter_study':'六图、每图固定方案的54个容量带宽格点；另有12个边界适配结果','timing':'自适应搜索时间曲线仅计当时已保存可用解；候选优选单独受限','manuscript':'论文/论文.tex','pdf':'论文/论文.pdf','report':'论文/批注文件夹/批注落实修改报告.md'}
(W/'CURRENT_PAPER_DATA.json').write_text(json.dumps(binding,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Manuscript and published-result tables updated; no solver or evaluator was executed.')
