# ORION Trident：独立 S / M / F 整合

**代码发布：PR #38，分支 `integration/orion-trident-publish-20260925`。**

本目录与并行进行的 `research_a_orion_fusion/` 完全分开。结构、内存、FIFO 的候选共享同一份实际已评估好方案；新方案更优才替换。题目原图、配置、官方评估器、公共 ORION 和其他研究目录不修改。

当前算法版本 **trident-1.3**。此前本地交付已保存32个实测主臂、17个Q3同方案无L2对照、1200次主调用和16次被接受FIFO变换的映射/核归属核对。不同版本和修正实验分开记录；本次GitHub发布不重新执行实验。新百图正式成绩由三台主机实际运行后产生。

先读 `REVIEW_AND_RESULTS.md`、`EXPERIMENT_PLAN.md`、`METHOD.md`。三台主机分别使用 `HOST_0.md`、`HOST_1.md`、`HOST_2.md`。代码已发布，三台无需再次运行代码发布脚本；只在各自结果完成后创建分片结果PR。

## 入口与文件

|文件/目录|用途|
|---|---|
|`sources.py` / `selector.py` / `solve.py`|惰性候选、按收益/成本分配来源、共享incumbent与原评估|
|`vendor/structure` / `vendor/memory` / `vendor/orion`|冻结研究依赖；来源见SOURCE_MANIFEST|
|`fifo.py` / `trace.py`|实际COPY发射/填充/驱逐窗口，只重排已有子图|
|`pool.py` / `resources.py`|自适应进程、25% CPU/RAM余量目标、硬截止|
|`bootstrap.py` / `study_inputs.py`|按本片图分批取得原始字节、正式方案、文献和研究记录|
|`campaign.py` / `SHARDS.json`|34/33/33工作量均衡、三问核数全覆盖、条件消融|
|`report.py` / `paper.py` / `mechanisms.py`|1400主+500同方案配对、论文表格、独立参数研究|
|`run_windows.ps1`|三机通用入口；优先已有D:\python\python.exe，Python3.12.x CPU-only|
|`publish_results.ps1`|独立worktree提交本片结果PR、大原始包上传Release；不自动合并|
|`evidence/`|原样实测表、实际方案和证据位置索引|

运行核心只依赖标准库；画图才需要matplotlib。原图/config/官方Python文件从固定Git提交按原始字节复制，每次只恢复本机所需图。冻结vendor使三机不受其他Agent正在修改研究线代码的影响。

## 单配置时间

配置指 `(图, 问题, 核数)`。600秒包括进程启动、解析、种子回放、构造、搜索、写盘和Q3精确同方案无L2配对。提前耗尽或接近可信界即退出，不等满时间。定向消融使用该配置600秒尚余预算；不足则记录延期。历史种子成本另列，未知总历史成本留空。

一张图的完整三问/核数实验包含14个主配置，其总成本另报。30秒采点来自同一次运行的实际改善事件；外来种子早期历史未知时留空。

## 正式启动

在独立干净worktree中，以主机0为例：

```powershell
& .\research_a_orion_trident\run_windows.ps1 -ShardIndex 0 -FetchInputs -Seconds 600 -Hours 12
```

主机1、2只改ShardIndex。首次资料准备独立计时；复用输入时去掉`-FetchInputs`。完整拉取方法见`INSTALL_AND_PUBLISH.md`。

## 发布范围

远端文件与大原始附件的覆盖范围见`DELIVERY_STATUS.json`和`evidence/EVIDENCE_INDEX.json`。完整原始实验ZIP和原本地Git bundle在本次对话附件中保留；它们的安装/归档不是三机开跑的前置条件。不要把文件发布workflow记作性能实验，也不要将并行PR #37记作本目录交付。
