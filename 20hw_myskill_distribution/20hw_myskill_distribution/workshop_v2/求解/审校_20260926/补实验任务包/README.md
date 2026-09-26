# 两图、四组邻域对照

主实验与500组同方案缓存配对已经齐备。这份任务包用于增强“结构、驻留、缓存时序邻域各自有何作用”的证据，共8项作业，尚未执行。

## 执行内容

| 分配 | 题图 | 共同起点周期 | 四组启用来源 |
|---|---|---:|---|
| 机器一 | case_080，第3问、5核 | 63518 | smf、sm、sf、mf |
| 机器二 | case_046，第3问、5核 | 52952 | smf、sm、sf、mf |

s、m、f分别表示现有结构、驻留、FIFO时序来源，基础来源b四组均保留。每图使用同一个已有完整方案作为起点；每组120秒、最多512次评价、stop_gap=0，采用原来的work_adaptive选择策略。每图四组在同一台机器上顺序执行，单并发。两图共960秒作业配额，实际时间还包括启动和结果整理。

各图随包保存原执行源码、官方评价代码、图、配置、起点方案与响应，直接调用原队列和求解入口。case_080为trident-1.3-win-save.1，case_046为trident-1.3；完整来源见assets/清单.json。结果按图分别比较。主实验保持原样。

## 分机命令

需要Python 3.12；队列与官方评价入口使用标准库。在本目录执行，输出位置随当前目录确定：

```powershell
# 机器一
py -3.12 ablation.py prepare --case case_080 --out .\运行结果\case_080_第1轮
py -3.12 ablation.py run --prepared .\运行结果\case_080_第1轮
py -3.12 ablation.py collect --prepared .\运行结果\case_080_第1轮
```

机器二将三条命令中的case_080改成case_046。Linux使用python3.12代替py -3.12。每次prepare使用新的输出目录，原件保留在assets中。

prepare生成已适配本机路径的四份请求；run顺序运行四组；collect读取实际保存的方案、官方响应和进度，输出collected.csv及collected.json。无需重新下载大包。

## 返回材料与论文用途

运行完后交回整个输出目录，包括四组的request、progress、summary、plan、result、attempts，以及host_execution.json、collected.csv、collected.json。

主比较列为at_120_seconds：120秒内已保存可用的最好方案，按总体任务执行时间（Makespan）及等周期时的额外COPY字节排序。final另列最终保存结果。来源统计分别记录接受次数与周期改善次数，二者可因等周期COPY改善而不同。若候选评价数为0，结果只说明起点表现；该轮需继续分析停止原因。

已有32条旧诊断记录均未进入候选评价，暂不用于邻域贡献分析。新结果将单列为两图定向对照；相同协议的smf组作为其余三组的参照。现有600秒主实验结果仍用于主结果表。

任务包已检查入口、请求字段、预算传递、结果采集逻辑及Python语法；本机没有启动这8项实验。
