# FIFO／选择／时间预算接入口

当前默认仅启用 `sm`：结构线 S、内存线 M；原 ORION 的少量局部候选 B 继续保留。问题三仍调用原题 FIFO 评估器，所以“F 尚未接入”不是关闭硬件缓存。PR #26 和 #34 (`_wu`) 的新研究插件没有被自动导入；本轮不能称为三项新优化都已通过。

完成后的任一 FIFO 版本由独立适配模块提供：

```python
FUSION_API = 1

def propose(g, n, cfg, q, incumbent, feedback, deadline):
    # incumbent 是共享字典：plan / official_result。
    # deadline 是 time.monotonic() 的绝对截止。
    # 每次 yield 前读取最新 incumbent，不执行官方评估、不写文件。
    # 非适用场景可以直接 return，但函数需保持生成器形式。
    # yield {'name':..., 'family':'fifo/...', 'plan':...,
    #        'proxy':{'score':...}, 'bounds':真实官方语义下的必要条件界}
    yield from ()

def select_source(available, state, incumbent, seconds_left):
    # 可选：只选择当前存在的 's'/'m'/'f'/'b' 候选源。
    # 返回 None 表示有意识提前停止，不能返回无效来源。
    # state['attempts'] 含真实评估完成时间、周期、接受与否。
    # 不得把代理估计当成绩，也不修改官方缓存规则。
    return available[0]
```

这是接口示例，不是已实现的新FIFO算法；不要用空生成器冒充F模块验证成功。

将完成并审查的插件适配到此接口，再显式使用：

```powershell
.\research_a_orion_fusion\run_windows.ps1 -Components smf -FifoModule your_adapter_module -Out research_a_orion_fusion\runs\smf_round02_shard_0
```

必须新输出目录。两个 FIFO 研究版本先分别比较，选定一个模块后在三台使用同样版本，不能两台各加载不同版本却合并成同一正式结果。

首次接入用未在本轮测过的2–3图，包含缓存敏感图和缓存无收益图；同方案重新调用无L2评估。只在指定案例回归时做 SM/SF/MF；仍不能解释时做 S/M/F。当前仅SM时诊断只有S、M，不虚构三选二结果。主机已有baseline保留规则不变，第三问配对必须对应最终发布方案。

为保持惰性构造，现版提供的是“候选源选择”接口，不是旧分支的任意候选池 `select_candidate` 原样接入；该函数需由适配器转换。全局作业截止仍归宿主负责，插件不能自行延长。
