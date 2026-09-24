"""Team-wide derived tables from the original successfully verified collect."""
import csv
import json
import statistics as st
from collections import Counter
from pathlib import Path
from build_snapshot import BASE,read,put,stage_rows,seconds,key,table_csv,utc

root=BASE/'team_collection_20260924_verified'
out=root/'merged/report'
report=read(out/'report.json')
if not report['formal_complete'] or report['valid']!=1400 or report['independent_checks']!=1400 or report['failures_or_missing']:
    raise ValueError('Original full collect has not passed')
idx=read(root/'merged/merged_index.json')
selected={tuple(e['key']):read(e['summary']) for e in idx['chosen']}
pairs={tuple(e['key']):read(e['summary']) for e in idx['pairs']}
if len(selected)!=1400 or len(pairs)!=500:raise ValueError('Team coverage')
with (out/'per_case.csv').open(encoding='utf-8-sig',newline='') as f:
    rows=list(csv.DictReader(f))
for r in rows:
    for k in r:
        if k not in ['case','status','pair_status']:r[k]=None if r[k]=='' else float(r[k])
    r['q']=int(r['q']);r['n']=int(r['n'])
cov={};ref={};phases={};costs=[];policies=[]
for shard in [0,1]:
    r=root/f'shard_{shard}/auto'
    manifest=read(r/'campaign.json');policy=read(r/'refinement_policy.json')
    policies.append(dict(shard=shard,workers=manifest.get('execution_override',{}).get('workers',manifest['identity']['args']['workers']),
        original_workers=manifest['identity']['args']['workers'],refinement_policy=policy,python=manifest['hardware']['python'],
        deadline_epoch=manifest['deadline_epoch']))
    base={}
    for ph in ['coverage','coverage_retry','refinement','pairs']:
        data=stage_rows(r,ph);phases[shard,ph]=data
        if ph=='coverage':base.update(data)
        if ph=='coverage_retry':base.update({k:v for k,v in data.items() if v['status']=='ok'})
        if ph=='refinement':ref.update(data)
        costs.append(dict(shard=shard,stage=ph,completed=len(data),valid=sum(s['status']=='ok' for s in data.values()),
             failed=sum(s['status']!='ok' for s in data.values()),job_seconds=sum(seconds(s) for s in data.values()),
             failed_job_seconds=sum(seconds(s) for s in data.values() if s['status']!='ok'),
             timeout_valid=sum(s.get('hard_timeout',False) and s['status']=='ok' for s in data.values()),
             timeout_without_valid=sum(s.get('hard_timeout',False) and s['status']!='ok' for s in data.values())))
    if set(cov)&set(base):raise ValueError('Overlapping shards')
    cov.update(base)
improvements=[]
for k,s in sorted(selected.items()):
    b=cov[k];r=ref.get(k)
    improvements.append(dict(case=k[0],q=k[1],n=k[2],coverage_status=b['status'],coverage_makespan=b['makespan'],selected_status=s['status'],
      selected_makespan=s['makespan'],coverage_over_selected=b['makespan']/s['makespan'],relative_makespan_reduction=1-s['makespan']/b['makespan'],
      coverage_added_copy_bytes=b['added_copy_bytes'],selected_added_copy_bytes=s['added_copy_bytes'],refinement_ran=r is not None,
      refinement_status=r['status'] if r else 'not_planned',refinement_hard_timeout=r.get('hard_timeout') if r else None,
      coverage_solve_seconds=seconds(b),refinement_solve_seconds=seconds(r) if r else 0,end_to_end_solve_seconds=seconds(b)+(seconds(r) if r else 0)))
table_csv(out/'improvements.csv',list(improvements[0]),improvements)
tails=[];groups={}
for q in [1,2,3]:
    rs=sorted([r for r in rows if r['q']==q and r['n']==5],key=lambda r:(r['speedup'],r['case']))
    v=[r['speedup'] for r in rs];med=st.median(v);lo=9;p10=v[lo]+.9*(v[lo+1]-v[lo])
    for rank,r in enumerate(rs,1):
        s=selected[key(r)];cert=s['certificate']
        tails.append({**r,**s['features'],**{k:cert[k] for k in ['compute_path','compute_load','compulsory_ddr','global_lower']},
          'rank_ascending':rank,'median_speedup':med,'mean_gap_contribution_vs_median':(med-r['speedup'])/100})
    groups[q]=dict(count=100,mean=st.mean(v),median=med,p10=p10,worst_case=rs[0]['case'],worst=v[0],below1=sum(x<1 for x in v),missing=0,
        bottom10_cases=[r['case'] for r in rs[:10]],bottom10_gap_contribution=sum((med-x)/100 for x in v[:10]),other90_mean=st.mean(v[10:]))
table_csv(out/'lower_tail.csv','q,n,case,rank_ascending,speedup,makespan,baseline,median_speedup,mean_gap_contribution_vs_median,added_copy_bytes,partition_added_copy_bytes,spill_added_copy_bytes,cache_hit_rate,ops,components,max_component,compute_path,compute_load,compulsory_ddr,global_lower,ratio_upper'.split(','),tails)
prefix=[];aggregates={}
for (sh,ph),data in phases.items():
    if ph=='pairs':continue
    for k,s in sorted(data.items()):
        state=read(Path(s['job'])/'progress.json');seed=cov[k]['makespan'] if ph=='refinement' else None
        choices=[('evaluations',v) for v in [3,8,16,24]]+[('seconds',v) for v in [5,10,20,30]]
        if seed is not None:choices.insert(0,('seed_at_zero',0))
        for kind,cut in choices:
            vals=[] if seed is None else [seed]
            if kind!='seed_at_zero':vals.extend(a['makespan'] for a in state.get('attempts',[]) if a.get('status')=='ok' and a.get('index' if kind=='evaluations' else 'completed_seconds',float('inf'))<=cut)
            prefix.append(dict(case=k[0],q=k[1],n=k[2],stage=ph,cutoff_kind=kind,cutoff_value=cut,best_makespan=min(vals) if vals else None,has_valid_incumbent=bool(vals)))
table_csv(out/'budget_prefixes.csv',list(prefix[0]),prefix)
for cut in [5,10,20,30]:
    rs=[r for r in prefix if r['stage']=='refinement' and r['cutoff_kind']=='seconds' and r['cutoff_value']==cut]
    aggregates[cut]=dict(count=len(rs),improved=sum(r['best_makespan']<cov[key(r)]['makespan'] for r in rs),
        mean_coverage_over_prefix=st.mean(cov[key(r)]['makespan']/r['best_makespan'] for r in rs))
totals=[]
for q,n in [(0,1),(3,1)]+[(q,n) for q in [1,2,3] for n in [2,3,4,5]]:
    ss=[s for (c,qq,nn),s in selected.items() if qq==q and nn==n]
    totals.append(dict(q=q,n=n,count=len(ss),makespan_sum=sum(s['makespan'] for s in ss),
        scheduled_copy_bytes=sum(s['scheduled_copy_bytes'] for s in ss),added_copy_bytes=sum(s['added_copy_bytes'] for s in ss),
        partition_added_copy_bytes=sum(s['partition_added_copy_bytes'] for s in ss),spill_added_copy_bytes=sum(s['spill_added_copy_bytes'] for s in ss)))
table_csv(out/'metric_totals.csv',list(totals[0]),totals);table_csv(out/'stage_costs.csv',list(costs[0]),costs)
cache_rows=[{k:r[k] for k in ['case','n','makespan','no_l2_makespan','cache_speedup','cache_hit_rate','spill_added_copy_bytes','pair_status']} for r in rows if r['q']==3]
table_csv(out/'cache_pairs.csv',list(cache_rows[0]),cache_rows)
ratios=[r['cache_speedup'] for r in cache_rows]
cache=dict(count=500,mean_ratio=st.mean(ratios),median_ratio=st.median(ratios),positive=sum(v>1 for v in ratios),tie=sum(v==1 for v in ratios),
    negative=[r for r in cache_rows if r['cache_speedup']<1],mean_hit_rate=st.mean(r['cache_hit_rate'] for r in cache_rows),
    best5=sorted(cache_rows,key=lambda r:r['cache_speedup'],reverse=True)[:5])
changed=[r for r in improvements if r['coverage_over_selected']>1]
nogain=[r for r in improvements if r['refinement_ran'] and r['coverage_over_selected']==1]
stats=dict(groups=groups,costs=costs,policies=policies,cache=cache,prefixes=aggregates,improvements=len(changed),ties=1400-len(changed),
    no_makespan_gain_refinement_count=len(nogain),no_makespan_gain_refinement_seconds=sum(r['refinement_solve_seconds'] for r in nogain),
    best_improvements=sorted(changed,key=lambda r:r['coverage_over_selected'],reverse=True)[:8])
put(out/'analysis_metrics.json',stats)

def f(x,d=4):return f'{x:,.{d}f}'
def tab(h,rr):return '\n'.join(['| '+' | '.join(h)+' |','|'+'|'.join(['---']*len(h))+'|']+['| '+' | '.join(map(str,r))+' |' for r in rr])
text=['# ORION day01：两机100图最终合并报告',
    '**100张官方图已完成：1400/1400主记录、500/500同方案缓存对照、1400/1400主记录统一独立验证通过，formal_complete=true，缺失为0。** 两片最终标准transfer分别在新根unpack，再由原campaign collect合并与验证；没有按分数挑选重复结果，没有把阶段index冒充final。',
    '本轮是用户授权的两机、混合worker执行：片0奇数图为Python3.12.5、1→2→4 worker、改进27/54秒；片1偶数图为Python3.12.14、2 worker、改进30/60秒。算法、官方评估器和配置的已有版本标识一致。原各机容量校准和截止都保留。这是该执行政策的完整成绩，不是各图严格相同墙钟预算、单一主机负载的受控算法比较。',
    '## 三问 1–5 核逐图加速比均值',
    '各点先逐图计算T1/Tk再取100图算术平均。Q1/Q2单核依原始基线定义为1，Q3单核使用实际记录；没有新造Q1/Q2独立单核作业。',
    tab(['问题','1核','2核','3核','4核','5核','每点图数'],[[f'Q{q}']+[f(report['groups'][f'q{q}_n{n}']['mean_speedup']) for n in range(1,6)]+[100] for q in [1,2,3]]),
    tab(['问题','5核均值','中位数','P10','最差图 / 倍数','低于1倍','缺失'],[[f'Q{q}',f(g['mean']),f(g['median']),f(g['p10']),g['worst_case']+' / '+f(g['worst']),g['below1'],0] for q,g in groups.items()]),
    'P10按(N−1)×0.1线性插值。原单核基线包含调度和存储成本，个别图相对该基线超过5倍不等于突破五核计算上限，更不能解释为求解worker并发的影响。',
    '## 为什么平均上不去',
    '三问最差都是case_016，5核仍只有1倍；case_024也在约1.1倍。低尾还有case_048/064/086，以及片0的case_051/005/047/035/085/075。下面是全体100图最低10%（10张），不会删除它们或改变分母。贡献为(本问题5核中位数−本图speedup)/100，单位是算术平均的倍数差。',
    tab(['问题','图','倍数','相对中位数的均值差贡献'],[[f"Q{r['q']}",r['case'],f(r['speedup']),f(r['mean_gap_contribution_vs_median'],6)] for r in tails if r['rank_ascending']<=10]),
    tab(['问题','全100图均值','中位数','最低10图贡献和','其余90图均值'],[[f'Q{q}',f(g['mean']),f(g['median']),f(g['bottom10_gap_contribution'],6),f(g['other90_mean'])] for q,g in groups.items()]),
    '最低10图解释的是相对中位数差距的一部分；其余90图也有正负贡献，不能把删除低分图后的均值当正式成绩。lower_tail.csv保留三问各100图共300行。',
    '## 好图、差图与具体证据',
    '以下summary/certificate是选中方案的实际证据。compute_path、compute_load、compulsory_ddr与global_lower为所用全局下界；candidate_*只约束当前候选，不能冒充全局最优界。U/L不是可承诺的提升倍数。',
    '**case_016：当前方案没有利用其他核。** Q3 5核Makespan7715523，等于单核基线；17995算子、单分量。global compute_path655140、compute_load1542995，当前core_load7714975。队友冻结的官方时间线显示仅core0执行，其他核内存峰值0；新增搬运/Spill/命中率均为0。其候选核负载接近完整串行工作量，说明当前分区/候选选择是直接问题。不能由“单连通分量”推断图本身完全不可并行；也不能把它归因于Spill。',
    '**case_024：负载不均比缓存命中率更能解释低速。** Q3 5核Makespan2227340，当前core_load1582213，对比均衡计算load下界510959约3.10倍；Spill0、缓存命中约46.66%。同方案缓存只把2229400降到2227340，改善约0.09%。负载/依赖调度限制与现有证据一致；没有独立反事实证明每一部分等待的准确比例。',
    '**case_051与case_005：通信和数据移动代价。** case_051 Q1 5核380494、1.5969倍，global_lower121416，candidate_core_load223853、candidate_communication308214；新增复制9045058B、Spill0。case_005 Q2 5核41763，candidate_io29235.67高于candidate_core_load15978，新增复制1420726B、Spill0。应优先检查分区切边和布局，而非一概增加缓存容量。',
    '**case_048与case_064：关键路径、跨核依赖及固定成本。** case_048 Q3全局path75960高于load27907.2，candidate_communication90248，实际116660；case_064全局path3528、candidate_communication5528、实际9601。现有路径界与通信界支持其并行收益有限，单纯增加候选调用数未必能接近5倍。',
    '**case_084 / 059：结构给了分配机会，且基线不是理论最优。** case_084 Q3 5核391700，相对2507412单核为6.4014倍；1077分量、最大8算子，candidate_core_load253428接近compute_load253310.4，命中0、Spill0，所以高分不是缓存带来。case_059 Q2 5核150455、global_lower147558.4，U/L约1.0196，继续搜索的已证上界空间较小。',
    '**case_092 / 083：改进确实产生了可测收益。** case_092 Q1 5核2438012→915907，新增搬运131186400→10301824B；case_083 Q1 5核542671→258241，新增搬运27912000→4991360B。搬运减少与Makespan改善同步，但这是追加预算后的阶段收益，不是同预算算法对照。',
    '大Spill还集中在部分大图，例如case_067 Q3 5核189630464B，但其U/global_lower约1.1024；有Spill不自动等于最差尾部。内存结论仅使用原官方峰值与合法性检查，未另做内存分配重放，也没有把主机进程内存等同于模拟NPU内存。',
    '## 改进、总成本和预算前缀',
    f"1400主键中，{len(changed)}项Makespan降低、{1400-len(changed)}项持平、0项退化、0项缺失。两片共1248改进终态，1247有效、1失败后保留覆盖；其中{len(nogain)}项没有降低Makespan（包含失败回退/仅复制改善），消耗{f(sum(r['refinement_solve_seconds'] for r in nogain),3)}作业秒。",
    tab(['片','阶段','完成','有效','失败','作业秒','失败秒','触帽有效/无可行解'],[[v['shard'],v['stage'],v['completed'],v['valid'],v['failed'],f(v['job_seconds'],3),f(v['failed_job_seconds'],3),f"{v['timeout_valid']}/{v['timeout_without_valid']}"] for v in costs]),
    '作业秒为各逻辑作业total_job_seconds之和，并发时不等于日历耗时；片0继承/中断两段仅计一次。片0覆盖14:23:35–16:18:19、重试16:18:19–16:27:23、改进16:27:23–19:37:15、配对19:37:20–19:40:36、验证19:40:36–19:42:29（北京时间）。片1原监督于19:07:46结束；详细阶段时间和各自预算见两片原报告与时钟。团队收集验证另外记录在COLLECTION_STATUS.json，未重跑求解器。',
    tab(['改进时间前缀','逻辑配置数','已改善','平均覆盖T/前缀最佳T'],[[str(c)+'秒',v['count'],v['improved'],f(v['mean_coverage_over_prefix'],6)] for c,v in aggregates.items()]),
    '预算CSV统一从两片原progress重算，另含3/8/16/24评估与覆盖/重试各阶段。逻辑refinement的已验证覆盖种子明确为t=0可用；覆盖成本另记不为零。只用截止前实际成功评估，超过实际停止帽只沿用已经取得的最佳值，不外推新结果。不同机器/worker/27与30秒帽会影响墙钟前缀，不把该轨迹当严格受控同预算比较。',
    '## 同一方案的缓存因果比',
    f"500对全部使用对应Q3选中方案，在无L2(Q2)与有L2(Q3)下对照。逐对T_noL2/T_L2算术平均{f(cache['mean_ratio'],6)}倍，中位数{f(cache['median_ratio'],6)}倍；{cache['positive']}正收益、{cache['tie']}持平、{len(cache['negative'])}负收益。逐配置字节命中率的算术平均{cache['mean_hit_rate']:.4%}，不是全体访问字节加权命中率。",
    tab(['核数','无L2平均T1/T','有L2平均T1/T','逐图缓存比均值','配对数'],[[n,f(report['groups'][f'q3_n{n}']['same_plan_no_l2_mean_speedup']),f(report['groups'][f'q3_n{n}']['mean_speedup']),f(report['groups'][f'q3_n{n}']['mean_same_plan_cache_speedup'],6),100] for n in range(1,6)]),
    '唯一负收益是case_046双核：同一方案113936→113944（增加8，约0.0070%），比值0.99992979。结果通过原验证，原样保留，不能删除或改为1。精确原因仍需缓存访问/调度路径分析，不能把细小差异擅自当成测量噪声抹掉。',
    tab(['高收益图/核','noL2 T','L2 T','缓存比','命中率'],[[r['case']+' n'+str(r['n']),int(r['no_l2_makespan']),int(r['makespan']),f(r['cache_speedup'],6),f(r['cache_hit_rate']*100,2)+'%'] for r in cache['best5']]),
    'case_046五核接近1.99倍、case_090约1.77倍、case_044约1.74倍，缓存对这些图有效；case_084虽总加速比6.4倍，命中0、同方案缓存比1。多数配置的收益接近1，均值被少数高收益图抬高，不能承诺每图得到平均改善。独立优化的Q2/Q3方案差值不参与这项因果比。',
    '## Makespan / DDR / Spill全量汇总',
    '下表每组100图，Makespan沿用官方时间单位，数据移动为字节。scheduled_copy_bytes是官方逻辑搬运量；Q3情况下不等于命中扣除后的真实DDR miss字节。总量用于说明绝对成本，不能替代逐图T1/Tk平均。',
    tab(['配置','ΣMakespan','Σscheduled','Σ新增','Σ分区新增','ΣSpill'],[[f"Q{v['q']} n{v['n']}"]+[f"{v[k]:,}" for k in ['makespan_sum','scheduled_copy_bytes','added_copy_bytes','partition_added_copy_bytes','spill_added_copy_bytes']] for v in totals]),
    '## 保留的失败与执行限制',
    '片0初始覆盖3次失败均由原重试恢复。1→2切换case_043 Q3 n3接续子段初始化耗尽剩余9.7385秒，没有新可行解，但保留前段Makespan262943；该子段失败与前段证据完整保留，逻辑作业有效。case_091 Q3 n5改进54秒无首个有效评估，保留覆盖1865477。片1没有正式作业失败。未解决主键0；触帽有效方案与无可行解分开，不靠删除失败提高均值。',
    '两机外层team_status均出现process_failed/exit_code=null的状态不一致。片1内层watchdog exit_code=0；片0Python完成标记及700项最终验证完整。原状态保留、退出码未知不补造。团队collect另在本机对1400主记录和500同方案对照重新执行原合法性核验，完成证据不依赖外层标签。',
    '片0原最终快照的两条pairs引用带Windows扩展路径前缀，打包前已按原transfer.rewrite规则修正输出根引用。前一未发布包与失败接收根保留；实际团队collect使用新的接收根，不读取活跃源目录，不改任何数值、方案或官方输入。',
    '## 下一轮最多三项建议（尚未启动）',
    '1. 优先为case_016/024和case_051/005/047增加有针对性的分区、最大核负载与关键跨核边候选。指标是全量5核均值与P10同时提升；不能只看高分样本。风险是切边减少与负载均衡冲突。',
    '2. 用已有前缀轨迹改进初始化复用和预算分配，减少无Makespan收益作业的消耗，优先改善首评估耗尽预算的情况。保留原总预算，用同预算pilot验证提前停止是否错过后期改善，不能把迁移或复制视作免费计算。',
    '3. 把缓存/Spill策略资源投向case_046/090/044/057/073等同方案收益证据较强的图，同时防止复制量、UB/L1峰值恶化。必须保留同方案有/无L2对照及负收益键，命中率不是最终优化目标。',
    '下一算法版须两机协调同源、新根、同预算pilot；本轮day01已封存，不自动另跑，不混合新版本成绩。主计算截止2026-09-24 16:43:48 UTC、团队截止17:43:48 UTC均未延长。',
    '## 交付与复核',
    '两片完整标准transfer分卷分别在 ../shard_0/final/ 与 ../shard_1/final/。不同分卷大小不影响重组后的标准格式；按各自清单拼接，再用原transfer unpack到新空根。TEAM_REPRODUCE.md给出原collect命令。',
    '本目录per_case.csv为1400主记录，verification.json为1400统一主核验项；cache_pairs.csv为500同方案对照；improvements.csv1400行，lower_tail.csv300行，budget_prefixes.csv保留真实轨迹前缀，metric_totals.csv和stage_costs.csv保留汇总，原question_1/2/3.svg为完整100图曲线。完整选中方案另打包，不上传赛事平台。',
    '本次只执行原协议要求的接收、结果收集与原合法性验证，没有smoke、额外哈希/指纹测试、pytest、unittest、全仓审计或benchmark；没有改官方图/config/评估器，没有自动合并PR。']
(out/'REPORT.md').write_text('\n\n'.join(text)+'\n',encoding='utf8')
put(out/'TEAM_STATUS.json',dict(schema_version=1,iteration_id='day01',stage='combined_final',graphs=100,expected_main=1400,valid_main=1400,
    expected_pairs=500,valid_pairs=500,independent_checks=1400,formal_complete=True,failures_or_missing=[],
    refinement_completed=1248,refinement_valid=1247,refinement_failed=1,historical_failure_count=5,
    hard_timeout_valid=sum(c['timeout_valid'] for c in costs),hard_timeout_without_valid=sum(c['timeout_without_valid'] for c in costs),
    mixed_execution=True,policies=policies,reported_at_utc=utc()))
print(json.dumps(dict(groups=groups,cache={k:v for k,v in cache.items() if k!='best5'},improved=len(changed),costs=costs,prefixes=aggregates),ensure_ascii=True))
