"""Render evidence-linked ORION shard reports from completed result summaries."""
from build_snapshot import BASE,SOURCE,read,put,utc,table_csv
import csv
import shutil
from datetime import datetime,timezone,timedelta

def fmt(v,d=4):return '未记录' if v is None else f'{v:,.{d}f}'
def mdtable(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+['| '+' | '.join(map(str,r))+' |' for r in rows])

for stage in ['refinement_complete','final']:
    dest=BASE/'phase_publication_20260924/artifacts/shard_0'/stage
    m=read(dest/'analysis_metrics.json');status=read(dest/'PHASE_STATUS.json')
    final=stage=='final'; snap=SOURCE.parent/'snapshots'/stage/'auto'
    with (dest/'per_case.csv').open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    with (dest/'lower_tail.csv').open(encoding='utf-8-sig',newline='') as f:tail=list(csv.DictReader(f))
    with (dest/'improvements.csv').open(encoding='utf-8-sig',newline='') as f:imp=list(csv.DictReader(f))
    rowmap={(r['case'],int(r['q']),int(r['n'])):r for r in rows}
    text=[f'# ORION day01 片0：{"最终验证版" if final else "改进结束阶段版"}',
      '本报告只涵盖奇数编号的 **50 张官方图**。有效主记录 **700/700**；改进作业 **620/620** 有终态，其中 **619 有效、1 次未找到新可行解**。该失败键沿用有效覆盖方案，主记录没有缺失。',
      ('本版含 **250/250 同方案缓存对照、700/700 最终独立合法性验证**，缺失列表为空。`shard_complete=true`；`formal_complete=false`，因为尚未合并队友偶数50图。' if final else
       '本版冻结 coverage/retry/refinement，不含缓存配对；配对为 pending，`valid_pairs=0`、`independent_checks=0`、`final_verification_complete=false`。原进程在汇总期间继续完成配对与验证，另见同级 final/，本版不回填最终状态。'),
      f"冻结开始：{status['snapshot_started_at_utc']}；冻结完成：{status['snapshot_finished_at_utc']}。算法源码自通过 pilot 后未改；实际执行经历 1→2→4 worker，已获用户授权。下面的统计保留这项限制。",
      '## 三问 1–5 核结果',
      '每个点均先逐图计算原始单核基线 T1 / 当前 Makespan，再对50图取算术平均。Q1/Q2 的单核点依题意为1；Q3单核是实际求解记录。不能用平均T1/平均Tk替代。',
      mdtable(['问题','1核','2核','3核','4核','5核','每点有效图数'],[[f'Q{q}']+[fmt(m['report_groups'][f'q{q}_n{n}']['mean_speedup'])+'×' for n in range(1,6)]+['50'] for q in [1,2,3]]),
      mdtable(['问题','5核均值','中位数','P10','最差图 / 倍数','低于1倍','缺失'],[[f'Q{q}',fmt(g['mean']),fmt(g['median']),fmt(g['p10']),g['worst_case']+' / '+fmt(g['worst']),g['below1'],g['missing']] for q,g in m['groups'].items()]),
      'P10 使用排序后 (N−1)×0.1 位置的线性插值。这里的“核数”是被模拟 NPU 核数，与运行求解器的 worker 数不同。部分结果超过5倍，是相对包含原调度/访存成本的单核基线，不能解释为5个求解进程带来的硬件加速。',
      '## 改进阶段增加了多少收益',
      '700个主键中，**402个 Makespan 下降、298个持平、0个退化、0个缺失**；去掉50个固定基线后，对应650个优化配置为402下降、248持平。620个改进任务中，402下降、217有效但 Makespan 持平、1失败后保留覆盖；另外30个优化配置没有进入改进计划。持平项中有2个只减少了新增复制字节。',
      mdtable(['问题','覆盖阶段5核均值','改进后5核均值','均值增加'],[[f'Q{q}',fmt(m['coverage_means'][f'q{q}_n5']),fmt(m['groups'][str(q)]['mean']),fmt(m['groups'][str(q)]['mean']-m['coverage_means'][f'q{q}_n5'])] for q in [1,2,3]]),
      '这是同键从覆盖预算追加改进预算后的增量收益，预算并不相同；不能把它表述为同预算下新算法战胜旧算法。基线重试补齐的3条记录也不算算法性能提升。',
      mdtable(['图 / 配置','覆盖 Makespan','选中 Makespan','降低','新增复制字节：前→后'],[[f"{r['case']} Q{r['q']} n{r['n']}",r['coverage_makespan'],r['selected_makespan'],fmt(100*r['relative_makespan_reduction'],2)+'%',f"{r['coverage_added_copy_bytes']} → {r['selected_added_copy_bytes']}"] for r in m['best_improvements'][:6]]),
      '例如 case_083 Q1 5核从542671降至258241，同时新增复制从27912000降至4991360字节，通信减少与改进相伴。相反 case_095 Q2 2核在新增复制从0升到16588800字节时，Makespan仍从1042890降至573690：复制量本身不是唯一目标，负载分配、调度和数据复用要一起看。',
      '## 为什么有些图好，有些图差',
      '以下证据直接来自选中 summary 的 features/certificate 与官方数据移动结果。global_lower 是全局下界；candidate_core_load、candidate_communication、candidate_io、candidate_lower 只约束当前候选。U/global_lower 不能当作必然能实现的加速倍数。',
      '**较好图的特征与限制。** case_059 有64个分量、最大分量43个算子。Q2 5核 Makespan150455，全局下界147558.4、当前核负载下界148816，U/L约1.0196，说明该候选离所用全局下界已经较近；继续均匀增加搜索时间的余地有限。case_097同样有64个分量，Q2 5核 Makespan2108989、全局下界2060697.6，U/L约1.0234。多个较小分量有利于分配是与数据一致的解释，但不是所有图都满足的结论。',
      '**Q1最差的 case_051。** 5核仅1.5969倍，Makespan380494。它是1416算子的单分量图；计算路径下界51552、平均计算负载下界121416，而当前最大核负载223853、通信约束308214。新增复制9045058字节，Spill为0。当前候选通信与负载不均的证据比“只因串行路径”更强；这些数字支持优先检查分区切边和布局，但尚未用单因素实验证明因果。',
      '**Q2的 case_005。** 5核2.2895倍，Makespan41763；全局下界12776.4，候选IO下界29235.67高于候选核负载15978。新增复制1420726字节，Spill为0，说明数据移动值得优先排查，不能把这里的低速归咎于Spill。',
      '**Q3的 case_047 / case_085 / case_075。** 5核分别2.3124、2.3766、2.3869倍，均只有一个连通分量。case_047 的 Makespan141197、全局下界51874、候选核负载69095、候选IO15368.53，Spill为0；case_085 的 Makespan1341351、计算负载下界513043.2、候选核负载667280，改进仅完成3次评估。依赖就绪、调度空闲和负载布局都值得查，但仅凭粗下界还不能将剩余差距分解为确切的等待比例。',
      '**大 Spill 不一定主导最差尾部。** case_067 Q3 5核 Spill189630464字节，但 Makespan12989574 / 全局下界11783046.4≈1.1024；case_091 的覆盖方案 Spill42895872字节，U/L≈1.0385。它们应单独优化，却不是上面最差5图的共同解释。主机进程内存与官方模拟的存储容量也必须分开；报告没有独立重放内存分配，保留原官方 Step3 峰值检查的范围。',
      '## 哪些图把均值拉低',
      '下面列完整50图中的最低5图（10%）。贡献定义为 (本问题5核中位数−该图加速比)/50；是相对中位数的算术分解，不是删图建议。全量150行5核数据及正负贡献见 lower_tail.csv。',
      mdtable(['问题','图','5核倍数','相对中位数的均值差贡献'],[[f"Q{r['q']}",r['case'],fmt(float(r['speedup'])),fmt(float(r['mean_gap_contribution_vs_median']),6)] for r in tail if int(r['rank_ascending'])<=5]),
      mdtable(['问题','全部50图均值','中位数','最低5图贡献和','其余45图均值'],[[f'Q{q}',fmt(g['mean']),fmt(g['median']),fmt(g['bottom5_gap_contribution'],6),fmt(g['other45_mean'])] for q,g in m['groups'].items()]),
      'Q3中位数已到4.8563倍，但均值4.3187倍，最低5图贡献约0.2460个均值倍数；其余45图均值也只有4.5323倍，说明差距并非只来自5张极端图。Q1同样存在比Q2/Q3更强的通信/调度代价。应改善低尾，不能靠筛掉慢图或改分母抬高平均。',
      '## Makespan 与 DDR / Spill',
      '逐图 Makespan、基线、复制、Spill、命中率见 per_case.csv。下表为各问题5核50图的字节总和；scheduled_ddr 指官方计划中的数据移动字节，并非主机实测内存流量，也不等于所有缓存命中后的物理DDR事务量。',
      mdtable(['配置','计划总数据移动','新增复制合计','分区新增','Spill新增'],[[name]+[f"{v[k]:,}" for k in ['scheduled_ddr_sum','added_ddr_sum','partition_added_sum','spill_added_sum']] for name,v in m['selected_memory_bytes'].items()]),
      '## Q3 同方案缓存对照']
    if final:
        c=m['cache'];equal=sum(float(r['cache_speedup'])==1 for r in rows if r['q']=='3');zero=sum(float(r['cache_hit_rate'])==0 for r in rows if r['q']=='3')
        text += [f"250对使用同一选中方案，比较 Q2无L2 / Q3有L2 的 Makespan。逐对比值的算术平均 **{c['mean_ratio']:.6f}×**，中位数 **{c['median_ratio']:.6f}×**；低于1倍0对，恰好1倍{equal}对。命中率逐配置平均 **{c['mean_hit_rate']:.4%}**，零命中{zero}对。命中率未按访问次数加权。",
          mdtable(['核数','同方案无L2平均T1/T','有L2平均T1/T','逐图缓存比均值','对数'],[[n,fmt(m['report_groups'][f'q3_n{n}']['same_plan_no_l2_mean_speedup']),fmt(m['report_groups'][f'q3_n{n}']['mean_speedup']),fmt(m['report_groups'][f'q3_n{n}']['mean_same_plan_cache_speedup'],6),50] for n in range(1,6)]),
          f"5核命中率平均{c['n5_mean_hit_rate']:.4%}，同方案缓存比仅1.035694倍。case_001各核命中0且比值1，符合缺少可利用复用的解释；高命中也不保证同比例缩短总时间。case_047 5核命中41.0123%，实际同方案比为{float(rowmap[('case_047',3,5)]['cache_speedup']):.6f}倍，其当前下界由核负载而非IO主导，与计算/调度限制一致。",
          mdtable(['图 / 核数','无L2 Makespan','有L2 Makespan','同方案缓存比','命中率'],[[f"{r['case']} n{r['n']}",int(r['no_l2_makespan']),int(r['makespan']),fmt(r['cache_speedup'],6),fmt(r['cache_hit_rate']*100,2)+'%'] for r in c['top'][:5]]),
          '最明显的收益是 case_057 5核，18506→13380（1.3831倍）；case_073 5核3239271→2412229（1.3429倍）。缓存对少数图有效，但全体中位数接近1，所以单靠缓存很难显著提高总平均。独立优化的Q2与Q3方案可能不同，不能用它们的平均差作缓存因果收益。']
    else:text += ['**pending。** 本阶段没有配对结果，不给出缓存因果比。Q3的性能曲线和已有官方命中率可以描述，但独立优化的Q2/Q3差值不能证明缓存收益。最终配对另存 final/。']
    text += ['## 阶段耗时与预算前缀',
       '下表“作业秒”是各逻辑作业 total_job_seconds 之和，包含启动/结尾开销；多个worker并发时不等于日历时长。继承记录只计一次，case_043合并后的两段只计一次，不再加 refinement_interrupted 或旧根的副本。',
       mdtable(['阶段','完成 / 有效 / 失败','作业秒','其中失败作业秒','触帽有效 / 无可行解'],[[ph,f"{v['completed']} / {v['ok']} / {v['failed']}",fmt(v['job_seconds'],3),fmt(v['failed_job_seconds'],3),f"{v['timeout_valid']} / {v['timeout_without_valid']}"] for ph,v in m['costs'].items()]),
       '阶段时间线（北京时间，来自原根请求/结果写入时间和阶段标记）：覆盖14:23:35.827–16:18:19.508（约1小时54分44秒）；重试16:18:19.520–16:27:23.181（约9分4秒）；改进16:27:23.209–19:37:15.263（约3小时9分52秒，含迁移空档）。'+('配对19:37:20.542–19:40:36.272（约3分16秒）；最终验证19:40:36.324–19:42:29.625（约1分53秒）。' if final else '后续配对和验证未计入本阶段快照。'),
       '原改进帽保持普通27秒、大图54秒、最多256评估；覆盖预算按原容量校准，大图pilot180秒，原30秒/24次pilot策略没有更改。迁移没有增加任何逻辑作业的时间/评估额度。主计算硬截止仍为2026-09-24 16:43:48 UTC，团队截止17:43:48 UTC；manifest更早deadline及原单worker计算的改进截止都保留。',
       mdtable(['改进阶段时间前缀','逻辑配置数','已严格改善配置数','平均覆盖Makespan/前缀最佳'],[[str(cut)+'秒',v['count'],v['strictly_improved'],fmt(v['mean_coverage_over_prefix'],6)] for cut,v in m['refinement_prefixes'].items()]),
       'budget_prefixes.csv另含3/8/16/24评估前缀以及覆盖、重试各阶段记录。改进前缀从控制器已拥有的官方有效覆盖种子算起，明确 seed_at_zero；其覆盖成本并不为零。只用截止前真实成功评估，不把后来结果倒填；截止超过实际停机/评估帽时沿用停机前最佳，绝不推断额外搜索结果。失败子段的前段轨迹在当前逻辑progress中已经合并。',
       f"218个改进配置没有降低Makespan，共消耗{m['no_makespan_gain_refinement_seconds']:.3f}作业秒，占改进成本{m['no_makespan_gain_refinement_seconds']/m['costs']['refinement']['job_seconds']:.2%}（包括2个只降低复制和1个失败回退）。5秒已有169项改善，20秒351项、30秒379项，最终402项；这些前缀反映本次混合并发下的已保存轨迹，不能当作相同硬件负载的独立预算实验。",
       'per_case.csv 的 solve_seconds保留既有报告定义；失败后回退到覆盖的键不包含失败改进成本。improvements.csv显式给出覆盖加改进成本，首次覆盖失败/重试等总成本以本节为准，避免漏算失败。',
       '## 失败、切换和验证边界',
       '1. case_067 / case_079 / case_091 的单核覆盖初次失败，保留原记录，重试后700主键完整。',
       '2. 1→2切换时 case_043 Q3 n3 前段44.2614706秒、11次评估；剩余9.7385294秒用于接续初始化后没有新可行解。已保留前段官方有效方案 Makespan262943，逻辑summary有效且触帽。resume_attempt_outcome.json、resume_attempt_progress.json 和 interrupted_incumbent_retention.json 保留子段失败，不能隐藏，也不能重复计费。',
       '3. case_091 Q3 n5 的54秒改进没有完成首个评估，summary为deadline_without_incumbent；回退覆盖Makespan1865477。其覆盖方案相对全局下界仅约3.85%差距，失败未造成主键缺失。没有证据把初始化超时直接归因于内存不足或4worker竞争。',
       '4. 2→4迁移先停止旧父调度器领取新作业，当前两个solver用完原预算；case_089 Q1/Q2 n3有效后才接续。新根继承331项（含单worker的243项），剩余289项按4worker执行。原算法、评估器与官方输入未改，外部接续脚本全部附带。中断后的候选轨迹可能重建，因此这是用户授权的混合执行记录，不宣称等同于从头单worker连续跑的严格受控实验。',
       '5. 最终监督器记录 process_failed、exit_code=null；脚本分支在没有获得退出码时走入failed。Python写入finished/complete，最终报告700主、250配对、700独立检查且无缺失，stderr为空。这里保留原始监督器状态与独立观测说明，不把未知退出码补造为0，也不把完整验证结果说成求解失败。',
       '## 下一轮只建议三项',
       '1. **低尾图定向分区与依赖调度候选。** 以case_051/005/047/085/075/035为主，比较减少跨核边与改善最大核负载的候选。预期改善Q1通信和Q2/Q3空闲；风险是减少切边可能损害负载均衡。下一版用相同pilot预算、相同图核配置并保留全部失败验证，不能只选成功例。',
       '2. **按收益轨迹分配搜索预算。** 218项无Makespan收益消耗约32.7%改进作业秒；对U/L接近1、多个前缀无改进者考虑提前停止，把既定总预算给低尾难图，同时缓存/复用初始化状态以减少case_091式首评估未完成。风险是过早停止会错失后期改善；用固定总预算的新根pilot比较前缀曲线，不能现场改本轮预算。',
       '3. **将缓存与Spill候选集中到确有收益的配置。** '+('本次缓存平均仅1.0144倍、中位数约1，case_057/073明显受益。' if final else '先等最终同方案配对识别高收益配置。')+'同时关注case_067/073/091的Spill量，避免全图均匀扩大缓存搜索。风险是只优化命中率而增加复制或依赖等待；必须比较同一方案有/无L2，并同时记录Makespan、DDR与Spill。',
       '这些是下一轮建议，尚未启动新迭代。算法变更需要两机协调同源、新输出根、同预算pilot；day01不再加入另一版本成绩。',
       '## 文件与团队合并',
       'per_case.csv 为700个原始主键；improvements.csv 为700行；lower_tail.csv 为三问各50图的5核排序；budget_prefixes.csv 为真实轨迹前缀。analysis_metrics.json提供全部派生统计。执行脚本和1→2→4来源在execution_provenance/。标准transfer包含全部失败、方案、官方评估结果与请求，未包含官方输入或旧pilot成绩。',
       '发布位置为 research_a_orion_anytime/team_results/day01/shard_0/'+stage+'/；队友使用对应shard_1路径与相同CSV模式。两个final transfer须分别unpack到新空根，再按原campaign collect合并。只有1400主记录+500同方案对照且最终验证完整，才能称100图完成；冲突重复不得按成绩择优消解。',
       '本报告和CSV仅使用已保存结果的只读汇总；没有新增求解评估、smoke、哈希/指纹测试、pytest、unittest、全仓审计或benchmark。']
    (dest/'REPORT.md').write_text('\n\n'.join(text)+'\n',encoding='utf8')
    observation=dict(observed_at_utc=utc(),raw_supervisor_status=read(SOURCE.parent/'team_status.json'),
        python_status=read(SOURCE/'continuation_status.json'),report_expected=700,report_valid=700,valid_pairs=250,independent_checks=700,missing=[],
        interpretation='Supervisor classified unavailable/null ExitCode as failure. Actual exit code unknown; Python completion and complete official verification are available. Original record preserved.',
        note='This later observation does not promote a refinement_complete snapshot to final verification.')
    put(dest/'supervisor_observation.json',observation)
    status['supervisor_exit_code']=None;status['supervisor_status_record']='process_failed';status['supervisor_status_discrepancy']=True
    put(dest/'PHASE_STATUS.json',status)
    # Report sidecars travel with the standard transfer and retain their relative file links.
    meta=snap/'publication';meta.mkdir(exist_ok=False)
    for f in dest.iterdir():
        if f.is_file():shutil.copy2(f,meta/f.name)
    print(stage,'REPORT_READY',len(text))
