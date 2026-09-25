# 项目内部署、原生理论与本地数据接入检查

本次修补#42的安装与资料路径，并把已合并#44的理论直接接入六个写作角色。没有执行优化搜索或新的官方评估。

## 实际读取的资料

理论源来自#44的真实15文件包，核读提交20539cef853ea496055c8ad5652c7ac3a6113237。最终e79a992f4dc757ae3cd435087c8242fc631c60aa与其相比只删除临时工作流，理论文件未变。默认资料源现从main读取paper_a_theory，每次同步固定实际提交。

实验读取此前完整TRIDENT_REAL_EVIDENCE_20260925.zip，107595313字节、3010个归档条目。原题DOCX与config来自用户的原A题ZIP。检查目录含中文和空格，用来实际覆盖本次项目内路径。

|执行项|结果|
|---|---|
|当前项目解析|Agent与Git缓存都落在传入项目内；不使用固定安装盘符|
|本地完整归档|3010文件实际读取解包，未产生第二份joined.zip，源包只读|
|原始记录|finalcode_011_and_carry中011的14主配置与5同方案配对读取成功，零数据错误|
|原运行值|T1=184697、Q3五核=41849；该组记录版本trident-1.1，未取其他版本较小值|
|连续ZIP分卷|用真实选中记录组成两个连续分卷，10个文件恢复后逐字节相同|
|原生理论同步|15份理论文件+原DOCX+config共17份以batch_size=1进入真实Git读取链|
|术语转换|生成schema=1的29条词条，正文Makespan规范名为“总体任务执行时间”|
|输入登记|DOCX和ZIP为真实文件，ZIP同时含THEORY、合并GLOSSARY和本地数据清单；未再打包大原始数据|
|出版切换|adopt-export保留theory_pr38_v1；准备阶段未知版本仍为空|
|CLI路由|paths、prepare-theory和使用SESSION术语表的lint实际执行成功|

孤立接入目录最初未建立题目入口，文件登记检查定位了该问题。package-inputs现建立入口并通过临时ZIP完成发布，随后已实际完成文件输入参数生成。这个接入目录没有运行原workshop；正式工作区仍由原workshop创建。

PowerShell已改为AgentRoot变量，避免与内置只读HOME冲突，文件保存为带BOM的UTF-8以供Windows PowerShell读取。Windows原生运行、完整模板安装和PDF生产未在此检查中执行；这些状态保留在机器回执中，由本地生产流程实际登记。

本次检查的14主+5配对属于一张真实图的历史数据接收，不是新百图成绩；formal_ready=false。原始#42的编辑保护、重复分片及错误配对检查仍在review/VALIDATION.json中。本次回执为review/PROJECT_LOCAL_CHECKS.json。
